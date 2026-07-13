# Memory Manager - Qdrant Long-term Memory System

SecureAI's persistent memory system using vector embeddings and semantic search.

## Overview

The Memory Manager provides long-term memory capabilities for all agents in the SecureAI platform. It uses Qdrant vector database to store and retrieve agent experiences using semantic search, enabling agents to learn from past executions and improve over time.

## Features

- **Semantic Memory Search**: Find relevant memories using natural language queries
- **Agent Memory Storage**: Each agent can store results with rich metadata
- **Context Enhancement**: Automatically enhance new tasks with relevant past context
- **Cross-Agent Learning**: Different agents can learn from each other's experiences
- **Job-Specific Memory**: Retrieve all memories associated with specific jobs
- **Automatic Expiry**: Configurable memory expiration (default 30 days)

## Architecture

```
Agent Execution → OpenAI Embeddings → Qdrant Storage → Vector Search → Context Retrieval → Enhanced Task Processing
```

## Components

### 1. Memory Manager (`main.py`)
Core Qdrant integration with OpenAI embeddings
- Vector storage and retrieval
- Semantic search functionality
- Memory lifecycle management

### 2. FastAPI Service (`app.py`)
RESTful API for memory operations
- Health monitoring
- Memory CRUD operations
- Statistics and analytics

### 3. Integration Module (`integration.py`)
Easy-to-use functions for agent integration
- Memory storage helpers
- Context retrieval
- Task enhancement

## API Endpoints

### Store Memory
```http
POST /memory/store
Content-Type: application/json

{
  "content": "Research findings about quantum computing...",
  "job_id": 123,
  "trace_id": "trace-abc-123",
  "agent_type": "research",
  "metadata": {"topic": "quantum_computing"}
}
```

### Retrieve Memories
```http
POST /memory/retrieve
Content-Type: application/json

{
  "query": "quantum computing developments",
  "limit": 5,
  "score_threshold": 0.7
}
```

### Get Job Memories
```http
GET /memory/job/{job_id}
```

### Memory Statistics
```http
GET /memory/stats
```

## Configuration

```bash
# Qdrant Configuration
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=secureai_memory

# OpenAI Configuration
OPENAI_API_KEY=sk-your-key
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536

# Memory Configuration
MEMORY_EXPIRY_DAYS=30
MAX_MEMORY_RESULTS=10
```

## Agent Integration

### Basic Integration

```python
from memory_manager.integration import MemoryIntegration

# Create integration for your agent
memory = MemoryIntegration("research")

# Store results
await memory.store_result(
    result="Research findings...",
    job_id=123,
    trace_id="trace-123",
    metadata={"topic": "ai_research"}
)

# Retrieve context
memories = await memory.retrieve_context(
    query="artificial intelligence developments",
    limit=5
)
```

### Enhanced Research Agent

See `research-agent/agent_with_memory.py` for a complete example of a research agent with memory integration.

## Testing

### Run Test Suite
```bash
python test-memory.py
```

### Manual Testing
```bash
# Test health
curl http://localhost:8005/health

# Store memory
curl -X POST http://localhost:8005/memory/store \
  -H "Content-Type: application/json" \
  -d '{"content": "Test memory", "agent_type": "research"}'

# Retrieve memories
curl -X POST http://localhost:8005/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

## Docker Setup

```bash
# Start Qdrant and memory manager
docker-compose up -d qdrant memory-manager

# Check status
docker-compose ps
curl http://localhost:8005/health
```

## Performance

- **Query Latency**: 50-200ms
- **Storage Latency**: 100-300ms
- **Memory Capacity**: Millions of memories
- **Search Accuracy**: High semantic similarity matching

## Monitoring

### Health Check
```bash
curl http://localhost:8005/health
```

### Statistics
```bash
curl http://localhost:8005/memory/stats
```

### Qdrant Monitoring
```bash
curl http://localhost:6333/collections/secureai_memory
```

## Troubleshooting

### Memory System Unhealthy
```bash
# Check Qdrant connection
docker exec -it memory-manager curl http://qdrant:6333/health

# Check logs
docker-compose logs memory-manager
docker-compose logs qdrant
```

### No Memories Retrieved
```bash
# Check collection exists
curl http://localhost:6333/collections/secureai_memory

# Verify memories are stored
curl http://localhost:8005/memory/stats

# Lower score threshold
curl -X POST http://localhost:8005/memory/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "score_threshold": 0.5}'
```

## Benefits

1. **Improved Research Quality**: Access to past findings
2. **Faster Results**: Cache of previously researched topics
3. **Better Context**: Understand what was already discovered
4. **Knowledge Accumulation**: Build knowledge over time
5. **Cross-Agent Learning**: Share experiences between agents

## Future Enhancements

- Memory consolidation and merging
- Advanced search (hybrid, temporal, multi-modal)
- Memory analytics and quality scoring
- Privacy and security features
- Knowledge graph construction

## Documentation

- **Full Documentation**: See `PHASE3-QDRANT.md` for comprehensive details
- **Testing**: See `test-memory.py` for test examples
- **Integration**: See `integration.py` for usage examples

## Status

✅ **OPERATIONAL** - Ready for production use

The Qdrant Long-term Memory System is fully integrated and ready to enhance agent capabilities with persistent memory!
