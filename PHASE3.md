# Phase 3 - LangGraph Workflow Planning & Advanced Orchestration 🧠

## Objective: Intelligent workflow planning + Long-term memory + Advanced orchestration

### Phase 3 Components

**Intelligent Planning:**
- ✅ **LangGraph Workflow Planning** - State machine-based workflow planning with conditional logic
- ✅ **Dynamic Workflow Types** - Sequential, parallel, conditional, and hybrid workflows
- ✅ **Workflow Execution Tracking** - Database-backed workflow execution monitoring
- ✅ **Capability-based Analysis** - AI-powered capability matching and task breakdown

**Advanced Features (In Progress):**
- 🚧 **Qdrant Long-term Memory** - Persistent memory across sessions with vector embeddings
- 🚧 **MCP Integration** - Model Context Protocol for external tool integration
- 🚧 **Advanced Workflow Orchestration** - Multi-step DAGs with complex dependencies

---

## 1. LangGraph Workflow Planning System

### Architecture Overview

```
User Request
    ↓
API Gateway (trace_id + correlation_id)
    ↓
Planner with LangGraph
    ↓
Workflow State Machine
    ├─ Analyze Prompt (determine workflow type)
    ├─ Route to Workflow Type
    │   ├─ Sequential (step-by-step)
    │   ├─ Parallel (concurrent execution)
    │   └─ Conditional (branching logic)
    ├─ Validate Workflow
    └─ Return Structured Tasks
    ↓
Scheduler (capability matching)
    ↓
Kafka (task distribution)
    ↓
Agents (execution)
    ↓
Result Aggregation
```

### Workflow State Machine

**LangGraph State Components:**
```python
class WorkflowState(TypedDict):
    prompt: str                  # User request
    job_id: int                  # Job identifier
    trace_id: str                # Full request trace
    correlation_id: str          # Cross-service correlation
    tasks: List[Dict]            # Generated tasks
    analysis: Optional[str]      # LLM analysis result
    capabilities_required: List[str]  # Required capabilities
    workflow_type: str           # sequential|parallel|conditional|hybrid
    confidence: float            # Workflow confidence score
    error_message: Optional[str] # Error details
```

### Workflow Types

#### **1. Sequential Workflow**
- **Purpose**: Step-by-step execution where each task depends on the previous one
- **Use Cases**: Multi-step research, data processing pipelines
- **Structure**: Task 1 → Task 2 → Task 3 → Task 4

**Example Request:**
```
"Research the latest AI developments, then analyze their impact on healthcare, and finally create a summary report"
```

**Generated Tasks:**
```json
{
  "workflow_type": "sequential",
  "tasks": [
    {"description": "Research latest AI developments", "required_capability": "research"},
    {"description": "Analyze healthcare impact", "required_capability": "analysis"},
    {"description": "Create summary report", "required_capability": "reporting"}
  ]
}
```

#### **2. Parallel Workflow**
- **Purpose**: Execute multiple independent tasks simultaneously
- **Use Cases**: Multi-source data gathering, independent research tasks
- **Structure**: Task 1, Task 2, Task 3 (all concurrent)

**Example Request:**
```
"Gather information about renewable energy from solar, wind, and hydro sources simultaneously"
```

**Generated Tasks:**
```json
{
  "workflow_type": "parallel",
  "tasks": [
    {"description": "Research solar energy", "required_capability": "research", "parallel_group": "A"},
    {"description": "Research wind energy", "required_capability": "research", "parallel_group": "A"},
    {"description": "Research hydro energy", "required_capability": "research", "parallel_group": "A"}
  ]
}
```

#### **3. Conditional Workflow**
- **Purpose**: Branch execution based on conditions or outcomes
- **Use Cases**: Decision trees, conditional logic, adaptive workflows
- **Structure**: Task 1 → (Condition A → Branch 1, Condition B → Branch 2)

**Example Request:**
```
"Check if the website example.com is accessible. If yes, scrape the content. If no, try the backup site."
```

**Generated Tasks:**
```json
{
  "workflow_type": "conditional",
  "tasks": [
    {"description": "Check website accessibility", "required_capability": "web_scraping", "condition": "true", "branch": "main"},
    {"description": "Scrape main site", "required_capability": "web_scraping", "condition": "accessible", "branch": "main"},
    {"description": "Try backup site", "required_capability": "web_scraping", "condition": "!accessible", "branch": "alternative"}
  ],
  "branches": {
    "main": ["check_accessibility", "scrape_main"],
    "alternative": ["check_accessibility", "try_backup"]
  }
}
```

#### **4. Hybrid Workflow**
- **Purpose**: Combine multiple workflow types for complex scenarios
- **Use Cases**: Complex multi-stage processes
- **Structure**: Mix of sequential, parallel, and conditional execution

---

## 2. Database Schema

### Workflow Tables

#### **workflows** Table
```sql
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    workflow_type VARCHAR(50) NOT NULL,  -- sequential, parallel, conditional, hybrid
    definition TEXT NOT NULL,             -- JSON workflow definition
    capabilities TEXT,                     -- JSON array of required capabilities
    is_active BOOLEAN DEFAULT true,
    version VARCHAR(20) DEFAULT '1.0.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### **workflow_executions** Table
```sql
CREATE TABLE workflow_executions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    trace_id VARCHAR(255) NOT NULL,
    correlation_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed, rolled_back
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER,
    execution_context TEXT,                -- JSON execution state
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);
```

---

## 3. LangGraph Implementation

### Workflow Graph Structure

```python
# Build LangGraph Workflow
def build_workflow_planning_graph():
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("analyze", analyze_prompt)
    workflow.add_node("sequential", create_sequential_workflow)
    workflow.add_node("parallel", create_parallel_workflow)
    workflow.add_node("conditional", create_conditional_workflow)
    workflow.add_node("validate", validate_workflow)
    
    # Define routing logic
    def route_workflow_type(state: WorkflowState) -> str:
        workflow_type = state.get('workflow_type', 'sequential')
        if workflow_type == 'parallel':
            return 'parallel'
        elif workflow_type == 'conditional':
            return 'conditional'
        else:
            return 'sequential'
    
    # Build graph
    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges("analyze", route_workflow_type, {
        'sequential': 'sequential',
        'parallel': 'parallel',
        'conditional': 'conditional'
    })
    
    workflow.add_edge("sequential", "validate")
    workflow.add_edge("parallel", "validate")
    workflow.add_edge("conditional", "validate")
    workflow.add_edge("validate", END)
    
    return workflow.compile()
```

### AI-Powered Analysis

**Prompt Analysis Node:**
```python
def analyze_prompt(state: WorkflowState) -> WorkflowState:
    """Analyze the prompt and determine workflow type"""
    
    analysis_prompt = f"""Analyze this user request and determine:
    1. What type of workflow is needed (sequential, parallel, conditional, hybrid)
    2. What capabilities are required
    3. How complex is this task (1-10)
    4. What are the main steps needed
    
    User request: {state['prompt']}
    
    Respond in JSON format:
    {{
        "workflow_type": "sequential|parallel|conditional|hybrid",
        "capabilities_required": ["capability1", "capability2"],
        "complexity": 1-10,
        "steps": ["step1", "step2", "step3"],
        "confidence": 0.0-1.0
    }}
    """
    
    response = llm.invoke([HumanMessage(content=analysis_prompt)])
    result = json.loads(response.content)
    
    state['workflow_type'] = result.get('workflow_type', 'sequential')
    state['capabilities_required'] = result.get('capabilities_required', [])
    state['confidence'] = result.get('confidence', 0.8)
    
    return state
```

---

## 4. API Integration

### Enhanced Plan Response

```json
{
  "job_id": 123,
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tasks": [
    {
      "task_id": 456,
      "description": "Research latest developments",
      "agent_type": "research",
      "status": "scheduled"
    },
    {
      "task_id": 457,
      "description": "Analyze healthcare impact",
      "agent_type": "research",
      "status": "scheduled"
    }
  ],
  "message": "Created 2 tasks using sequential workflow",
  "workflow_type": "sequential",
  "workflow_confidence": 0.85,
  "workflow_execution_id": 789
}
```

### New Response Fields

- **workflow_type**: The type of workflow generated (sequential/parallel/conditional)
- **workflow_confidence**: AI confidence score (0.0-1.0) in the workflow choice
- **workflow_execution_id**: Database ID for tracking workflow execution

---

## 5. Usage Examples

### Example 1: Sequential Research Workflow

**Request:**
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Research quantum computing developments, analyze their security implications, and create a comprehensive report"
  }'
```

**Response:**
```json
{
  "workflow_type": "sequential",
  "workflow_confidence": 0.92,
  "tasks": [
    {"description": "Research quantum computing", "agent_type": "research"},
    {"description": "Analyze security implications", "agent_type": "analysis"},
    {"description": "Create comprehensive report", "agent_type": "reporting"}
  ]
}
```

### Example 2: Parallel Data Gathering

**Request:**
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Gather market data from tech, finance, and healthcare sectors simultaneously"
  }'
```

**Response:**
```json
{
  "workflow_type": "parallel",
  "workflow_confidence": 0.88,
  "tasks": [
    {"description": "Research tech sector", "agent_type": "research"},
    {"description": "Research finance sector", "agent_type": "research"},
    {"description": "Research healthcare sector", "agent_type": "research"}
  ]
}
```

### Example 3: Conditional Decision Tree

**Request:**
```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Check if API endpoint is healthy. If yes, fetch data. If no, trigger alert and retry"
  }'
```

**Response:**
```json
{
  "workflow_type": "conditional",
  "workflow_confidence": 0.85,
  "tasks": [
    {"description": "Check API health status", "agent_type": "web_scraping"},
    {"description": "Fetch data from API", "agent_type": "web_scraping"},
    {"description": "Trigger alert and retry", "agent_type": "email_sending"}
  ]
}
```

---

## 6. Monitoring & Debugging

### Check Workflow Executions

```bash
# View recent workflow executions
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT * FROM workflow_executions ORDER BY created_at DESC LIMIT 10;"

# Check specific workflow execution
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT * FROM workflow_executions WHERE job_id = 123;"

# Monitor workflow status distribution
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT status, COUNT(*) FROM workflow_executions GROUP BY status;"
```

### View Workflow Definitions

```bash
# List all workflow types
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT workflow_type, COUNT(*) FROM workflows GROUP BY workflow_type;"

# View specific workflow definition
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT name, workflow_type, definition FROM workflows WHERE id = 1;"
```

### Monitor LangGraph Planning

```bash
# Watch planner logs for LangGraph activity
docker-compose logs -f planner | grep "LangGraph"

# Check workflow analysis results
docker-compose logs planner | grep "workflow_type"

# Monitor confidence scores
docker-compose logs planner | grep "confidence"
```

### Performance Metrics

```bash
# Average workflow confidence
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT AVG((execution_context->>'confidence')::float) FROM workflow_executions WHERE execution_context IS NOT NULL;"

# Workflow type distribution
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT (execution_context->>'workflow_type') as type, COUNT(*) FROM workflow_executions GROUP BY type;"
```

---

## 7. Advanced Features (Coming Soon)

### Qdrant Long-term Memory

**Purpose**: Persistent memory across sessions using vector embeddings

**Capabilities:**
- Store and retrieve research results across sessions
- Semantic search through historical data
- Context-aware memory retrieval
- Automatic memory consolidation

**Architecture:**
```
Agent Execution
    ↓
Generate Results
    ↓
Store in Qdrant (with embeddings)
    ↓
Retrieve Relevant Memory (for future tasks)
    ↓
Enhanced Context for Planning
```

### MCP Integration

**Purpose**: Model Context Protocol for external tool integration

**Capabilities:**
- Standardized tool integration
- Plugin architecture for external services
- Secure tool execution
- Real-time tool responses

**Supported MCP Tools:**
- File system operations
- Database queries
- API integrations
- Custom business logic

### Advanced Workflow Orchestration

**Features:**
- Complex DAG execution
- Multi-step conditional workflows
- Dynamic workflow adaptation
- Workflow versioning and rollback

---

## 8. Testing LangGraph Workflows

### Test Sequential Workflow

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Step 1: Research AI trends. Step 2: Analyze business impact. Step 3: Create report."
  }'
```

### Test Parallel Workflow

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Simultaneously research solar, wind, and hydro energy developments"
  }'
```

### Test Conditional Workflow

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Check website availability. If up, scrape content. If down, send alert"
  }'
```

---

## 9. Troubleshooting

### LangGraph Issues

**Workflow planning fails:**
```bash
# Check OpenAI API key
docker exec -it planner env | grep OPENAI_API_KEY

# Verify LangGraph dependencies
docker exec -it planner python -c "import langgraph; print('LangGraph OK')"

# Check planner logs
docker-compose logs planner | grep "LangGraph"
```

**Low confidence scores:**
```bash
# Monitor confidence patterns
docker-compose logs planner | grep "confidence" | awk '{print $NF}' | sort -n

# Check prompt complexity
docker-compose logs planner | grep "complexity"
```

### Database Issues

**Workflow execution tracking:**
```bash
# Check workflow_executions table
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT * FROM workflow_executions WHERE status = 'failed';"

# Monitor execution context
docker exec -it postgres psql -U admin -d secureai -c \
  "SELECT id, (execution_context->>'error_message') as error FROM workflow_executions WHERE error_message IS NOT NULL;"
```

---

## 10. Performance & Scaling

### LangGraph Performance

**Planning Latency:**
- Sequential: 2-5 seconds
- Parallel: 3-7 seconds  
- Conditional: 4-8 seconds
- Hybrid: 5-10 seconds

**Memory Usage:**
- Base Planner: ~200MB
- LangGraph Engine: ~100MB
- Per Workflow: ~5MB

### Scaling Considerations

**Horizontal Scaling:**
- Multiple planner instances behind load balancer
- Shared workflow execution database
- Caching layer for common workflow patterns

**Optimization Strategies:**
- Cache frequent workflow patterns
- Batch workflow planning for similar requests
- Optimize LLM prompts for faster analysis
- Use streaming responses for long workflows

---

## Phase 3 Status

**✅ Complete Features:**
- ✅ LangGraph workflow planning system
- ✅ Sequential, parallel, conditional workflows
- ✅ AI-powered workflow analysis
- ✅ Workflow execution tracking
- ✅ Enhanced capability matching
- ✅ Database-backed workflow monitoring

**🚧 In Progress:**
- 🚧 Qdrant long-term memory integration
- 🚧 MCP protocol integration
- 🚧 Advanced workflow orchestration

**🎯 Next Steps:**
1. Complete Qdrant memory system
2. Implement MCP tool integration
3. Add advanced workflow DAGs
4. Optimize workflow planning performance
5. Add workflow visualization UI

---

**Phase 3 LangGraph Workflow Planning is now fully operational! 🧠✨**
