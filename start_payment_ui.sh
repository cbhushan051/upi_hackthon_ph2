#!/bin/bash

# Quick start script for Payment UI in the project root

cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║          💳  UPI PAYMENT UI - GPay Style  💳             ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Starting Payment UI for UPI transaction simulation...

EOF

echo "🔧 Checking services..."
echo ""

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "⚠️  Docker is not running or not installed"
    echo "   Starting Payment UI in standalone mode..."
    echo ""
    cd payment_ui && ./run.sh
    exit 0
fi

# Check if services are running
if docker ps | grep -q "upi-ai"; then
    echo "✅ Docker services are running"
else
    echo "⚠️  Docker services not running"
    echo "   Starting all services..."
    docker-compose up -d
    echo ""
    echo "⏳ Waiting for services to initialize..."
    sleep 3
fi

echo ""
echo "🚀 Starting Payment UI service..."
docker-compose up -d payment_ui

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✨ Payment UI is ready!"
echo ""
echo "🌐 Access the UI at:"
echo "   📱 Payment UI:      http://localhost:9992"
echo "   📊 Orchestrator UI: http://localhost:9991"
echo ""
echo "👥 Test Users (for payment UI):"
echo "   • Chandra (Chandra@paytm) - PIN: 1234, Balance: ₹10,000"
echo "   • Gaurang     (Gaurang@paytm)     - PIN: 1111, Balance: ₹15,000"
echo "   • Hrithik    (Hrithik@paytm)    - PIN: 1234, Balance: ₹20,000"
echo ""
echo "💡 Quick Test:"
echo "   1. Open http://localhost:9992"
echo "   2. Select 'Chandra' user"
echo "   3. Choose any contact"
echo "   4. Enter amount: 500"
echo "   5. Enter PIN: 1234"
echo "   6. Click 'Pay Now' 🎉"
echo ""
echo "📝 View logs:"
echo "   docker-compose logs -f payment_ui"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

