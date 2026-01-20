# Flight Tracker Deployment Guide

## 1. Accessing Services

Since the services run inside a Kubernetes cluster (Kind), you can access them using `kubectl port-forward`.

### API Access
Run these commands in separate terminal windows:
- **User Manager**: `kubectl port-forward svc/user-manager 5000:5000`
- **Data Collector**: `kubectl port-forward svc/data-collector 5001:5000`

### Monitoring Access
- **Prometheus UI**: [http://localhost:30090](http://localhost:30090)
- **User Manager Metrics**: [http://localhost:30000/metrics](http://localhost:30000/metrics)

---

## 2. API Documentation & Examples

Use these examples to test the cluster once port-forwarding is active.

### User Manager (Local Port 5000)

| Action              | Command Example                                                                                                                                                                                                                                                       |
|:--------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Add User**        | `curl -X POST http://localhost:5000/users -H "Content-Type: application/json" -H "Idempotency-Key: key1" -d '{"email": "mario.rossi@gmail.com", "first_name": "Mario", "last_name": "Rossi", "tax_code": "RSSMRA85D15Z404E", "iban": "IT19Z1234567890000123456789"}'` |
| **Add Telegram ID** | `curl -X POST http://localhost:5000/users/telegram -H "Content-Type: application/json" -d '{"email": "mario.rossi@gmail.com", "telegram_chat_id": "your-chat-id"}'`                                                                                                   |
| **Get User**        | `curl http://localhost:5000/users/mario.rossi@gmail.com`                                                                                                                                                                                                              |
| **Delete User**     | `curl -X DELETE http://localhost:5000/users/mario.rossi@gmail.com -H "Idempotency-Key: key2"`                                                                                                                                                                         |
| **Ping**            | `curl http://localhost:5000/ping`                                                                                                                                                                                                                                     |

### Data Collector (Local Port 5001)

| Action             | Command Example                                                                                                                                                                     |
|:-------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Add Interest**   | `curl -X POST http://localhost:5001/interests -H "Content-Type: application/json" -d '{"email": "mario.rossi@gmail.com", "airport_code": "LIRF", "high_value": 2, "low_value": 1}'` |
| **Get Flights**    | `curl http://localhost:5001/flights/LIRF`                                                                                                                                           |
| **Get Departures** | `curl http://localhost:5001/flights/LIRF?type=departures`                                                                                                                           |
| **Get Arrivals**   | `curl http://localhost:5001/flights/LIRF?type=arrivals`                                                                                                                             |
| **Get Interests**  | `curl http://localhost:5001/interests/mario.rossi@gmail.com`                                                                                                                        |
| **Daily Average**  | `curl http://localhost:5001/flights/average/LICC`                                                                                                                                   |
| **Last Flight**    | `curl http://localhost:5001/flights/last/LICC`                                                                                                                                      |
| **Ping**           | `curl http://localhost:5001/ping`                                                                                                                                                   |

---

## 3. Monitoring with Prometheus

### Service Health
1. Open [http://localhost:30090](http://localhost:30090).
2. Go to **Status** -> **Targets**.
3. All endpoints (`user-manager`, `data-collector`) should show as **UP**.

### Useful Prometheus Queries
Paste these into the **Graph** tab:
- **Request Traffic**: `rate(http_requests_total{service="user-manager"}[1m])`
- **External API Latency**: `opensky_api_call_duration_seconds`
- **Data Collection Volume**: `flights_fetched_total`

---

## 4. Troubleshooting & Cleanup

### View Logs
```bash
# Alert Notifier logs
kubectl logs -l app=alert-notifier-system --tail=50

# Kafka logs
kubectl logs -l app=kafka --tail=50
```

### Delete Cluster
To completely remove the environment:
```bash
kind delete cluster --name flight-tracker
```
