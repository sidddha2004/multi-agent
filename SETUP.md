# SecureAI Setup Guide (Phase 1 + Phase 2)

## Phase Overview

**Phase 1**: Single distributed agent with Agent Registry and WebSocket real-time updates  
**Phase 2**: Multiple specialized workers (Research, Browser, SQL, Email) with heartbeats and result aggregation

This guide covers setting up both phases. Phase 2 builds on Phase 1 architecture.

---

## Quick Start (Phase 2 Full Setup)

### 1. Configure Environment
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-actual-key-here
```

### 2. Start All Services
```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

### 3. Access Services
- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Planner**: http://localhost:8001
- **Scheduler**: http://localhost:8002
- **WebSocket**: ws://localhost:8000/ws?token=JWT
- **Agent Registry**: http://localhost:8002/agents

## Test the Flow

### Option 1: Using the Web Interface (Recommended)
1. Open http://localhost:3000
2. Register a new account
3. Login with your credentials
4. Watch the "Live" indicator turn green (WebSocket connected)
5. Submit different types of tasks:
   - **Research**: "Research the latest developments in quantum computing"
   - **Browser**: "Go to https://example.com and extract the main heading"
   - **SQL**: "Show me all jobs in the database"
   - **Email**: "Send test email to test@example.com about system status"
6. Watch real-time status updates without refreshing!

### Option 2: Using cURL
```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test12345","name":"Test User"}'

# 2. Login
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test12345"}' \
  | jq -r '.access_token')

# 3. Submit task (returns job_id + trace_id)
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What are the benefits of microservices architecture?"}'

# Response:
# {
#   "job_id": 1,
#   "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
#   "status": "processing",
#   "message": "Task submitted successfully"
# }

# 4. Check task status (with trace_id)
curl http://localhost:8000/api/tasks/1 \
  -H "Authorization: Bearer $TOKEN"

# 5. List all tasks
curl http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN"

# 6. Check Agent Registry
curl http://localhost:8002/agents
```

## Architecture Flow

```
User Request (Frontend)
    ↓
API Gateway (JWT Auth, Rate Limit)
    ↓
Create Job with trace_id
    ↓
Planner (LLM Task Breakdown)
    ↓
Scheduler (Queries Agent Registry)
    ↓
Agent Registry (Returns: tasks.research)
    ↓
Kafka (tasks.research topic)
    ↓
Research Agent (Consumer)
    ↓
OpenAI (LLM Processing)
    ↓
PostgreSQL (Agent writes result)
    ↓
Kafka (results topic)
    ↓
WebSocket (Real-time update)
    ↓
Frontend (Live status)
```

## Services (Phase 2)

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | React dashboard with WebSockets |
| API Gateway | 8000 | Auth, routing, WebSocket server |
| Planner | 8001 | Task generation with trace_id |
| Scheduler | 8002 | Agent Registry queries |
| Result Aggregator | - | Kafka results consumer |
| Research Agent | - | Kafka consumer (LLM research) |
| Browser Agent | - | Kafka consumer (Selenium automation) |
| SQL Agent | - | Kafka consumer (Database queries) |
| Email Agent | - | Kafka consumer (Email sending) |
| Kafka | 9092 | Message broker |
| PostgreSQL | 5432 | Database with agent_registry |
| Redis | 6379 | Cache, pub/sub, heartbeats |

## Kafka Topics (Phase 2)

**Task Topics:**
- **tasks.research** - Research agent tasks
- **tasks.browser** - Browser agent tasks  
- **tasks.sql** - SQL agent tasks
- **tasks.email** - Email agent tasks

**Result Topics:**
- **results** - All agent results (consumed by Result Aggregator)

**Future Topics:**
- **tasks.retry** - Failed tasks for retry
- **tasks.dead_letter** - Permanently failed tasks

## Database Tables

### users
- User authentication data

### jobs
- Job tracking with trace_id
- Status: pending, planning, scheduled, processing, completed, failed

### tasks
- Individual task records
- Written by Research Agent (not Planner/Scheduler!)
- Includes result field

### agent_registry (Phase 1 + 2)
- Dynamic agent registration
- All Phase 2 agents registered at startup
- Example agents:
  ```json
  {
    "name": "Research Agent",
    "agent_type": "research",
    "kafka_topic": "tasks.research",
    "capabilities": ["research", "analysis"]
  },
  {
    "name": "Browser Agent",
    "agent_type": "browser",
    "kafka_topic": "tasks.browser",
    "capabilities": ["web_scraping", "selenium"]
  },
  {
    "name": "SQL Agent",
    "agent_type": "sql",
    "kafka_topic": "tasks.sql",
    "capabilities": ["database_queries", "sql_generation"]
  },
  {
    "name": "Email Agent",
    "agent_type": "email",
    "kafka_topic": "tasks.email",
    "capabilities": ["email_sending", "notification"]
  }
  ```

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose logs

# Restart specific service
docker-compose restart research-agent

# Rebuild everything
docker-compose down
docker-compose up --build
```

### Kafka connection issues
```bash
# Wait for Kafka to fully start (takes ~30 seconds)
docker-compose logs kafka

# Check topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Database connection errors
```bash
# Check PostgreSQL
docker-compose ps postgres

# Check database
docker exec -it postgres psql -U admin -d secureai

# In psql:
# \dt (list tables)
# SELECT * FROM agent_registry;
```

### WebSocket not connecting
1. Check API Gateway is running: `curl http://localhost:8000/`
2. Verify JWT token is valid
3. Check browser console for errors
4. Look for "Live" green dot in frontend

### Agent not processing tasks
```bash
# Check agent logs
docker-compose logs -f research-agent

# Verify agent is registered
curl http://localhost:8002/agents

# Check Kafka messages
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic tasks.research --from-beginning
```

## Monitoring & Debugging (Phase 2)

### Check Agent Health
```bash
# Monitor all agent heartbeats
watch -n 5 'docker exec -it redis redis-cli KEYS "heartbeat:*"'

# Check specific agent
docker exec -it redis redis-cli GET "heartbeat:research-agent"
docker exec -it redis redis-cli GET "heartbeat:browser-agent"

# Monitor agent logs
docker-compose logs -f browser-agent
docker-compose logs -f sql-agent
docker-compose logs -f email-agent
```

### Monitor Kafka Messages (Phase 2)
```bash
# Monitor all task topics
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic tasks.research --from-beginning

docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic tasks.browser --from-beginning

# Monitor results
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic results --from-beginning
```

### View Result Aggregator
```bash
# Check aggregator logs
docker-compose logs -f result-aggregator

# Monitor Redis pub/sub
docker exec -it redis redis-cli MONITOR | grep "job_updates"
```

### Phase 1 Monitoring

### Real-time WebSocket Test
```javascript
// In browser console after login:
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

ws.onmessage = (event) => {
  console.log('Update:', JSON.parse(event.data));
};
```

### Trace a Request
```bash
# 1. Submit task and save trace_id
TRACE_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# 2. Query database for this trace
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT * FROM jobs WHERE trace_id = '$TRACE_ID';"

docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT * FROM tasks WHERE trace_id = '$TRACE_ID';"
```

### View Agent Registry
```bash
curl http://localhost:8002/agents | jq
```

## Key Improvements in Phase 1

### ✅ Agent Registry
- No hardcoded topics
- Dynamic agent registration
- Easy to add new agents

### ✅ Traceability
- Every request has trace_id
- Track complete lifecycle
- Debug failed requests

### ✅ Separation of Concerns
- Research Agent writes results
- Results flow through Kafka
- Planner/Scheduler don't touch outputs

### ✅ Real-time Updates
- WebSocket connections
- No polling required
- Live status indicators

## Phase 2 Additional Features

### ✅ Multiple Specialized Workers
- Research Agent (LLM analysis)
- Browser Agent (Selenium automation)
- SQL Agent (Database queries)
- Email Agent (SMTP notifications)

### ✅ Worker Health Monitoring
- Redis-based heartbeats
- Automatic worker detection
- Health status tracking

### ✅ Result Aggregation
- Dedicated Result Aggregator service
- Centralized result collection
- Database updates via aggregator

### ✅ Enhanced Real-time Updates
- Redis pub/sub for WebSocket
- Better connection handling
- Multi-gateway scalability

## Next Steps

### For Phase 1 Users
1. **Test the WebSocket** - Submit task and watch live updates
2. **Check trace_id** - Verify full request tracking
3. **View Agent Registry** - See dynamic agent registration

### For Phase 2 Users
1. **Test all agents** - Try different agent types
2. **Monitor heartbeats** - Check worker health in Redis
3. **View result aggregation** - Check Result Aggregator logs
4. **Test WebSocket updates** - Verify real-time multi-agent updates

### Ready for Phase 3
The architecture now supports:
- ✅ Multiple specialized workers
- ✅ Dynamic agent capabilities
- ✅ Health monitoring
- ✅ Result aggregation
- ✅ Event-driven architecture

**Phase 3 will add:**
- LangGraph workflow planning
- Long-term memory with Qdrant
- Advanced workflow DAGs
- Multi-step task orchestration

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (deletes database)
docker-compose down -v

# Rebuild from scratch
docker-compose down -v
docker-compose up --build
```

## Verify Phase 1 is Working

✅ **Frontend connects** - Green "Live" dot appears
✅ **Task submitted** - Returns job_id + trace_id
✅ **Agent Registry** - Scheduler queries successfully
✅ **Kafka messages** - Tasks appear in tasks.research
✅ **Agent processes** - Research Agent consumes and processes
✅ **Results written** - Agent writes to PostgreSQL
✅ **WebSocket updates** - Real-time status in frontend
✅ **Full trace** - trace_id visible throughout flow
