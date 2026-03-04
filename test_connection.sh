#!/bin/bash
echo "=== Orchestrator Connection Test ==="
echo ""
echo "1. Testing server status..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "   ✓ Server is running"
    echo "   Response: $(curl -s http://localhost:8080/health)"
else
    echo "   ✗ Server is NOT responding"
    exit 1
fi

echo ""
echo "2. Testing root page..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/)
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✓ Root page accessible (HTTP $HTTP_CODE)"
else
    echo "   ✗ Root page failed (HTTP $HTTP_CODE)"
fi

echo ""
echo "3. Testing static files..."
CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/static/style.css)
JS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/static/app.js)
if [ "$CSS_CODE" = "200" ] && [ "$JS_CODE" = "200" ]; then
    echo "   ✓ Static files accessible"
else
    echo "   ✗ Static files failed (CSS: $CSS_CODE, JS: $JS_CODE)"
fi

echo ""
echo "4. Port status:"
netstat -tlnp 2>/dev/null | grep 8080 || ss -tlnp 2>/dev/null | grep 8080

echo ""
echo "=== ACCESS URLS ==="
echo "Try these URLs in your browser:"
echo "  - http://localhost:8080"
echo "  - http://127.0.0.1:8080"
echo "  - http://192.168.1.121:8080"
echo ""
echo "If you still get ERR_CONNECTION_REFUSED:"
echo "  1. Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)"
echo "  2. Try incognito/private mode"
echo "  3. Check browser console (F12) for errors"
echo "  4. Try a different browser"


