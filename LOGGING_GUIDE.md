argentum.mintllm.2025# Enhanced Logging Guide

## Overview

This project now includes comprehensive logging capabilities for all backend services and API routing. The logging infrastructure has been enhanced with:

- **Detailed request/response tracking** for all HTTP endpoints
- **Structured log formats** with timestamps and service identifiers
- **Docker Compose log management** with rotation and size limits
- **Request middleware** that logs all incoming/outgoing traffic
- **Enhanced error tracking** and debugging information

## Docker Compose Logging

### View Logs for All Services

```bash
# View all services logs with timestamps
docker compose logs -f

# View specific service logs
docker compose logs -f npci
docker compose logs -f rem_bank
docker compose logs -f bene_bank
docker compose logs -f payer_psp
docker compose logs -f payee_psp
docker compose logs -f orchestrator
docker compose logs -f payment_ui

# View multiple services
docker compose logs -f npci rem_bank bene_bank

# View last N lines
docker compose logs --tail=100 npci

# View logs since specific time
docker compose logs --since 10m npci
docker compose logs --since "2024-01-01T12:00:00"
```

### Log Configuration

All services are configured with:
- **Log Driver**: json-file
- **Max Size**: 10MB per file
- **Max Files**: 3 rotated log files
- **PYTHONUNBUFFERED**: 1 (ensures real-time log output)
- **FLASK_ENV**: development (for detailed Flask logging)

## Log Format

All services use a consistent, structured log format:

```
YYYY-MM-DD HH:MM:SS [LEVEL] [service_name] message
```

### Example Logs

```
2024-01-28 10:30:45 [INFO] [npci] ==> Incoming POST /api/reqpay | Content-Type: application/xml | Content-Length: 1245 | Remote: 172.18.0.5
2024-01-28 10:30:45 [INFO] [npci] [NPCI] /api/reqpay received body (first 500 chars): <?xml version="1.0"...
2024-01-28 10:30:45 [INFO] [npci] [NPCI] Forwarding ReqPay (DEBIT) to rem_bank: http://rem_bank:5005/api/reqpay
2024-01-28 10:30:46 [INFO] [rem_bank] ==> Incoming POST /api/reqpay | Content-Type: application/xml | Content-Length: 1245 | Remote: 172.18.0.3
2024-01-28 10:30:46 [INFO] [rem_bank] [rem_bank] Received ReqPay DEBIT from NPCI | Payer=Chandra@paytm | Amount=500.0 | Txn.id=TXN20240128103045123
2024-01-28 10:30:46 [INFO] [rem_bank] <== Response POST /api/reqpay | Status: 202 | Content-Type: application/json | Content-Length: 28
```

## Service-Specific Logging

### NPCI (Network Switch)

**Key Logs:**
- Request validation (XSD schema validation)
- Routing decisions (which PSP/bank to forward to)
- Request/response to all connected services
- Transaction flow tracking (DEBIT → CREDIT flow)
- Pending debits tracking

**Example:**
```bash
docker compose logs -f npci | grep "ReqPay"
docker compose logs -f npci | grep "RespPay"
docker compose logs -f npci | grep "Forwarding"
```

### Remitter Bank (rem_bank)

**Key Logs:**
- Account balance checks
- Minimum transaction amount validation
- Debit operations
- Account updates
- Agent manifest processing

**Example:**
```bash
docker compose logs -f rem_bank | grep "DEBIT"
docker compose logs -f rem_bank | grep "balance"
```

### Beneficiary Bank (bene_bank)

**Key Logs:**
- Account lookup by VPA
- Credit operations
- Balance updates
- Transaction validation

**Example:**
```bash
docker compose logs -f bene_bank | grep "CREDIT"
docker compose logs -f bene_bank | grep "Payee"
```

### Payer PSP (payer_psp)

**Key Logs:**
- PIN validation
- User authentication
- Request forwarding to NPCI
- Final transaction status

**Example:**
```bash
docker compose logs -f payer_psp | grep "PIN"
docker compose logs -f payer_psp | grep "Validated"
```

### Payee PSP (payee_psp)

**Key Logs:**
- VPA validation requests
- Profile lookups
- RespValAdd generation

**Example:**
```bash
docker compose logs -f payee_psp | grep "ReqValAdd"
docker compose logs -f payee_psp | grep "VPA"
```

### Orchestrator

**Key Logs:**
- Change manifest tracking
- Agent status updates
- Dispatch operations
- (Polling endpoints filtered to reduce noise)

**Example:**
```bash
docker compose logs -f orchestrator | grep "manifest"
docker compose logs -f orchestrator | grep "status"
```

## Request/Response Logging

Every HTTP request and response is logged with:

### Incoming Request Log
```
==> Incoming <METHOD> <PATH> | Content-Type: <type> | Content-Length: <bytes> | Remote: <IP>
    Query params: {key: value, ...}  (if present)
    JSON body: {...}  (if JSON request)
```

### Outgoing Response Log
```
<== Response <METHOD> <PATH> | Status: <code> | Content-Type: <type> | Content-Length: <bytes>
```

## Debugging Workflows

### 1. Trace a Complete Transaction

```bash
# Start following all relevant services
docker compose logs -f npci rem_bank bene_bank payer_psp payee_psp

# Make a payment request
# Watch the logs flow through each service
```

### 2. Debug Failed Transactions

```bash
# Look for errors across all services
docker compose logs | grep -i "error\|failure\|exception"

# Check specific error codes
docker compose logs | grep "INSUFFICIENT_BALANCE\|INVALID_PIN\|PAYER_NOT_FOUND"

# Check specific transaction by ID
docker compose logs | grep "TXN20240128103045123"
```

### 3. Monitor API Routing

```bash
# See all incoming requests across services
docker compose logs -f | grep "==>"

# See all outgoing responses
docker compose logs -f | grep "<=="

# Track forwarding between services
docker compose logs -f | grep "Forwarding"
```

### 4. Performance Analysis

```bash
# Watch response times by comparing request/response timestamps
docker compose logs -f npci | grep -E "(==>|<==)"

# Count requests per service
docker compose logs --since 1h | grep "==>" | wc -l
```

### 5. Track Agent Communication

```bash
# Monitor manifest dispatch and processing
docker compose logs -f | grep -i "manifest"

# Track agent status updates
docker compose logs -f orchestrator | grep "status"
```

## Log File Locations

Docker stores logs in:
- **Linux**: `/var/lib/docker/containers/<container-id>/<container-id>-json.log`
- **Mac/Windows**: Through Docker Desktop's storage system

Access via Docker commands:
```bash
# Find container ID
docker ps

# Inspect log configuration
docker inspect <container-id> | grep -A 10 "LogConfig"
```

## Advanced Filtering

### Using grep for Pattern Matching

```bash
# Find all 4xx/5xx errors
docker compose logs --since 1h | grep -E "Status: [45][0-9]{2}"

# Find all XML requests
docker compose logs | grep "Content-Type: application/xml"

# Find specific VPA activity
docker compose logs | grep "Chandra@paytm"

# Find amount-related logs
docker compose logs | grep -i "amount.*[0-9]"
```

### Using jq for JSON Processing

```bash
# Extract JSON bodies from logs
docker compose logs --no-log-prefix | grep "JSON body" | sed 's/.*JSON body: //' | jq .

# Parse structured log data (if logging JSON format in future)
docker compose logs --no-log-prefix npci -n 100 | jq -R 'fromjson?'
```

## Environment Variables for Logging Control

You can adjust logging levels by modifying `.env`:

```bash
# Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOGLEVEL=DEBUG

# Flask debug mode (set to 1 for more verbose output)
FLASK_DEBUG=1
```

Then restart services:
```bash
docker compose restart <service-name>
```

## Best Practices

1. **Always use `-f` for real-time debugging**: `docker compose logs -f`
2. **Filter early, filter often**: Use grep/service names to reduce noise
3. **Use timestamps**: Add `--timestamps` if not already in log format
4. **Save important logs**: Redirect to file for analysis
   ```bash
   docker compose logs --since 10m > transaction_logs.txt
   ```
5. **Clean old logs periodically**: Docker log rotation handles this automatically
6. **Check disk space**: Monitor `/var/lib/docker` on Linux systems

## Troubleshooting

### Logs not appearing?

1. Check `PYTHONUNBUFFERED=1` is set in docker-compose.yml
2. Verify logging is configured in the application
3. Restart the service: `docker compose restart <service>`

### Too much output?

1. Use service-specific logs: `docker compose logs -f npci`
2. Increase filtering: `docker compose logs -f npci | grep "ERROR"`
3. Adjust orchestrator to filter polling endpoints (already configured)

### Log rotation not working?

Check Docker's log configuration:
```bash
docker inspect <container> | grep -A 10 LogConfig
```

### Missing werkzeug logs?

The werkzeug HTTP server logs are enabled with:
```python
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)
```

This is configured in all Flask applications.

## Additional Resources

- [Docker Compose Logs Documentation](https://docs.docker.com/compose/reference/logs/)
- [Docker Logging Drivers](https://docs.docker.com/config/containers/logging/configure/)
- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Flask Logging](https://flask.palletsprojects.com/en/2.3.x/logging/)

---

## Quick Reference

```bash
# Follow all logs
docker compose logs -f

# Follow specific service
docker compose logs -f <service>

# Last 100 lines
docker compose logs --tail=100

# Since 10 minutes ago
docker compose logs --since 10m

# Search for errors
docker compose logs | grep -i error

# Count requests
docker compose logs | grep "==>" | wc -l

# Save to file
docker compose logs > logs.txt
```



