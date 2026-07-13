# SecureAI System Startup Script (Windows PowerShell)

Write-Host "🚀 Starting SecureAI System..." -ForegroundColor Green

# Start infrastructure first
Write-Host "📡 Starting infrastructure services..." -ForegroundColor Yellow
docker compose up -d postgres redis zookeeper kafka qdrant

# Wait for infrastructure
Write-Host "⏳ Waiting for infrastructure (15 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Check Kafka
Write-Host "🔍 Checking Kafka..." -ForegroundColor Yellow
$kafkaReady = $false
$maxAttempts = 10
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>$null | Out-Null
        $kafkaReady = $true
        break
    } catch {
        Write-Host "❌ Kafka not ready (attempt $i/$maxAttempts)..." -ForegroundColor Red
        Start-Sleep -Seconds 3
    }
}

if ($kafkaReady) {
    Write-Host "✅ Kafka is ready!" -ForegroundColor Green
} else {
    Write-Host "❌ Kafka failed to start" -ForegroundColor Red
    exit 1
}

# Check PostgreSQL
Write-Host "🔍 Checking PostgreSQL..." -ForegroundColor Yellow
$pgReady = $false
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        docker exec postgres pg_isready -U admin 2>$null | Out-Null
        $pgReady = $true
        break
    } catch {
        Write-Host "❌ PostgreSQL not ready (attempt $i/$maxAttempts)..." -ForegroundColor Red
        Start-Sleep -Seconds 2
    }
}

if ($pgReady) {
    Write-Host "✅ PostgreSQL is ready!" -ForegroundColor Green
} else {
    Write-Host "❌ PostgreSQL failed to start" -ForegroundColor Red
    exit 1
}

# Start core services
Write-Host "🔧 Starting core services..." -ForegroundColor Yellow
docker compose up -d api-gateway planner scheduler

# Wait for core services
Write-Host "⏳ Waiting for core services (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Start agents
Write-Host "🤖 Starting agents..." -ForegroundColor Yellow
docker compose up -d research-agent browser-agent sql-agent email-agent

# Start support services
Write-Host "🛠️ Starting support services..." -ForegroundColor Yellow
docker compose up -d result-aggregator dlq-handler memory-manager mcp-integration

# Start frontend
Write-Host "🌐 Starting frontend..." -ForegroundColor Yellow
docker compose up -d frontend

Write-Host ""
Write-Host "✅ SecureAI System Started Successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 System Status:" -ForegroundColor Cyan
Write-Host "   Frontend:     http://localhost:3000"
Write-Host "   API Gateway: http://localhost:8000"
Write-Host "   Scheduler:   http://localhost:8002"
Write-Host ""
Write-Host "🧪 Running System Tests..." -ForegroundColor Yellow

Start-Sleep -Seconds 5

# Test 1: Check agents
Write-Host ""
Write-Host "🔍 Test 1: Agent Registration" -ForegroundColor Yellow
try {
    $agents = Invoke-RestMethod -Uri "http://localhost:8002/agents" -Method Get
    $agentCount = $agents.agents.Count
    Write-Host "✅ Agents registered: $agentCount agents found" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to check agents" -ForegroundColor Red
}

# Test 2: Check Kafka topics
Write-Host "🔍 Test 2: Kafka Topics" -ForegroundColor Yellow
try {
    $topics = docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list 2>$null
    $taskTopics = $topics | Select-String "tasks\."
    $topicCount = ($taskTopics | Measure-Object).Count
    Write-Host "✅ Kafka topics: $topicCount task topics found" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to check Kafka topics" -ForegroundColor Red
}

# Test 3: Check database
Write-Host "🔍 Test 3: Database Connection" -ForegroundColor Yellow
try {
    $jobCount = docker exec postgres psql -U admin -d secureai -tAc "SELECT COUNT(*) FROM jobs" 2>$null
    if ($jobCount) {
        Write-Host "✅ Database: $jobCount jobs in system" -ForegroundColor Green
    } else {
        Write-Host "✅ Database connected, no jobs yet" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Database connection failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "🎉 SecureAI System Ready!" -ForegroundColor Green
Write-Host "📝 Submit your first task at http://localhost:3000" -ForegroundColor Cyan
