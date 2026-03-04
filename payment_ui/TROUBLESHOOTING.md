# Payment UI - Troubleshooting Guide

## Common Issues and Solutions

### 1. Permission Denied Error (`/dev/shm/`)

**Error**:
```
PermissionError: [Errno 13] Permission denied: '/dev/shm/pym-xxxxx'
```

**Cause**: Flask's debug mode requires write access to shared memory (`/dev/shm/`), which may not be available in some environments.

**Solution**: Debug mode is now disabled by default. The app will run without issues.

If you need debug mode and have proper permissions:
```bash
export FLASK_DEBUG=true
python app.py
```

For Docker:
```bash
docker-compose run --rm -e FLASK_DEBUG=true payment_ui
```

---

### 2. Port Already in Use

**Error**:
```
OSError: [Errno 98] Address already in use
```

**Solution**:
```bash
# Change the port
export PAYMENT_UI_PORT=8001
python app.py

# Or find and kill the process
lsof -ti:9992 | xargs kill -9
```

---

### 3. Connection Refused to Payer PSP

**Error**:
```
Connection failed. Make sure services are running
```

**Solution**:
```bash
# Make sure Docker services are running
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs payer_psp

# Test connectivity
curl http://localhost:5060/health
```

---

### 4. Invalid PIN Error

**Error**:
```
INVALID_PIN - Incorrect UPI PIN
```

**Solution**: Use the correct PINs for test users:
- `Chandra@paytm`: **1234**
- `Gaurang@paytm`: **1111**
- `Hrithik@paytm`: **1234**

---

### 5. Amount Below Minimum

**Error**:
```
INVALID_AMOUNT - Minimum transaction amount is INR 150.00
```

**Solution**: Enter an amount of ₹150 or more.

---

### 6. Module Not Found

**Error**:
```
ModuleNotFoundError: No module named 'flask'
```

**Solution**:
```bash
# Install dependencies
pip install -r requirements.txt

# Or use the run script which does this automatically
./run.sh
```

---

### 7. Docker Build Fails

**Error**:
```
ERROR: failed to solve: process "/bin/sh -c pip install..."
```

**Solution**:
```bash
# Clean Docker cache
docker system prune -a

# Rebuild
docker-compose build --no-cache payment_ui
docker-compose up -d payment_ui
```

---

### 8. Transaction Timeout

**Error**:
```
Transaction timeout. Please try again.
```

**Solution**:
```bash
# Check all services are responsive
docker-compose ps

# Restart slow services
docker-compose restart payer_psp npci

# Increase timeout if needed (edit app.py)
timeout=30  # seconds
```

---

### 9. Browser Won't Load UI

**Issue**: Opening http://localhost:9992 shows nothing

**Solution**:
```bash
# Check if service is running
curl http://localhost:9992/health

# Check logs
docker-compose logs payment_ui

# Try different browser
# Clear browser cache
```

---

### 10. Transaction History Not Saving

**Issue**: History disappears on refresh

**Solution**: Transaction history uses localStorage. Check:
- Browser privacy settings
- Incognito/private mode (localStorage disabled)
- Browser storage quota

---

## Debug Mode

### When to Use Debug Mode

✅ **Use debug mode when**:
- Developing new features
- Investigating bugs
- Need detailed error traces
- Have proper system permissions

❌ **Don't use debug mode when**:
- Running in restricted environments
- No access to `/dev/shm/`
- Production/demo environments
- Don't need auto-reload

### Enable Debug Mode

```bash
# Method 1: Environment variable
export FLASK_DEBUG=true
python app.py

# Method 2: Edit app.py directly
debug_mode = True  # Change this line
```

---

## Checking Service Health

### Quick Health Check

```bash
# Payment UI
curl http://localhost:9992/health

# Expected: {"status": "ok"}
```

### Detailed Service Check

```bash
# Check all services
for port in 9992 5060 5050 5090 5080; do
    echo "Port $port:"
    curl -s http://localhost:$port/health || echo "  ❌ Not responding"
done
```

---

## Logs and Debugging

### View Real-time Logs

```bash
# Payment UI logs
docker-compose logs -f payment_ui

# All services
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100 payment_ui
```

### Python Debugging

```python
# Add to app.py for debugging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export FLASK_ENV=development
```

---

## Reset Everything

### Complete Reset

```bash
# Stop all services
docker-compose down

# Remove volumes (clears databases)
docker-compose down -v

# Clean Docker system
docker system prune -a

# Remove virtual environment
rm -rf payment_ui/venv

# Rebuild and start
docker-compose up -d --build
```

---

## Getting Help

### Gather Information

When reporting issues, include:

1. **Error message**: Full error text
2. **Service logs**: `docker-compose logs`
3. **Service status**: `docker-compose ps`
4. **Environment**: OS, Docker version
5. **Steps to reproduce**: What you did

### Example Bug Report

```
**Issue**: Payment fails with connection error

**Environment**:
- OS: Ubuntu 20.04
- Docker: 20.10.12
- Browser: Chrome 96

**Steps**:
1. Started services: docker-compose up -d
2. Opened http://localhost:9992
3. Selected user: Chandra
4. Entered amount: 500
5. Entered PIN: 1234
6. Clicked Pay Now

**Error**:
Connection failed. Make sure services are running

**Logs**:
[paste relevant logs here]

**Service Status**:
[paste docker-compose ps output]
```

---

## Performance Issues

### Slow Transactions

**Causes**:
- Services not fully initialized
- Resource constraints
- Network issues

**Solutions**:
```bash
# Wait for services to fully start
sleep 5

# Check resource usage
docker stats

# Increase Docker resources (Docker Desktop)
# Settings → Resources → Memory/CPU
```

---

## Security Notes

⚠️ **Development Only**

This is a simulation environment:
- Debug mode exposes stack traces
- PINs are in plaintext
- No encryption
- Not for production use

---

## Still Having Issues?

1. Check the main README: `payment_ui/README.md`
2. Check project docs: `PROJECT_OVERVIEW.md`
3. Review Docker Compose: `docker-compose.yml`
4. Check service logs carefully
5. Try the interactive test script: `python scripts/interactive_test.py`

---

**Most issues are solved by**: `docker-compose down && docker-compose up -d` 🎯

