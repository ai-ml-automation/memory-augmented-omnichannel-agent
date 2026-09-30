# Load Testing

## Setup

```bash
pip install locust
```

## Running

```bash
# From project root
locust -f backend/tests/load/locustfile.py --host http://localhost:8000

# Headless mode (CI)
locust -f backend/tests/load/locustfile.py --host http://localhost:8000 \
    --headless -u 100 -r 10 --run-time 60s \
    --csv=results/load_test
```

## Test Scenarios

| User Type | Description | Target |
|-----------|-------------|--------|
| HealthCheckUser | Hits /health and / endpoints | Health endpoint |
| RegisterLoginUser | Registers and logs in | Auth endpoints |
| ChatUser | Sends chat messages, evaluates responses | Chat endpoints |

## Metrics

- **p95 latency**: Target < 500ms for health, < 2000ms for chat
- **Throughput**: Target > 100 req/s for health, > 20 req/s for chat
- **Error rate**: Target < 1%
