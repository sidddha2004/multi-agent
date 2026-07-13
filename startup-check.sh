#!/bin/bash
# SecureAI System Startup and Health Check

echo "🚀 Starting SecureAI System..."

# Start infrastructure first
echo "📡 Starting infrastructure services..."
docker compose up -d postgres redis zookeeper kafka qdrant

# Wait for infrastructure to be healthy
echo "⏳ Waiting for infrastructure to be ready..."
sleep 15

# Check if Kafka is ready
echo "🔍 Checking Kafka..."
until docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 >/dev/null 2>&1; do
    echo "❌ Kafka not ready yet, waiting..."
    sleep 3
done
echo "✅ Kafka is ready!"

# Check if PostgreSQL is ready
echo "🔍 Checking PostgreSQL..."
until docker exec postgres pg_isready -U admin >/dev/null 2>&1; do
    echo "❌ PostgreSQL not ready yet, waiting..."
    sleep 2
done
echo "✅ PostgreSQL is ready!"

# Start core services
echo "🔧 Starting core services..."
docker compose up -d api-gateway planner scheduler

# Wait for core services
echo "⏳ Waiting for core services..."
sleep 10

# Start agents
echo "🤖 Starting agents..."
docker compose up -d research-agent browser-agent sql-agent email-agent

# Start support services
echo "🛠️ Starting support services..."
docker compose up -d result-aggregator dlq-handler memory-manager mcp-integration

# Start frontend
echo "🌐 Starting frontend..."
docker compose up -d frontend

echo ""
echo "✅ SecureAI System Started Successfully!"
echo ""
echo "📊 System Status:"
echo "   Frontend:     http://localhost:3000"
echo "   API Gateway: http://localhost:8000"
echo "   Scheduler:   http://localhost:8002"
echo ""
echo "🧪 Running System Tests..."

sleep 5

# Test 1: Check agents
echo ""
echo "🔍 Test 1: Agent Registration"
AGENTS=$(curl -s http://localhost:8002/agents | grep -c "agent_type")
if [ "$AGENTS" -gt 0 ]; then
    echo "✅ Agents registered: $AGENTS agents found"
else
    echo "❌ No agents registered"
fi

# Test 2: Check Kafka topics
echo "🔍 Test 2: Kafka Topics"
TOPICS=$(docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list | grep -c "tasks")
if [ "$TOPICS" -gt 0 ]; then
    echo "✅ Kafka topics: $TOPICS task topics found"
else
    echo "❌ No Kafka topics found"
fi

# Test 3: Check database
echo "🔍 Test 3: Database Connection"
DB_CHECK=$(docker exec postgres psql -U admin -d secureai -tAc "SELECT COUNT(*) FROM jobs" 2>/dev/null)
if [ ! -z "$DB_CHECK" ]; then
    echo "✅ Database: $DB_CHECK jobs in system"
else
    echo "❌ Database connection failed"
fi

echo ""
echo "🎉 SecureAI System Ready!"
echo "📝 Submit your first task at http://localhost:3000"
