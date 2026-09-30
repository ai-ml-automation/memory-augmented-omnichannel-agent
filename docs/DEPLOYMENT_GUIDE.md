# 🚀 DEPLOYMENT_GUIDE.md

## 1. Введение

### 1.1. Обзор

Данное руководство описывает процесс развёртывания системы «Омниканальный агент с долговременной памятью» в production-окружении на базе Kubernetes. Процесс включает сборку Docker-образов, настройку секретов, применение Kubernetes-манифестов, настройку Ingress с SSL-сертификатами и проверку работоспособности.

Система состоит из следующих компонентов, каждый из которых развёртывается в отдельном поде или наборе подов:

- **Backend API** — FastAPI приложение, обрабатывающее запросы.
- **Frontend** — React SPA, раздаваемый через Nginx.
- **Celery Worker** — обработка асинхронных задач (извлечение фактов, decay).
- **Celery Beat** — планировщик периодических задач.
- **PostgreSQL** — реляционная база данных (обычно управляется внешним оператором, но может быть развёрнута в кластере).
- **Redis** — кэш и брокер сообщений (также может быть внешним).
- **Qdrant** — векторная база данных.
- **Neo4j** — графовая база данных.
- **MinIO** — S3-совместимое объектное хранилище.
- **Prometheus + Grafana + Loki + Jaeger** — стек мониторинга (опционально).

В production-окружении базы данных (PostgreSQL, Redis, Qdrant, Neo4j, MinIO) часто выносятся за пределы кластера (управляемые сервисы облачного провайдера). Данное руководство предполагает, что они уже развёрнуты и доступны по сетевым адресам.

### 1.2. Требования

Перед началом развёртывания убедитесь, что:

- Кластер Kubernetes (версия 1.24+) доступен и настроен.
- Установлен и настроен `kubectl`.
- Установлен `docker` (или другой контейнерный рантайм).
- Доступен container registry (например, Docker Hub, Yandex Container Registry, или локальный реестр).
- Настроены DNS-записи для домена приложения (например, `app.example.com`).
- Установлен ingress-контроллер (например, nginx-ingress).
- Установлен cert-manager для автоматического получения SSL-сертификатов (опционально, но рекомендуется).

---

## 2. Сборка образов

Система использует **многостадийные Dockerfile** для оптимизации размера образов и безопасности.

### 2.1. Бэкенд

Файл: [Dockerfile.backend.prod](../Dockerfile.backend.prod)

```bash
docker build -f Dockerfile.backend.prod -t backend:latest .
```

**Особенности**:
- **Stage 1 (builder)**: Устанавливает зависимости в отдельный слой.
- **Stage 2 (production)**: Копирует только необходимые файлы, запускается от non-root пользователя.
- Healthcheck: проверяет `/health` каждые 30 секунд.

**Тегирование для реестра** (замените `your-registry`):

```bash
docker tag backend:latest your-registry/omnichannel-backend:latest
docker push your-registry/omnichannel-backend:latest
```

### 2.2. Фронтенд

Файл: [Dockerfile.frontend.prod](../Dockerfile.frontend.prod)

```bash
docker build -f Dockerfile.frontend.prod -t frontend:latest .
```

**Особенности**:
- **Stage 1 (builder)**: Собирает React-приложение (npm run build).
- **Stage 2 (production)**: Nginx Alpine с собранными статическими файлами.
- Healthcheck: проверяет `/health` (Nginx возвращает 200 OK).

**Тегирование для реестра**:

```bash
docker tag frontend:latest your-registry/omnichannel-frontend:latest
docker push your-registry/omnichannel-frontend:latest
```

---

## 3. Настройка секретов

### 3.1. Создание Kubernetes Secret

Все чувствительные данные должны храниться в Kubernetes Secret. Создайте файл [k8s/base/secrets.yml](../k8s/base/secrets.yml) (не коммитьте его в репозиторий с реальными значениями):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
  namespace: omnichannel
type: Opaque
stringData:
  # Database
  database-url: "postgresql+asyncpg://user:password@postgres-host:5432/omnichannel"
  # Redis
  redis-url: "redis://redis-host:6379/0"
  # Qdrant
  qdrant-url: "http://qdrant-host:6333"
  qdrant-api-key: "your-qdrant-api-key"
  # Neo4j
  neo4j-uri: "bolt://neo4j-host:7687"
  neo4j-user: "neo4j"
  neo4j-password: "your-neo4j-password"
  # JWT
  jwt-secret: "your-jwt-secret-32-chars-min"
  # Encryption
  encryption-key: "your-32-byte-aes-key"
  # LLM (если используется)
  yandex-api-key: "your-yandex-api-key"
  # Messengers
  telegram-bot-token: "your-telegram-token"
  vk-access-token: "your-vk-token"
  # Vault (если используется)
  vault-token: "your-vault-token"
```

Примените секрет:

```bash
kubectl apply -f k8s/base/secrets.yml
```

### 3.2. Интеграция с HashiCorp Vault (опционально)

Если используется Vault, установите и настройте его отдельно. Приложение ([backend/src/vault_client.py](../backend/src/vault_client.py)) будет автоматически читать секреты из Vault в production-режиме (`APP_ENV=production`). Убедитесь, что:

- Vault доступен по `VAULT_URL`.
- Установлен `VAULT_TOKEN` с правами на чтение пути `secret/omnichannel`.
- В Vault созданы ключи: `jwt_secret`, `encryption_key` и другие.

---

## 4. Применение Kubernetes манифестов

Все манифесты находятся в директории [k8s/base/](../k8s/base/).

### 4.1. Порядок применения

```bash
kubectl apply -f k8s/base/namespace.yml
kubectl apply -f k8s/base/configmap.yml
kubectl apply -f k8s/base/secrets.yml
kubectl apply -f k8s/base/backend.yml
kubectl apply -f k8s/base/celery-worker.yml
kubectl apply -f k8s/base/celery-beat.yml
kubectl apply -f k8s/base/frontend.yml
kubectl apply -f k8s/base/ingress.yml
kubectl apply -f k8s/base/hpa.yml
kubectl apply -f k8s/base/network-policy.yml
kubectl apply -f k8s/base/pdb.yml
```

### 4.2. Описание манифестов

| Манифест | Назначение |
|----------|------------|
| `namespace.yml` | Создаёт namespace `omnichannel` |
| `configmap.yml` | Несекретные переменные окружения (QDRANT_URL, NEO4J_URI, LOG_LEVEL) |
| `secrets.yml` | Секреты (не коммитится с реальными значениями) |
| `backend.yml` | Deployment и Service для FastAPI (2 реплики) |
| `celery-worker.yml` | Deployment для Celery worker (1 реплика, масштабируется через HPA) |
| `celery-beat.yml` | Deployment для Celery Beat (1 реплика) |
| `frontend.yml` | Deployment и Service для React (2 реплики) |
| `ingress.yml` | Ingress для маршрутизации трафика |
| `hpa.yml` | HorizontalPodAutoscaler для backend (2–10 реплик) |
| `network-policy.yml` | Ограничение сетевого доступа |
| `pdb.yml` | PodDisruptionBudget (минимум 1 работающий под) |

### 4.3. Проверка статуса

```bash
kubectl get pods -n omnichannel
kubectl get deployments -n omnichannel
kubectl get services -n omnichannel
kubectl get hpa -n omnichannel
```

---

## 5. Настройка Ingress и SSL

### 5.1. Ingress (HTTP/HTTPS)

Файл: [k8s/base/ingress.yml](../k8s/base/ingress.yml)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: omnichannel-ingress
  namespace: omnichannel
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.example.com
      secretName: omnichannel-tls
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

**Обязательно замените** `app.example.com` на ваш реальный домен.

### 5.2. SSL-сертификаты (cert-manager)

Если используется cert-manager, убедитесь, что он установлен в кластере:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.12.0/cert-manager.yaml
```

Создайте ClusterIssuer (если ещё нет):

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

После применения ingress, cert-manager автоматически получит и обновит сертификат.

---

## 6. Мониторинг и логирование

### 6.1. Стек мониторинга (опционально)

Для production рекомендуется развернуть стек мониторинга в отдельном namespace:

- **Prometheus** — сбор метрик.
- **Grafana** — визуализация.
- **Loki** — сбор логов.
- **Jaeger** — трассировка.
- **Alertmanager** — оповещения.

Конфигурации для этих сервисов находятся в [config/](../config/) (prometheus.yml, loki.yml, promtail.yml, grafana provisioning).

Их можно развернуть отдельно, используя Helm-чарты или отдельные манифесты.

### 6.2. Доступ к дашбордам

После развёртывания Grafana:

- **URL**: `http://grafana.example.com` (или через порт-форвардинг)
- **Логин**: `admin`
- **Пароль**: см. секреты Grafana

Дашборды:
- **Omnichannel Backend** — технические метрики.
- **Business Metrics** — бизнес-показатели (память, NPS, AHT).

---

## 7. Проверка работоспособности

### 7.1. Health checks

| Эндпоинт | Назначение |
|----------|------------|
| `GET /health` | Проверка всех зависимостей (PG, Redis, Qdrant, Neo4j) |
| `GET /chat/health` | Статус LLM |
| `GET /voice/health` | Статус голосовых сервисов |
| `GET /metrics` | Prometheus метрики |

**Пример проверки**:

```bash
curl -v https://app.example.com/health
```

Ожидаемый ответ (все сервисы здоровы):

```json
{
  "status": "healthy",
  "services": {
    "postgres": "healthy",
    "redis": "healthy",
    "qdrant": "healthy",
    "neo4j": "healthy"
  }
}
```

### 7.2. Smoke-тестирование API

1. **Регистрация пользователя**:

```bash
curl -X POST https://app.example.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"phone": "+79991234567", "password": "TestPass123!"}'
```

2. **Логин**:

```bash
curl -X POST https://app.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "+79991234567", "password": "TestPass123!"}' \
  -c cookies.txt
```

3. **Отправка сообщения** (с авторизацией из cookies):

```bash
curl -X POST https://app.example.com/api/v1/chat/users/123/message \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "Hello, agent!", "channel_type": "web"}'
```

---

## 8. Обновление и откат

### 8.1. Стратегия обновления

В манифестах используется стратегия **RollingUpdate** (по умолчанию). При обновлении образов новые поды создаются постепенно, без простоя.

```bash
# Обновить образ backend
kubectl set image deployment/backend backend=your-registry/omnichannel-backend:v2.0 -n omnichannel

# Следить за обновлением
kubectl rollout status deployment/backend -n omnichannel
```

### 8.2. Откат

Если новая версия работает некорректно:

```bash
kubectl rollout undo deployment/backend -n omnichannel
```

### 8.3. Обновление ConfigMap/Secret

Если изменился ConfigMap или Secret, их нужно переприменить, а затем перезапустить поды:

```bash
kubectl apply -f k8s/base/configmap.yml
kubectl rollout restart deployment/backend -n omnichannel
```

---

## 9. Troubleshooting (типичные проблемы)

### 9.1. Поды не стартуют (ImagePullBackOff)

Проверьте, что образы загружены в реестр и указаны правильные теги:

```bash
kubectl describe pod <pod-name> -n omnichannel
```

### 9.2. Недоступность базы данных

Проверьте строки подключения в секретах и сетевую достижимость:

```bash
kubectl exec -it deployment/backend -n omnichannel -- \
  python -c "import psycopg2; conn = psycopg2.connect('postgresql://...')"
```

### 9.3. Ingress не работает (404)

Проверьте, что ingress-контроллер запущен и правила корректны:

```bash
kubectl get ingress -n omnichannel
kubectl describe ingress omnichannel-ingress -n omnichannel
```

### 9.4. Нет метрик в Prometheus

Убедитесь, что `prometheus-fastapi-instrumentator` настроен и `/metrics` доступен:

```bash
curl https://app.example.com/metrics
```

---

## 10. Переменные окружения (production)

Полный список переменных, которые должны быть заданы в `ConfigMap` и `Secret`:

| Переменная | Где задаётся | Назначение |
|------------|--------------|------------|
| `APP_ENV` | ConfigMap | `production` (включает режим production) |
| `DATABASE_URL` | Secret | Подключение к PostgreSQL |
| `REDIS_URL` | Secret | Подключение к Redis |
| `QDRANT_URL` | ConfigMap | URL Qdrant |
| `QDRANT_API_KEY` | Secret | API-ключ Qdrant (если требуется) |
| `NEO4J_URI` | ConfigMap | URI Neo4j |
| `NEO4J_USER` | Secret | Пользователь Neo4j |
| `NEO4J_PASSWORD` | Secret | Пароль Neo4j |
| `JWT_SECRET` | Secret | Секрет для JWT (32+ символов) |
| `ENCRYPTION_KEY` | Secret | Ключ AES-256-GCM (32 байта) |
| `ENABLE_LLM` | ConfigMap | `true` или `false` |
| `ENABLE_VOICE` | ConfigMap | `true` или `false` |
| `ENABLE_MEMORY` | ConfigMap | `true` или `false` |
| `CORS_ORIGINS` | ConfigMap | Список разрешённых origin'ов (через запятую) |
| `VAULT_URL` | ConfigMap | URL Vault (если используется) |
| `VAULT_TOKEN` | Secret | Токен Vault |
