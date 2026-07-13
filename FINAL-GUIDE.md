# 🔧 SecureAI Final Setup & Testing Guide

## 🎯 System Status Summary

### ✅ Components Working
- **PostgreSQL**: Database running and accepting connections
- **Redis**: Cache and heartbeat system operational
- **Kafka**: Message broker with all topics created
- **Qdrant**: Vector database for semantic memory
- **API Gateway**: Authentication and job submission working
- **Planner**: Workflow planning using rule-based logic
- **Scheduler**: Task routing to agents (with registration fixes)
- **Research Agent**: Registered and consuming from Kafka
- **Frontend**: React application running on port 3000

### 🔧 Recently Fixed Issues
1. **LangGraph Dependencies Removed** - Simplified planner to rule-based workflows
2. **WebSocket Double-Accept Fixed** - Removed duplicate accept() call
3. **Agent Registration System** - Added proper POST body registration
4. **Missing Dependencies Added** - httpx, email-validator, psycopg2-binary
5. **Kafka/Zookeeper Volumes** - Added persistent storage
6. **Database Health Checks** - Ensured proper startup order

## 🚀 Quick Start Instructions

### Step 1: Rebuild Services with Latest Fixes
```bash
# Build all modified services
docker compose build scheduler research-agent api-gateway planner

# Restart everything
docker compose down
docker compose up -d
```

### Step 2: Use Automated Startup Script (Windows)
```powershell
# Run the automated startup and health check
.\startup-check.ps1
```

Or manually:
```bash
# Start in correct order
docker compose up -d postgres redis zookeeper kafka qdrant
# Wait 15 seconds
docker compose up -d api-gateway planner scheduler
# Wait 10 seconds  
docker compose up -d research-agent browser-agent sql-agent email-agent
docker compose up -d result-aggregator dlq-handler memory-manager mcp-integration
docker compose up -d frontend
```

## 🧪 System Testing Checklist

### Test 1: Infrastructure Health
```bash
# Check all containers running
docker compose ps

# Expected: All containers "Up X minutes" with no "Exited"
```

### Test 2: Agent Registration
```bash
curl http://localhost:8002/agents

# Expected: JSON with 4 agents (Research, Browser, SQL, Email)
# Should show capabilities and kafka topics
```

### Test 3: Kafka Topics
```bash
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Expected: tasks.research, tasks.browser, tasks.sql, tasks.email, results, tasks.retry, tasks.dead_letter
```

### Test 4: Database Connection
```bash
docker exec postgres psql -U admin -d secureai -c "SELECT COUNT(*) FROM jobs;"

# Expected: Number of jobs (0 or more)
```

### Test 5: Frontend Access
```bash
# Visit in browser: http://localhost:3000
# Expected: SecureAI frontend loads with job submission form
```

## 🔄 Complete Task Flow Test

### 1. Login to Get Token
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 2. Submit a Test Task
```bash
# Replace YOUR_TOKEN from login response
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"prompt":"What is artificial intelligence?"}'
```

### 3. Monitor Task Progress
```bash
# Watch task status change
curl http://localhost:8000/api/jobs \
  -H "Authorization: Bearer YOUR_TOKEN"

# Check Kafka messages
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic tasks.research --from-beginning --max-messages 1

# Watch agent logs
docker compose logs -f research-agent
```

## 🛠️ Troubleshooting Guide

### Issue: Tasks Stuck in "scheduled"
**Symptoms**: Jobs created but status never changes
**Solution**:
```bash
# Check if agents are registered
curl http://localhost:8002/agents

# Check scheduler logs
docker compose logs scheduler | grep -i "error\|kafka"

# Restart agents
docker compose restart research-agent browser-agent sql-agent email-agent
```

### Issue: WebSocket Connection Failures
**Symptoms**: Frontend shows WebSocket errors, but jobs still process
**Solution**: WebSocket errors are cosmetic - core functionality works. The backend accepts connections properly.

### Issue: Kafka Connection Refused
**Symptoms**: Scheduler can't connect to Kafka
**Solution**:
```bash
# Ensure startup order
docker compose down
docker compose up -d postgres redis zookeeper kafka
# Wait 20 seconds
docker compose up -d scheduler
```

### Issue: Agent Registration 422 Errors
**Symptoms**: Agents fail to register with scheduler
**Solution**: Fixed in latest code - rebuild scheduler and agents
```bash
docker compose build scheduler research-agent
docker compose up -d scheduler research-agent
```

## 📊 Current Architecture Flow

```
User → Frontend (React)
     ↓
API Gateway (FastAPI - Port 8000)
     ↓
Planner (Rule-based Workflow) → Creates Tasks
     ↓
Scheduler (Agent Registry + Kafka Producer) → Routes to Topics
     ↓
Kafka (Message Broker)
     ↓
Agents (Research/Browser/SQL/Email) → Process Tasks
     ↓
Kafka Results Topic
     ↓
Result Aggregator → Updates Database + Redis
     ↓
WebSocket (Real-time Updates) → Frontend
```

## 🔑 Required API Keys

Set these in your `.env` file:
```bash
OPENAI_API_KEY=sk-proj-xxxxx  # Required for all agents
```

Optional:
```bash
QDRANT_API_KEY=xxxxx           # For managed Qdrant
MCP_API_KEY=xxxxx              # For MCP integration
SMTP_HOST=smtp.gmail.com       # For email agent
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## 📝 Services and Ports

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 3000 | React UI |
| API Gateway | 8000 | Authentication & Job API |
| Planner | 8001 | Workflow Planning |
| Scheduler | 8002 | Agent Registry & Task Routing |
| Memory Manager | 8005 | Qdrant Memory Interface |
| MCP Integration | 8006 | External Tool Access |
| PostgreSQL | 5432 | Main Database |
| Redis | 6379 | Cache & PubSub |
| Kafka | 9092-9093 | Message Broker |
| Qdrant | 6333-6334 | Vector Database |

## 🎉 Success Criteria

✅ **Infrastructure**: All containers running without errors
✅ **Agents**: 4 agents registered with capabilities
✅ **Kafka**: All 7 topics created
✅ **Database**: Jobs and tasks tables accessible
✅ **API**: Job submission and status queries working
✅ **Flow**: End-to-end task processing functional

## 🚨 Known Limitations

1. **WebSocket Reconnections**: Frontend may show connection errors, but backend works correctly
2. **Startup Timing**: Services must start in correct order (use startup script)
3. **Task Processing**: First few tasks may take longer due to cold starts
4. **Memory System**: Qdrant collection created on first use

## 📞 Support & Testing

For any issues:
1. Check logs: `docker compose logs [service-name]`
2. Verify containers: `docker compose ps`
3. Test individual components using the checklist above
4. Ensure startup order using provided scripts

The system is designed to be resilient - individual service failures won't crash the entire system. Agents will reconnect automatically if Kafka restarts, and the scheduler will retry failed tasks.
