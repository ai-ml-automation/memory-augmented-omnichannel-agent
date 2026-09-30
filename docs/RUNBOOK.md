# 🚨 RUNBOOK.md

## 1. Введение

Данный Runbook предназначен для инженеров, выполняющих дежурство (on‑call) по системе «Омниканальный агент с долговременной памятью». Он содержит краткие пошаговые инструкции по проверке здоровья системы, реагированию на типовые инциденты, масштабированию и восстановлению.

**Целевая аудитория:** инженеры, администраторы, DevOps.

**Связанные документы:**
- [MONITORING_GUIDE.md](MONITORING_GUIDE.md) — подробное описание метрик, дашбордов и алертов.
- [RECOVERY_PLAN.md](RECOVERY_PLAN.md) — детальные процедуры восстановления после сбоев.
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — развёртывание и обновление.
- [SCALING_GUIDE.md](SCALING_GUIDE.md) — масштабирование компонентов.

---

## 2. Проверка здоровья системы

### 2.1. HTTP Health‑checks

| Эндпоинт | Назначение | Ожидаемый статус |
|----------|------------|------------------|
| `GET /health` | Проверка всех зависимостей (PG, Redis, Qdrant, Neo4j) | `200 OK`, `"status": "healthy"` |
| `GET /chat/health` | Статус LLM | `200 OK`, `"enabled": true` |
| `GET /voice/health` | Статус голосовых сервисов | `200 OK`, `"voice_enabled": true` |
| `GET /metrics` | Prometheus метрики | `200 OK`, текстовый формат |

**Быстрая проверка:**
```bash
curl -s http://localhost:8000/health | python -m json.tool
```

### 2.2. Состояние Docker / Kubernetes

**Docker Compose (dev/staging):**
```bash
docker compose ps
docker compose logs --tail=100 backend
```

**Kubernetes (production):**
```bash
kubectl get pods -n omnichannel
kubectl get deployments -n omnichannel
kubectl get services -n omnichannel
kubectl get hpa -n omnichannel
kubectl logs -n omnichannel deployment/backend --tail=100
```

### 2.3. Состояние Celery

Проверка воркеров и очередей:

```bash
# Проверить статус воркеров (через Celery CLI)
kubectl exec -it deployment/celery-worker -n omnichannel -- celery -A src.celery_app status

# Проверить длину очереди (Redis)
kubectl exec -it deployment/redis -n omnichannel -- redis-cli LLEN celery
```

**Признаки проблем:**
- Воркеры не отвечают (`celery status` показывает `OFFLINE`).
- Длина очереди растёт (> 100 задач).
- В логах воркеров ошибки подключения к Redis или БД.

### 2.4. Состояние Vault (если используется)

```bash
# Проверить аутентификацию
kubectl exec -it deployment/backend -n omnichannel -- \
  python -c "from src.vault_client import get_vault_client; print(get_vault_client().is_authenticated())"
```

Если Vault недоступен, приложение использует fallback из `.env` (но в production это не должно происходить).

---

## 3. Сбои PostgreSQL

### Симптомы
- Ошибки `connection refused` или `timeout` в логах backend.
- Health‑check `/health` возвращает `postgres: unhealthy`.
- Запросы к API завершаются 500.

### Действия

1. **Проверить статус контейнера / пода:**
   ```bash
   docker compose ps postgres              # Docker
   kubectl get pods -l app=postgres -n omnichannel   # K8s
   ```

2. **Проверить логи:**
   ```bash
   docker compose logs --tail=50 postgres
   kubectl logs -n omnichannel deployment/postgres --tail=50
   ```

3. **Проверить доступность БД:**
   ```bash
   docker compose exec postgres pg_isready -U postgres
   kubectl exec -it deployment/postgres -n omnichannel -- pg_isready -U postgres
   ```

4. **Перезапустить PostgreSQL:**
   ```bash
   docker compose restart postgres
   kubectl rollout restart deployment/postgres -n omnichannel
   ```

5. **Если данные повреждены — восстановить из бэкапа** (см. [RECOVERY_PLAN.md](RECOVERY_PLAN.md), раздел "PostgreSQL Recovery").

### Переключение на реплику (production)

Если настроена реплика, измените `DATABASE_URL` в Secret:

```bash
kubectl edit secret backend-secrets -n omnichannel
# обновить database-url на реплику
kubectl rollout restart deployment/backend -n omnichannel
kubectl rollout restart deployment/celery-worker -n omnichannel
```

---

## 4. Недоступность Qdrant

### Симптомы
- Ошибки векторного поиска в логах (`vector_store_service`).
- Memory search не возвращает релевантные результаты.
- Health‑check показывает `qdrant: unhealthy`.

### Действия

1. **Проверить статус:**
   ```bash
   docker compose ps qdrant
   curl -s http://localhost:6333/healthz
   kubectl get pods -l app=qdrant -n omnichannel
   ```

2. **Перезапустить:**
   ```bash
   docker compose restart qdrant
   kubectl rollout restart deployment/qdrant -n omnichannel
   ```

3. **Если Qdrant недоступен длительное время:**
   - Система автоматически переходит в режим работы без памяти (используется только Redis-кэш).
   - Операции записи новых фактов будут откладываться до восстановления.
   - После восстановления новые факты будут проиндексированы автоматически.

**Fallback:** при недоступности Qdrant API `/memory/search` возвращает только результаты из PostgreSQL (ключевой поиск), без векторной и графовой частей.

---

## 5. Сбой Celery

### Симптомы
- Задачи не обрабатываются (очередь растёт).
- Воркеры не стартуют или падают.
- Ошибки в логах `celery-worker`.

### Действия

1. **Проверить статус воркеров:**
   ```bash
   kubectl get pods -l app=celery-worker -n omnichannel
   kubectl logs -n omnichannel deployment/celery-worker --tail=50
   ```

2. **Проверить очередь (Redis):**
   ```bash
   kubectl exec -it deployment/redis -n omnichannel -- redis-cli LLEN celery
   ```

3. **Перезапустить воркеры:**
   ```bash
   kubectl rollout restart deployment/celery-worker -n omnichannel
   ```

4. **Если очередь переполнена (>1000 задач):**
   - Увеличьте количество воркеров (см. раздел "Масштабирование").
   - При необходимости очистите очередь (крайняя мера):
     ```bash
     kubectl exec -it deployment/redis -n omnichannel -- redis-cli DEL celery
     ```
   - **Предупреждение:** очистка очереди приведёт к потере необработанных задач.

5. **Проверить Celery Beat (планировщик):**
   ```bash
   kubectl logs -n omnichannel deployment/celery-beat --tail=50
   ```
   Если Beat не работает, задачи DecayAgent не будут запускаться.

---

## 6. Недоступность Vault

### Симптомы
- Ошибки в логах backend при попытке чтения секретов.
- Приложение не стартует (если Vault обязателен).

### Действия

1. **Проверить Vault:**
   ```bash
   curl -s http://vault:8200/v1/sys/health
   kubectl get pods -l app=vault -n omnichannel
   ```

2. **Если Vault недоступен, а приложение использует fallback:**
   - Убедитесь, что в Secret `backend-secrets` заданы все необходимые значения (JWT_SECRET, ENCRYPTION_KEY и др.).
   - Приложение автоматически переключится на чтение из переменных окружения, если `APP_ENV != production` или Vault недоступен.

3. **Перезапустить Vault:**
   ```bash
   kubectl rollout restart deployment/vault -n omnichannel
   ```

4. **Если Vault не восстанавливается — временно отключите интеграцию:**
   - Установите `APP_ENV=development` в ConfigMap (только для аварийных случаев, не рекомендуется в production).

---

## 7. Высокая нагрузка

### Симптомы
- Высокое потребление CPU/Memory (>80%).
- Увеличение времени ответа API.
- Рост очереди Celery.

### Действия

**1. Масштабирование подов (K8s):**

```bash
# Увеличить количество реплик backend
kubectl scale deployment backend -n omnichannel --replicas=4

# Увеличить количество воркеров Celery
kubectl scale deployment celery-worker -n omnichannel --replicas=3
```

**2. Проверить HPA (если настроен):**
```bash
kubectl get hpa -n omnichannel
kubectl describe hpa backend-hpa -n omnichannel
```

Если HPA не срабатывает — проверьте метрики (CPU, Memory) в Prometheus.

**3. Увеличить concurrency Celery (вручную):**

Измените переменную окружения `CELERY_WORKER_CONCURRENCY` в Deployment и перезапустите:

```bash
kubectl set env deployment/celery-worker -n omnichannel CELERY_WORKER_CONCURRENCY=8
kubectl rollout restart deployment/celery-worker -n omnichannel
```

**4. Проверить нагрузку на базы данных:**
- PostgreSQL: `kubectl top pods -l app=postgres`
- Qdrant: проверьте метрики в Grafana (панель Qdrant).

---

## 8. Мониторинг и алерты

### 8.1. Основные метрики

| Метрика | Назначение | Порог |
|---------|------------|-------|
| `http_request_duration_seconds` | Задержка API | P95 > 3s (warning) |
| `llm_request_duration_seconds` | Задержка LLM | P95 > 5s (warning) |
| `qdrant_search_duration_seconds` | Задержка поиска в Qdrant | P95 > 2s (warning) |
| `http_requests_total{status=~"5.."}` | Ошибки 5xx | > 5% (critical) |
| `conflicts_detected_total{resolution="hitl_required"}` | HITL конфликты | > 10/час (warning) |
| `celery_queue_length` | Длина очереди Celery | > 100 (warning) |

### 8.2. Доступ к Grafana

- **URL:** `http://grafana.example.com` (или через port‑forward)
- **Логин:** `admin`
- **Пароль:** из секретов Grafana

**Дашборды:**
- **Omnichannel Backend** — технические метрики.
- **Business Metrics** — бизнес-показатели (память, NPS, AHT).
- **Celery Dashboard** — состояние очередей и воркеров (если настроен).

### 8.3. Алерты (Prometheus)

Настроены в [config/prometheus-rules.json](../config/prometheus-rules.json).

| Alert | Severity | Действие |
|-------|----------|----------|
| `HighLLMLatency` | warning | Проверить LLM, увеличить ресурсы / переключить провайдер |
| `BackendHighLatency` | warning | Проверить нагрузку, масштабировать backend |
| `QdrantHighLatency` | warning | Проверить Qdrant, увеличить ресурсы |
| `BackendHighErrRate` | critical | Проверить логи, перезапустить backend |
| `HighConflictRate` | warning | Проверить логику ConflictResolver, возможно, требуется доработка |
| `QdrantDown` | critical | Перезапустить Qdrant, проверить хранилище |

---

## 9. Восстановление из бэкапа

> **Подробные инструкции см. в [RECOVERY_PLAN.md](RECOVERY_PLAN.md).**

**Краткая шпаргалка:**

### PostgreSQL
```bash
# Остановить backend
kubectl scale deployment backend -n omnichannel --replicas=0

# Восстановить из дампа
kubectl exec -it deployment/postgres -n omnichannel -- \
  pg_restore -U postgres -d omnichannel /backups/postgres_latest.dump

# Запустить backend
kubectl scale deployment backend -n omnichannel --replicas=2
```

### Qdrant
```bash
# Загрузить снимок через API
curl -X PUT http://qdrant:6333/collections/omnichannel/snapshots \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/path/to/snapshot.snapshot"
```

### Neo4j
```bash
# Загрузить APOC JSON экспорт (через Neo4j Browser или API)
# Подробнее: docs/RECOVERY.md
```

---

## 10. Наиболее частые проблемы

| Проблема | Решение |
|----------|---------|
| `ENABLE_LLM=false` в логах | Установить `ENABLE_LLM=true` в ConfigMap/Secret, перезапустить |
| `ModuleNotFoundError` в тестах | Проверить `PYTHONPATH`, установить зависимости |
| JWT expired | Пользователю перелогиниться; проверить `JWT_EXPIRATION_HOURS` |
| Neo4j auth failed | Проверить `NEO4J_USER` / `NEO4J_PASSWORD` в секретах |
| Rate limit 429 | Увеличить лимиты в `slowapi` (см. [MONITORING_GUIDE.md](MONITORING_GUIDE.md)) |
| Celery Beat не запускает задачи | Проверить `CELERY_BROKER_URL`, перезапустить Beat |
| Vault authentication failed | Проверить `VAULT_TOKEN`, статус Vault |
| Очередь Celery не очищается | Проверить воркеры, при необходимости очистить очередь (см. раздел 5) |
