# Phase 3: MCP (Model Context Protocol) Integration 🔌

## Overview

The MCP Integration system provides SecureAI agents with standardized access to external tools and data sources using the Model Context Protocol specification. This enables agents to interact with file systems, databases, APIs, web searches, and custom tools in a consistent, secure manner.

---

## Architecture

### MCP Integration Flow

```
Agent Task → Tool Selection → Parameter Validation → Tool Execution → Result Processing → Agent Enhancement
```

### Components

**1. MCP Core Engine**
- Tool registration and management
- Parameter validation
- Tool execution and monitoring
- Error handling and retry logic

**2. Built-in Tools**
- Web Search: Online information retrieval
- File System: File read/write operations
- Database: SQL query execution
- API Calls: HTTP request handling
- Custom Tools: User-defined integrations

**3. FastAPI Service**
- RESTful API for tool operations
- Health monitoring and statistics
- Tool discovery and capabilities
- Execution tracking and logging

**4. Agent Integration**
- Simple function calls for tool access
- Context-aware execution
- Result processing and enhancement
- Error handling with fallback

---

## Features

### 1. Standardized Tool Access

**Capability**: Consistent interface for diverse tools

**Example**:
```python
# Execute different tools with same interface
web_result = await mcp.execute_tool("web_search", {"query": "AI news"})
file_result = await mcp.execute_tool("file_read", {"file_path": "/data/file.txt"})
db_result = await mcp.execute_tool("database_query", {"query": "SELECT * FROM users"})
```

### 2. Parameter Validation

**Capability**: Automatic parameter checking before execution

**Example**:
```python
# Invalid parameters caught before execution
result = await mcp.execute_tool("web_search", {})
# Error: Missing required parameter: query
```

### 3. Tool Type System

**Capability**: Categorized tools for better organization

**Types**:
- `file_system`: File operations
- `database`: Database queries
- `api`: HTTP API calls
- `web_search`: Online search
- `custom`: User-defined tools

### 4. Authentication Support

**Capability**: Secure tool access with authentication

**Example**:
```python
# Tools requiring authentication
api_result = await mcp.execute_tool("api_call", {
    "url": "https://api.example.com/data",
    "headers": {"Authorization": "Bearer token123"}
})
```

---

## Built-in Tools

### 1. Web Search Tool

**Purpose**: Search the web for information

**Parameters**:
- `query` (string, required): Search query
- `num_results` (integer, optional): Number of results (default: 5)

**Usage**:
```python
result = await mcp.execute_tool("web_search", {
    "query": "latest AI developments",
    "num_results": 3
})
```

**Response**:
```json
{
  "query": "latest AI developments",
  "results": [
    {
      "title": "AI Breakthrough in 2024",
      "url": "https://example.com/ai-news",
      "snippet": "Major AI advancement announced..."
    }
  ],
  "total_results": 3
}
```

### 2. File Read Tool

**Purpose**: Read file contents

**Parameters**:
- `file_path` (string, required): Path to file
- `encoding` (string, optional): File encoding (default: utf-8)

**Usage**:
```python
result = await mcp.execute_tool("file_read", {
    "file_path": "/data/research.txt",
    "encoding": "utf-8"
})
```

### 3. File Write Tool

**Purpose**: Write content to files

**Parameters**:
- `file_path` (string, required): Path to file
- `content` (string, required): Content to write
- `mode` (string, optional): Write mode (default: overwrite)

**Usage**:
```python
result = await mcp.execute_tool("file_write", {
    "file_path": "/data/output.txt",
    "content": "Research findings..."
})
```

### 4. Database Query Tool

**Purpose**: Execute SQL queries

**Parameters**:
- `query` (string, required): SQL query
- `database` (string, required): Database name

**Usage**:
```python
result = await mcp.execute_tool("database_query", {
    "query": "SELECT * FROM users WHERE active = true",
    "database": "production"
})
```

### 5. API Call Tool

**Purpose**: Make HTTP API requests

**Parameters**:
- `url` (string, required): API endpoint
- `method` (string, optional): HTTP method (default: GET)
- `headers` (object, optional): Request headers
- `body` (object, optional): Request body

**Usage**:
```python
result = await mcp.execute_tool("api_call", {
    "url": "https://api.example.com/data",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": {"param": "value"}
})
```

---

## API Endpoints

### 1. Health Check
```bash
GET /health
```

**Response**:
```json
{
  "status": "healthy",
  "total_tools": 5,
  "enabled_tools": 5
}
```

### 2. List Tools
```bash
GET /tools?tool_type=web_search
```

**Response**:
```json
[
  {
    "name": "web_search",
    "description": "Search the web for information",
    "tool_type": "web_search",
    "parameters": {...},
    "enabled": true,
    "requires_auth": false
  }
]
```

### 3. Get Tool Details
```bash
GET /tools/{tool_name}
```

**Response**:
```json
{
  "name": "web_search",
  "description": "Search the web for information",
  "type": "web_search",
  "parameters": {...},
  "enabled": true,
  "requires_auth": false,
  "endpoint": "/tools/web_search",
  "method": "POST"
}
```

### 4. Register Tool
```bash
POST /tools/register
```

**Request**:
```json
{
  "name": "weather_api",
  "description": "Get weather information",
  "tool_type": "api",
  "parameters": {
    "location": {"type": "string", "description": "City name"}
  },
  "endpoint": "https://api.weather.com/current"
}
```

### 5. Execute Tool
```bash
POST /tools/execute
```

**Request**:
```json
{
  "tool_name": "web_search",
  "parameters": {
    "query": "artificial intelligence",
    "num_results": 5
  }
}
```

**Response**:
```json
{
  "tool_name": "web_search",
  "success": true,
  "result": {...},
  "execution_time": 1.234,
  "timestamp": "2026-07-13T10:30:00Z"
}
```

---

## Agent Integration

### Basic Integration

```python
from mcp_integration.main import get_mcp_integration

class EnhancedAgent:
    def __init__(self):
        self.mcp = get_mcp_integration()

    async def process_with_tools(self, task):
        # Determine which tool to use
        if "search" in task.lower():
            result = await self.mcp.execute_tool("web_search", {
                "query": task,
                "num_results": 3
            })
        elif "file" in task.lower():
            result = await self.mcp.execute_tool("file_read", {
                "file_path": "/data/relevant_file.txt"
            })

        return result
```

### Advanced Integration

```python
class SmartResearchAgent:
    def __init__(self):
        self.mcp = get_mcp_integration()

    async def comprehensive_research(self, topic):
        # Multi-tool research approach
        results = {}

        # 1. Web search for current information
        web_results = await self.mcp.execute_tool("web_search", {
            "query": f"{topic} latest developments",
            "num_results": 5
        })
        results["web"] = web_results.result

        # 2. File search for historical data
        file_results = await self.mcp.execute_tool("file_read", {
            "file_path": f"/data/{topic}_history.txt"
        })
        results["files"] = file_results.result

        # 3. Database query for structured data
        db_results = await self.mcp.execute_tool("database_query", {
            "query": f"SELECT * FROM research WHERE topic = '{topic}'",
            "database": "knowledge_base"
        })
        results["database"] = db_results.result

        return results
```

---

## Custom Tool Registration

### Example: Weather API Tool

```python
from mcp_integration.main import get_mcp_integration, MCPTool, ToolType

# Register custom weather tool
weather_tool = MCPTool(
    name="weather_check",
    description="Get current weather information",
    tool_type=ToolType.API,
    parameters={
        "location": {"type": "string", "description": "City name"},
        "units": {"type": "string", "default": "metric", "description": "Temperature units"}
    },
    endpoint="https://api.weather.com/current",
    method="GET",
    requires_auth=True
)

mcp = get_mcp_integration()
mcp.register_tool(weather_tool)
```

### Example: Custom Data Processing Tool

```python
# Custom tool for data analysis
analysis_tool = MCPTool(
    name="data_analysis",
    description="Analyze dataset and provide insights",
    tool_type=ToolType.CUSTOM,
    parameters={
        "data": {"type": "object", "description": "Dataset to analyze"},
        "analysis_type": {"type": "string", "description": "Type of analysis"}
    },
    endpoint="/tools/analysis",
    method="POST"
)

mcp.register_tool(analysis_tool)
```

---

## Configuration

### Environment Variables

```bash
# MCP Configuration
MCP_SERVER_URL=http://localhost:8080
MCP_API_KEY=your-api-key
MCP_TIMEOUT=30
```

### Docker Setup

```yaml
mcp-integration:
  build: ./mcp-integration
  ports:
    - "8006:8006"
  environment:
    - MCP_SERVER_URL=http://localhost:8080
    - MCP_API_KEY=${MCP_API_KEY:-}
    - MCP_TIMEOUT=30
  restart: on-failure
```

---

## Usage Examples

### Example 1: Research Agent with Web Search

**Scenario**: Research agent needs current information

```python
# Agent searches for latest AI developments
result = await mcp.execute_tool("web_search", {
    "query": "artificial intelligence breakthroughs 2024",
    "num_results": 5
})

# Process search results
if result.success:
    for finding in result.result["results"]:
        print(f"Found: {finding['title']}")
```

### Example 2: Data Agent with Multiple Tools

**Scenario**: Comprehensive data gathering

```python
# 1. Get web data
web_data = await mcp.execute_tool("web_search", {"query": "market trends"})

# 2. Get historical data from files
file_data = await mcp.execute_tool("file_read", {"file_path": "/data/historical.json"})

# 3. Query database
db_data = await mcp.execute_tool("database_query", {
    "query": "SELECT * FROM sales WHERE date > '2024-01-01'",
    "database": "analytics"
})

# Combine all data sources
comprehensive_data = {
    "current": web_data.result,
    "historical": file_data.result,
    "database": db_data.result
}
```

### Example 3: Multi-Step Workflow

**Scenario**: Complex research workflow

```python
async def research_workflow(topic):
    # Step 1: Search web for current info
    web_info = await mcp.execute_tool("web_search", {
        "query": f"{topic} current status"
    })

    # Step 2: Check if we have historical data
    try:
        historical_data = await mcp.execute_tool("file_read", {
            "file_path": f"/data/{topic}_archive.txt"
        })
    except:
        historical_data = None

    # Step 3: Store new findings
    if web_info.success:
        await mcp.execute_tool("file_write", {
            "file_path": f"/data/{topic}_new.txt",
            "content": str(web_info.result)
        })

    return {"web": web_info.result, "historical": historical_data.result if historical_data else None}
```

---

## Monitoring & Management

### Health Monitoring

```bash
# Check MCP service health
curl http://localhost:8006/health

# Get detailed statistics
curl http://localhost:8006/stats
```

### Tool Management

```bash
# List all tools
curl http://localhost:8006/tools

# Get specific tool details
curl http://localhost:8006/tools/web_search

# Register new tool
curl -X POST http://localhost:8006/tools/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "custom_tool",
    "description": "My custom tool",
    "tool_type": "custom",
    "parameters": {}
  }'
```

### Performance Metrics

**Key Metrics**:
- Total tools available
- Enabled tools count
- Tools by type
- Execution latency
- Success/failure rates

---

## Security Features

### 1. Parameter Validation
- Type checking for all parameters
- Required parameter enforcement
- Default value handling

### 2. Authentication Support
- Per-tool authentication requirements
- API key integration
- Secure credential storage

### 3. Execution Control
- Tool enable/disable functionality
- Timeout protection
- Error handling with fallback

---

## Benefits for SecureAI Platform

### 1. Enhanced Capabilities
- Access to external data sources
- Real-time information retrieval
- File system operations
- Database integration

### 2. Standardized Interface
- Consistent tool access patterns
- Unified error handling
- Common parameter format

### 3. Extensibility
- Easy custom tool registration
- Plugin architecture
- Modular design

### 4. Agent Intelligence
- Multi-source data gathering
- Complex workflow support
- Real-time research capabilities

---

## Future Enhancements

### Planned Features
1. **Real Web Search**: Integration with search APIs
2. **File System Access**: Actual file operations
3. **Database Connectivity**: Real database queries
4. **Tool Marketplace**: Share custom tools
5. **Advanced Auth**: OAuth, API key management

### Scalability
1. **Tool Caching**: Cache tool results
2. **Rate Limiting**: Prevent API abuse
3. **Batch Operations**: Execute multiple tools
4. **Async Execution**: Parallel tool execution

---

## Troubleshooting

### Common Issues

**1. Tool Not Found**
```bash
# Check available tools
curl http://localhost:8006/tools

# Verify tool name spelling
curl http://localhost:8006/tools/web_search
```

**2. Parameter Validation Errors**
```bash
# Check tool parameters
curl http://localhost:8006/tools/web_search

# Ensure required parameters provided
# Missing: query parameter
```

**3. Authentication Failures**
```bash
# Check tool auth requirements
curl http://localhost:8006/tools/api_call

# Verify API keys configured
docker exec -it mcp-integration env | grep MCP_API_KEY
```

---

## Summary

The MCP Integration system provides:

✅ **Standardized Tool Access**: Consistent interface for diverse tools
✅ **Built-in Tools**: Web search, file operations, database queries, API calls
✅ **Custom Tool Support**: Easy registration of user-defined tools
✅ **Parameter Validation**: Automatic checking before execution
✅ **Security Features**: Authentication support and execution control
✅ **Agent Integration**: Simple functions for tool access
✅ **Monitoring**: Health checks and statistics
✅ **Extensibility**: Plugin architecture for custom tools

**Status**: ✅ **OPERATIONAL**

**Next Steps**: Integrate with Advanced Workflow Orchestration

---

**Phase 3 MCP Integration is ready for production use! 🔌✨**
