"""
FastAPI Service for MCP Integration

Provides REST API endpoints for Model Context Protocol operations.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import asyncio

from main import get_mcp_integration, MCPTool, ToolType, mcp_health_check

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="SecureAI MCP Integration",
    description="Model Context Protocol integration for external tool access",
    version="1.0.0"
)


# Pydantic Schemas
class ToolRegistrationRequest(BaseModel):
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    tool_type: str = Field(..., description="Tool type (file_system, database, api, web_search, custom)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    endpoint: Optional[str] = Field(None, description="Tool endpoint URL")
    method: str = Field("GET", description="HTTP method")
    requires_auth: bool = Field(False, description="Requires authentication")

class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(..., description="Name of tool to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    context: Optional[Dict[str, Any]] = Field(None, description="Execution context")

class ToolResponse(BaseModel):
    name: str
    description: str
    tool_type: str
    parameters: Dict[str, Any]
    enabled: bool
    requires_auth: bool

class ToolExecutionResponse(BaseModel):
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str

class HealthResponse(BaseModel):
    status: str
    total_tools: int
    enabled_tools: int
    error: Optional[str] = None


# Endpoints
@app.get("/", tags=["Health"])
def root():
    """Root endpoint"""
    return {
        "service": "mcp-integration",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def get_health():
    """Health check endpoint"""
    health_data = mcp_health_check()
    return HealthResponse(**health_data)


@app.get("/tools", response_model=List[ToolResponse], tags=["Tools"])
def list_tools(tool_type: Optional[str] = None):
    """List available MCP tools"""
    try:
        integration = get_mcp_integration()

        # Convert string tool_type to enum if provided
        filter_type = None
        if tool_type:
            try:
                filter_type = ToolType(tool_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid tool type: {tool_type}")

        tools = integration.list_tools(filter_type)

        return [
            ToolResponse(
                name=tool.name,
                description=tool.description,
                tool_type=tool.tool_type.value,
                parameters=tool.parameters,
                enabled=tool.enabled,
                requires_auth=tool.requires_auth
            )
            for tool in tools
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@app.get("/tools/{tool_name}", response_model=Dict[str, Any], tags=["Tools"])
def get_tool_details(tool_name: str):
    """Get detailed information about a specific tool"""
    try:
        integration = get_mcp_integration()
        capabilities = integration.get_tool_capabilities(tool_name)

        if not capabilities:
            raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")

        return capabilities

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tool details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tool details: {str(e)}")


@app.post("/tools/register", response_model=Dict[str, str], tags=["Tools"])
def register_tool(request: ToolRegistrationRequest):
    """Register a new MCP tool"""
    try:
        integration = get_mcp_integration()

        # Convert string tool_type to enum
        try:
            tool_type_enum = ToolType(request.tool_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid tool type: {request.tool_type}. Must be one of: {', '.join([t.value for t in ToolType])}"
            )

        tool = MCPTool(
            name=request.name,
            description=request.description,
            tool_type=tool_type_enum,
            parameters=request.parameters,
            endpoint=request.endpoint,
            method=request.method,
            requires_auth=request.requires_auth
        )

        success = integration.register_tool(tool)

        if success:
            return {
                "status": "success",
                "message": f"Tool {request.name} registered successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to register tool")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register tool: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register tool: {str(e)}")


@app.post("/tools/execute", response_model=ToolExecutionResponse, tags=["Tools"])
async def execute_tool(request: ToolExecutionRequest):
    """Execute an MCP tool"""
    try:
        integration = get_mcp_integration()

        result = await integration.execute_tool(
            tool_name=request.tool_name,
            parameters=request.parameters,
            context=request.context
        )

        return ToolExecutionResponse(
            tool_name=result.tool_name,
            success=result.success,
            result=result.result,
            error=result.error,
            execution_time=result.execution_time,
            timestamp=result.timestamp
        )

    except Exception as e:
        logger.error(f"Failed to execute tool: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute tool: {str(e)}")


@app.post("/tools/{tool_name}/execute", response_model=ToolExecutionResponse, tags=["Tools"])
async def execute_tool_by_name(tool_name: str, parameters: Dict[str, Any] = None, context: Dict[str, Any] = None):
    """Execute a tool by name (alternative endpoint)"""
    try:
        integration = get_mcp_integration()

        result = await integration.execute_tool(
            tool_name=tool_name,
            parameters=parameters or {},
            context=context
        )

        return ToolExecutionResponse(
            tool_name=result.tool_name,
            success=result.success,
            result=result.result,
            error=result.error,
            execution_time=result.execution_time,
            timestamp=result.timestamp
        )

    except Exception as e:
        logger.error(f"Failed to execute tool: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute tool: {str(e)}")


@app.get("/stats", response_model=Dict[str, Any], tags=["Monitoring"])
def get_mcp_stats():
    """Get MCP integration statistics"""
    try:
        integration = get_mcp_integration()
        tools = integration.list_tools()

        stats = {
            "total_tools": len(tools),
            "enabled_tools": sum(1 for t in tools if t.enabled),
            "disabled_tools": sum(1 for t in tools if not t.enabled),
            "tools_by_type": {},
            "tools_requiring_auth": sum(1 for t in tools if t.requires_auth)
        }

        # Count tools by type
        for tool in tools:
            tool_type = tool.tool_type.value
            stats["tools_by_type"][tool_type] = stats["tools_by_type"].get(tool_type, 0) + 1

        return stats

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
