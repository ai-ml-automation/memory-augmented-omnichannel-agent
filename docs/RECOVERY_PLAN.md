# 🔄 RECOVERY_PLAN.md

## 1. Введение

### 1.1. Цель документа

Данный документ описывает процедуры восстановления системы «Омниканальный агент с долговременной памятью» после сбоев различного уровня — от отказа отдельного компонента до полной потери инфраструктуры. Он предназначен для DevOps-инженеров, администраторов и дежурных специалистов, обеспечивающих восстановление работоспособности системы в рамках заданных целей по времени (RTO) и точке восстановления (RPO).

План охватывает все критичные компоненты: базы данных (PostgreSQL, Qdrant, Neo4j, Redis), объектное хранилище MinIO, а также сам бэкенд и фронтенд. По каждому компоненту описаны шаги по восстановлению из бэкапов, проверке целостности данных и возврату в рабочее состояние.

### 1.2. Целевые показатели

| Показатель | Значение | Обоснование |
|------------|----------|-------------|
| **RPO (Recovery Point Objective)** | ≤ 1 час | Максимально допустимая потеря данных при сбое |
| **RTO (Recovery Time Objective)** | ≤ 4 часа | Максимально допустимое время простоя |
| **RTO для критичных компонентов** | ≤ 1 час | Для PostgreSQL и Qdrant (основные хранилища) |

### 1.3. Принципы восстановления

- **Приоритетность:** сначала восстанавливаются компоненты, обеспечивающие базовую функциональность (PostgreSQL, Redis, бэкенд).
- **Изоляция:** восстановление производится на отдельной инфраструктуре (staging-окружение) для проверки перед переключением production-трафика.
- **Автоматизация:** ключевые шаги автоматизированы скриптами (бэкапы, проверка целостности).
- **Документирование:** все действия фиксируются в логах для последующего анализа.

---

## 2. Бэкапы и их структура

### 2.1. Расписание и хранение

Бэкапы создаются ежедневно в **02:00 UTC** через скрипт [scripts/backup.sh](../scripts/backup.sh).

| Компонент | Тип бэкапа | Retention | Хранилище |
|-----------|------------|-----------|-----------|
| PostgreSQL | pg_dump (формат custom) | 30 дней | MinIO `omnichannel-backups/backups/` |
| Qdrant | Snapshot (API) | 30 дней | MinIO `omnichannel-backups/backups/` |
| Neo4j | APOC JSON экспорт | 30 дней | MinIO `omnichannel-backups/backups/` |
| MinIO | (сами объекты бэкапятся отдельно) | — | — |

**Структура каталога бэкапов:**
```
backups/
├── postgres_20260716_020000.dump
├── qdrant_20260716_020000.snapshot
├── neo4j_20260716_020000.json
└── latest -> postgres_latest.dump (симлинк)
```

### 2.2. Проверка целостности бэкапов

Периодически (раз в неделю) необходимо проверять бэкапы на целостность:

```bash
# Проверка PostgreSQL дампа
pg_restore --list /backups/postgres_latest.dump > /dev/null

# Проверка Qdrant снимка (загрузка в тестовую коллекцию)
curl -X PUT http://localhost:6333/collections/test/snapshots \
  -F "snapshot=@/backups/qdrant_latest.snapshot"

# Проверка Neo4j JSON (парсинг)
python -c "import json; json.load(open('/backups/neo4j_latest.json'))"
```

---

## 3. Восстановление PostgreSQL

### 3.1. Сценарий: Восстановление из бэкапа

**Шаги:**

1. **Остановить backend** (чтобы избежать записи новых данных во время восстановления):
   ```bash
   kubectl scale deployment backend -n omnichannel --replicas=0
   kubectl scale deployment celery-worker -n omnichannel --replicas=0
   ```

2. **Удалить существующую базу данных** (если она повреждена):
   ```bash
   kubectl exec -it deployment/postgres -n omnichannel -- \
     psql -U postgres -c "DROP DATABASE IF EXISTS omnichannel;"
   kubectl exec -it deployment/postgres -n omnichannel -- \
     psql -U postgres -c "CREATE DATABASE omnichannel;"
   ```

3. **Загрузить дамп из MinIO**:
   ```bash
   # Скачать последний дамп
   mc cp minio/omnichannel-backups/backups/postgres_latest.dump /tmp/
   ```

4. **Восстановить дамп**:
   ```bash
   kubectl cp /tmp/postgres_latest.dump deployment/postgres:/tmp/
   kubectl exec -it deployment/postgres -n omnichannel -- \
     pg_restore -U postgres -d omnichannel /tmp/postgres_latest.dump
   ```

5. **Запустить приложение**:
   ```bash
   kubectl scale deployment backend -n omnichannel --replicas=2
   kubectl scale deployment celery-worker -n omnichannel --replicas=1
   ```

6. **Проверить работоспособность**:
   ```bash
   curl -s http://localhost:8000/health | jq .
   ```

### 3.2. Сценарий: Переключение на реплику

Если настроена реплика и мастер-нода недоступна:

1. **Проверить статус реплики:**
   ```bash
   kubectl exec -it deployment/postgres-replica -n omnichannel -- pg_isready -U postgres
   ```

2. **Изменить DATABASE_URL** в секретах на реплику:
   ```bash
   kubectl edit secret backend-secrets -n omnichannel
   # Обновить database-url
   kubectl rollout restart deployment/backend -n omnichannel
   ```

3. **Настроить реплику как мастер** (при необходимости).

---

## 4. Восстановление Qdrant

### 4.1. Сценарий: Восстановление из снимка

1. **Остановить Qdrant**:
   ```bash
   kubectl scale deployment qdrant -n omnichannel --replicas=0
   ```

2. **Загрузить снимок из MinIO**:
   ```bash
   mc cp minio/omnichannel-backups/backups/qdrant_latest.snapshot /tmp/
   ```

3. **Запустить новый инстанс Qdrant и загрузить снимок**:
   ```bash
   kubectl apply -f k8s/base/qdrant.yml
   # Дождаться готовности пода
   kubectl wait --for=condition=ready pod -l app=qdrant -n omnichannel --timeout=300s
   ```

4. **Загрузить снимок через API**:
   ```bash
   curl -X PUT "http://qdrant:6333/collections/omnichannel/snapshots" \
     -H "Content-Type: multipart/form-data" \
     -F "snapshot=@/tmp/qdrant_latest.snapshot"
   ```

5. **Проверить восстановление**:
   ```bash
   curl -s http://qdrant:6333/collections/omnichannel | jq .
   ```

### 4.2. Альтернатива: Восстановление без снимка

Если снимок недоступен, система может работать без Qdrant (только с Redis-кэшем и PostgreSQL). Новые факты будут индексироваться после восстановления Qdrant.

---

## 5. Восстановление Neo4j

### 5.1. Сценарий: Восстановление из APOC JSON-экспорта

1. **Остановить Neo4j**:
   ```bash
   kubectl scale deployment neo4j -n omnichannel --replicas=0
   ```

2. **Загрузить JSON-экспорт из MinIO**:
   ```bash
   mc cp minio/omnichannel-backups/backups/neo4j_latest.json /tmp/
   ```

3. **Запустить Neo4j и выполнить импорт** (через APOC):
   ```bash
   kubectl apply -f k8s/base/neo4j.yml
   kubectl wait --for=condition=ready pod -l app=neo4j -n omnichannel --timeout=300s
   ```

   Затем выполните импорт через Cypher:
   ```cypher
   CALL apoc.import.json("file:///tmp/neo4j_latest.json", {useTypes: true})
   ```

   Для этого нужно скопировать JSON в контейнер:
   ```bash
   kubectl cp /tmp/neo4j_latest.json deployment/neo4j:/tmp/
   ```

4. **Проверить граф**:
   ```bash
   kubectl exec -it deployment/neo4j -n omnichannel -- \
     cypher-shell "MATCH (n) RETURN count(n);"
   ```

### 5.2. Если Neo4j не восстанавливается

Система продолжит работу только с PostgreSQL и Qdrant (без графовых запросов). Функциональность, зависящая от графа (анализ причинно-следственных связей), будет ограничена.

---

## 6. Восстановление Redis

Redis используется для кэша, очередей и чекпоинтов LangGraph. Потеря данных Redis не является критической (кэш перестроится, очереди могут быть перезапущены).

### 6.1. Восстановление из RDB/AOF

1. **Остановить Redis**:
   ```bash
   kubectl scale deployment redis -n omnichannel --replicas=0
   ```

2. **Восстановить файлы RDB/AOF из бэкапа** (если есть):
   ```bash
   mc cp minio/omnichannel-backups/backups/redis_latest.rdb /tmp/
   kubectl cp /tmp/redis_latest.rdb deployment/redis:/data/dump.rdb
   ```

3. **Запустить Redis**:
   ```bash
   kubectl scale deployment redis -n omnichannel --replicas=1
   ```

### 6.2. Если Redis не восстанавливается

- Очереди Celery будут потеряны, но задачи можно перезапустить вручную.
- Чекпоинты LangGraph (сессии пользователей) могут потеряться — пользователям потребуется перелогиниться.
- Кэш перестроится автоматически.

---

## 7. Восстановление MinIO

MinIO хранит аудиофайлы и бэкапы. Восстановление требуется только при полной потере данных.

1. **Остановить MinIO**:
   ```bash
   kubectl scale deployment minio -n omnichannel --replicas=0
   ```

2. **Восстановить данные из внешнего бэкапа** (если MinIO сам был забэкаплен).
3. **Запустить MinIO**:
   ```bash
   kubectl scale deployment minio -n omnichannel --replicas=1
   ```

---

## 8. Восстановление бэкенда и фронтенда

Бэкенд и фронтенд являются stateless и восстанавливаются простым перезапуском подов.

### 8.1. Перезапуск подов

```bash
kubectl rollout restart deployment/backend -n omnichannel
kubectl rollout restart deployment/frontend -n omnichannel
```

### 8.2. Восстановление из образа (при повреждении)

Если образ повреждён или изменён, восстановите предыдущую версию:

```bash
kubectl set image deployment/backend backend=your-registry/omnichannel-backend:previous-tag -n omnichannel
kubectl rollout status deployment/backend -n omnichannel
```

---

## 9. Тестирование восстановления

### 9.1. План тестирования

- **Ежеквартально** проводить «учения» по восстановлению:
  1. Выбрать сценарий (например, потеря PostgreSQL).
  2. Выполнить восстановление на отдельном окружении (staging).
  3. Измерить фактическое время (RTO) и сверить с целевыми показателями.
  4. Задокументировать результаты и скорректировать процедуры.

### 9.2. Проверка целостности после восстановления

После восстановления проверьте:

1. API (`/health`) — все сервисы должны быть зелёными.
2. Некритичные функции (например, `/chat/health`, `/voice/health`).
3. Наличие данных (выполните запрос к памяти пользователя).
4. Celery задачи (отправьте сообщение в чат и проверьте, что задача выполняется).

---

## 10. Аварийное восстановление всего кластера

В случае полной потери кластера (облачного провайдера или дата-центра) выполните:

1. **Развернуть новый кластер Kubernetes**.
2. **Восстановить все манифесты** из репозитория:
   ```bash
   kubectl apply -f k8s/base/
   ```
3. **Восстановить базы данных** из бэкапов в MinIO (или другого внешнего хранилища) в порядке: PostgreSQL → Neo4j → Qdrant → Redis.
4. **Запустить приложение** и проверить работоспособность.
