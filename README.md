# Distributed AI Agent Platform

Enterprise-grade AI orchestration platform for distributed multi-agent execution with **LangGraph Workflow Planning, Agent Registry, Traceability, and Real-time Updates**.

## Architecture

```
User → React Frontend → API Gateway → Planner (LangGraph) → Scheduler → Agent Registry → Kafka → Agents → PostgreSQL
                                                              ↓
                                                         Results Topic
                                                              ↓
                                                          Gateway → Frontend
```

## 🚀 Current Status: Phase 3 (LangGraph Workflow Planning)

### ✅ Completed Features

**Phase 1 - Core Platform:**
- **Frontend**: React dashboard with WebSocket real-time updates
- **API Gateway**: FastAPI with JWT auth, rate limiting, WebSocket support
- **Planner**: LLM-based task generation with trace ID tracking
- **Scheduler**: Agent Registry-based task distribution (not hardcoded)
- **Research Agent**: Kafka consumer that writes results to PostgreSQL
- **Agent Registry**: Database-backed agent registration system

**Phase 2 - Distributed Execution:**
- **Multiple Specialized Workers**: Research, Browser, SQL, Email agents
- **Retry + DLQ System**: Automatic retry with exponential backoff (1min, 5min, 15min)
- **Enhanced Trace ID System**: Full request correlation (job_id + trace_id + correlation_id)
- **Capability-based Scheduling**: Plugin architecture for zero-code agent additions
- **Worker Heartbeats**: Redis-based health monitoring
- **Result Aggregator**: Collects results from all agents
- **Enhanced WebSocket**: Redis pub/sub for scalability

**Phase 3 - LangGraph Workflow Planning:**
- **LangGraph State Machine**: Intelligent workflow planning with conditional logic
- **Dynamic Workflow Types**: Sequential, parallel, conditional, and hybrid workflows
- **AI-Powered Analysis**: LLM-based workflow type determination
- **Workflow Execution Tracking**: Database-backed workflow monitoring
- **Enhanced Response**: workflow_type, workflow_confidence, workflow_execution_id

**Phase 3 - Qdrant Long-term Memory:**
- **Vector Database Integration**: Qdrant for semantic memory storage
- **OpenAI Embeddings**: text-embedding-3-small for semantic understanding
- **Memory Manager Service**: FastAPI service for memory operations
- **Agent Integration**: Easy memory storage and context retrieval
- **Semantic Search**: Find relevant memories using natural language
- **Cross-Agent Learning**: Different agents learn from shared experiences

### 🚧 In Progress

**Phase 3 Advanced Features:**
- **MCP Integration**: Model Context Protocol for external tool integration
- **Advanced Orchestration**: Multi-step DAGs with complex dependencies

## 🆕 Phase 3 Features: LangGraph Workflow Planning

### 1. **Intelligent Workflow Planning**
- **LangGraph State Machine**: AI-powered workflow analysis and generation
- **Multiple Workflow Types**: Sequential, parallel, conditional, hybrid
- **Dynamic Task Breakdown**: LLM analyzes prompt and creates optimal workflow
- **Workflow Confidence Scoring**: AI confidence in workflow selection (0.0-1.0)

### 2. **Enhanced Planning Capabilities**
- **Sequential Workflows**: Step-by-step execution for dependent tasks
- **Parallel Workflows**: Concurrent execution for independent tasks
- **Conditional Workflows**: Branching logic for adaptive workflows
- **Hybrid Workflows**: Complex multi-stage processes

### 3. **Workflow Execution Tracking**
- **Database-Backed Monitoring**: Track workflow execution in real-time
- **Execution Context**: Full workflow state and progress tracking
- **Error Handling**: Comprehensive error tracking and reporting
- **Performance Metrics**: Confidence scores and execution analysis

### 4. **AI-Powered Analysis**
- **Automatic Workflow Detection**: AI determines optimal workflow type
- **Capability Matching**: Intelligent agent capability selection
- **Complexity Assessment**: Task complexity evaluation (1-10 scale)
- **Multi-Step Planning**: Break down complex requests into manageable steps

### 1. **Agent Registry System**
- Agents are registered in database (not hardcoded)
- Dynamic topic routing (`tasks.research`, `tasks.coding`, etc.)
- Capability-based agent selection
- Easy to add new agents without code changes

### 2. **Full Traceability**
- Every request has `job_id` and `trace_id`
- Track entire request lifecycle from submission to completion
- Debug failed requests with complete trace

### 3. **Real-time Updates**
- WebSocket connections for live status updates
- No polling required
- Automatic reconnection on disconnect

### 4. **Separation of Concerns**
- Research Agent writes results to PostgreSQL
- Results Topic → Gateway → Frontend flow
- Planner/Scheduler don't handle worker outputs

## Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **Frontend**: React, WebSockets
- **Messaging**: Apache Kafka (topic-specific: `tasks.research`, `results`)
- **Database**: PostgreSQL (users, jobs, tasks, agent_registry)
- **Cache**: Redis
- **AI**: OpenAI GPT-4
- **Container**: Docker, Docker Compose

## Database Schema

### users
```sql
- id, email, password_hash, name, created_at
```

### jobs
```sql
- id, user_id, trace_id (unique), prompt, status, created_at, updated_at
```

### tasks
```sql
- id, job_id, trace_id, description, status, agent_type, result, created_at, updated_at
```

### agent_registry (NEW!)
```sql
- id, name, agent_type, capabilities (JSON), kafka_topic, is_active, version, created_at, updated_at
```

## Kafka Topics

- **tasks.research** - Tasks for research agents
- **tasks.coding** - Tasks for coding agents (Phase 2)
- **tasks.browser** - Tasks for browser agents (Phase 2)
- **results** - All agent results

## Setup

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 2. Start All Services
```bash
docker-compose up --build
```

### 3. Access Services
- **Frontend**: http://localhost:3000
- **API Gateway**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws?token=YOUR_JWT_TOKEN

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and get JWT token
- `WebSocket /ws?token=JWT` - Real-time updates

### Tasks
- `POST /api/tasks` - Submit task (returns job_id + trace_id)
- `GET /api/tasks` - List user's tasks
- `GET /api/tasks/{job_id}` - Get task details with results

### Internal Services
- `POST /plan` - Planner: Generate task breakdown
- `POST /schedule` - Scheduler: Route tasks to agents
- `GET /agents` - List registered agents

## Request Flow with Traceability

1. **User** submits prompt → Frontend
2. **API Gateway** validates JWT + rate limit
3. **Job** created with `trace_id`
4. **Planner** breaks down into tasks (propagates `trace_id`)
5. **Scheduler** queries Agent Registry for topics
6. **Scheduler** publishes to `tasks.research` (with `trace_id`)
7. **Research Agent** consumes from Kafka
8. **Agent** processes with OpenAI
9. **Agent** writes result to PostgreSQL
10. **Agent** publishes to `results` topic
11. **Gateway** receives result via WebSocket
12. **Frontend** displays real-time update

## Example Request/Response

### Submit Task
```json
POST /api/tasks
{
  "prompt": "What are the benefits of microservices?"
}

Response:
{
  "job_id": 123,
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "message": "Task submitted successfully"
}
```

### WebSocket Update
```json
{
  "type": "task_update",
  "job_id": 123,
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed"
}
```

## Agent Registry Example

### Default Research Agent (auto-registered)
```json
{
  "id": 1,
  "name": "Research Agent",
  "agent_type": "research",
  "capabilities": ["research", "analysis", "information_gathering"],
  "kafka_topic": "tasks.research",
  "is_active": true,
  "version": "1.0.0"
}
```

### Add New Agent (Phase 2)
```sql
INSERT INTO agent_registry (name, agent_type, capabilities, kafka_topic)
VALUES ('Coding Agent', 'coding', '["code_generation", "debugging"]', 'tasks.coding');
```

## Monitoring & Debugging

### View Agent Registry
```bash
curl http://localhost:8002/agents
```

### Check Kafka Topics
```bash
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Monitor Research Agent
```bash
docker-compose logs -f research-agent
```

## Next Phases

- **Phase 2**: Add specialized workers (Coding, Browser, SQL, Email)
- **Phase 3**: Dynamic agent capabilities with LangGraph
- **Phase 4**: Kubernetes deployment with monitoring
- **Phase 5**: Enterprise features (Permit.io, workflows, multi-tenant)

## Why This Architecture?

✅ **No Hardcoding** - Agent Registry replaces hardcoded topics
✅ **Full Traceability** - trace_id tracks entire request lifecycle
✅ **Separation of Concerns** - Agents write results, not Planner/Scheduler
✅ **Real-time Updates** - WebSockets instead of polling
✅ **Future-Proof** - Easy to add agents without refactoring

## License

MIT
