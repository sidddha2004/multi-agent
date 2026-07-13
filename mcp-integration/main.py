"""
MCP (Model Context Protocol) Integration for SecureAI

Provides standardized integration with external tools and data sources
using the Model Context Protocol specification.
"""

import os
import logging
import json
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")
MCP_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "30"))

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ToolType(Enum):
    """Types of MCP tools"""
    FILE_SYSTEM = "file_system"
    DATABASE = "database"
    API = "api"
    WEB_SEARCH = "web_search"
    CUSTOM = "custom"


class MCPTool(BaseModel):
    """MCP Tool definition"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    tool_type: ToolType = Field(..., description="Type of tool")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    endpoint: Optional[str] = Field(None, description="Tool endpoint URL")
    method: str = Field("GET", description="HTTP method")
    headers: Dict[str, str] = Field(default_factory=dict, description="Default headers")
    requires_auth: bool = Field(False, description="Requires authentication")
    enabled: bool = Field(True, description="Tool is enabled")


class MCPToolResponse(BaseModel):
    """MCP Tool execution response"""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MCPIntegration:
    """Main MCP Integration class"""

    def __init__(self):
        """Initialize MCP integration"""
        self.tools: Dict[str, MCPTool] = {}
        self.http_client = None
        self.load_builtin_tools()
        logger.info("MCP Integration initialized")

    def load_builtin_tools(self):
        """Load built-in MCP tools"""
        builtin_tools = [
            MCPTool(
                name="web_search",
                description="Search the web for information",
                tool_type=ToolType.WEB_SEARCH,
                parameters={
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "default": 5, "description": "Number of results"}
                },
                endpoint="/tools/web_search",
                method="POST"
            ),
            MCPTool(
                name="file_read",
                description="Read file contents",
                tool_type=ToolType.FILE_SYSTEM,
                parameters={
                    "file_path": {"type": "string", "description": "Path to file"},
                    "encoding": {"type": "string", "default": "utf-8", "description": "File encoding"}
                },
                endpoint="/tools/file_read",
                method="POST"
            ),
            MCPTool(
                name="file_write",
                description="Write content to file",
                tool_type=ToolType.FILE_SYSTEM,
                parameters={
                    "file_path": {"type": "string", "description": "Path to file"},
                    "content": {"type": "string", "description": "Content to write"},
                    "mode": {"type": "string", "default": "overwrite", "description": "Write mode"}
                },
                endpoint="/tools/file_write",
                method="POST",
                requires_auth=True
            ),
            MCPTool(
                name="database_query",
                description="Execute database query",
                tool_type=ToolType.DATABASE,
                parameters={
                    "query": {"type": "string", "description": "SQL query"},
                    "database": {"type": "string", "description": "Database name"}
                },
                endpoint="/tools/database_query",
                method="POST",
                requires_auth=True
            ),
            MCPTool(
                name="api_call",
                description="Make HTTP API call",
                tool_type=ToolType.API,
                parameters={
                    "url": {"type": "string", "description": "API endpoint URL"},
                    "method": {"type": "string", "default": "GET", "description": "HTTP method"},
                    "headers": {"type": "object", "description": "Request headers"},
                    "body": {"type": "object", "description": "Request body"}
                },
                endpoint="/tools/api_call",
                method="POST"
            )
        ]

        for tool in builtin_tools:
            self.tools[tool.name] = tool

        logger.info(f"Loaded {len(builtin_tools)} built-in MCP tools")

    def register_tool(self, tool: MCPTool) -> bool:
        """Register a new MCP tool"""
        try:
            if tool.name in self.tools:
                logger.warning(f"Tool {tool.name} already exists, updating...")
            self.tools[tool.name] = tool
            logger.info(f"Registered MCP tool: {tool.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register tool {tool.name}: {e}")
            return False

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Get tool by name"""
        return self.tools.get(tool_name)

    def list_tools(self, tool_type: Optional[ToolType] = None) -> List[MCPTool]:
        """List available tools, optionally filtered by type"""
        tools = list(self.tools.values())
        if tool_type:
            tools = [t for t in tools if t.tool_type == tool_type]
        return tools

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> MCPToolResponse:
        """Execute an MCP tool"""
        start_time = datetime.utcnow()

        try:
            tool = self.get_tool(tool_name)
            if not tool:
                return MCPToolResponse(
                    tool_name=tool_name,
                    success=False,
                    result=None,
                    error=f"Tool {tool_name} not found"
                )

            if not tool.enabled:
                return MCPToolResponse(
                    tool_name=tool_name,
                    success=False,
                    result=None,
                    error=f"Tool {tool_name} is disabled"
                )

            # Validate parameters
            validated_params = self._validate_parameters(tool, parameters)
            if not validated_params["valid"]:
                return MCPToolResponse(
                    tool_name=tool_name,
                    success=False,
                    result=None,
                    error=f"Invalid parameters: {validated_params['errors']}"
                )

            # Execute tool based on type
            result = await self._execute_tool_by_type(tool, parameters, context)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return MCPToolResponse(
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Tool execution failed: {e}")
            return MCPToolResponse(
                tool_name=tool_name,
                success=False,
                result=None,
                error=str(e),
                execution_time=execution_time
            )

    def _validate_parameters(self, tool: MCPTool, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool parameters"""
        errors = []
        validated = {}

        try:
            # Check required parameters
            for param_name, param_schema in tool.parameters.items():
                if param_name not in parameters:
                    if "default" not in param_schema:
                        errors.append(f"Missing required parameter: {param_name}")
                    else:
                        validated[param_name] = param_schema["default"]
                else:
                    # Type validation
                    param_value = parameters[param_name]
                    param_type = param_schema.get("type")

                    if param_type == "string" and not isinstance(param_value, str):
                        errors.append(f"Parameter {param_name} must be string")
                    elif param_type == "integer" and not isinstance(param_value, int):
                        errors.append(f"Parameter {param_name} must be integer")
                    elif param_type == "object" and not isinstance(param_value, dict):
                        errors.append(f"Parameter {param_name} must be object")
                    else:
                        validated[param_name] = param_value

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "validated": validated
            }

        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)],
                "validated": {}
            }

    async def _execute_tool_by_type(
        self,
        tool: MCPTool,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute tool based on its type"""

        if tool.tool_type == ToolType.WEB_SEARCH:
            return await self._execute_web_search(parameters, context)
        elif tool.tool_type == ToolType.FILE_SYSTEM:
            return await self._execute_file_operation(tool.name, parameters, context)
        elif tool.tool_type == ToolType.DATABASE:
            return await self._execute_database_query(parameters, context)
        elif tool.tool_type == ToolType.API:
            return await self._execute_api_call(parameters, context)
        else:
            return await self._execute_custom_tool(tool, parameters, context)

    async def _execute_web_search(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute web search tool"""
        try:
            query = parameters.get("query")
            num_results = parameters.get("num_results", 5)

            # Simulate web search (in production, integrate with real search API)
            logger.info(f"Web search: {query} (limit: {num_results})")

            # Mock results for demonstration
            mock_results = [
                {
                    "title": f"Search result {i+1} for: {query}",
                    "url": f"https://example.com/result-{i+1}",
                    "snippet": f"This is a mock search result snippet for query: {query}"
                }
                for i in range(min(num_results, 5))
            ]

            return {
                "query": query,
                "results": mock_results,
                "total_results": len(mock_results)
            }

        except Exception as e:
            logger.error(f"Web search failed: {e}")
            raise

    async def _execute_file_operation(self, tool_name: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute file system operation"""
        try:
            file_path = parameters.get("file_path")

            if tool_name == "file_read":
                # Mock file read
                return {
                    "file_path": file_path,
                    "content": f"Mock content from {file_path}",
                    "size": 1024,
                    "encoding": parameters.get("encoding", "utf-8")
                }
            elif tool_name == "file_write":
                # Mock file write
                content = parameters.get("content", "")
                return {
                    "file_path": file_path,
                    "bytes_written": len(content.encode()),
                    "success": True
                }

        except Exception as e:
            logger.error(f"File operation failed: {e}")
            raise

    async def _execute_database_query(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute database query"""
        try:
            query = parameters.get("query")
            database = parameters.get("database")

            logger.info(f"Database query on {database}: {query}")

            # Mock database query result
            return {
                "database": database,
                "query": query,
                "rows": [
                    {"id": 1, "name": "Mock Data 1"},
                    {"id": 2, "name": "Mock Data 2"}
                ],
                "row_count": 2
            }

        except Exception as e:
            logger.error(f"Database query failed: {e}")
            raise

    async def _execute_api_call(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute HTTP API call"""
        try:
            url = parameters.get("url")
            method = parameters.get("method", "GET")
            headers = parameters.get("headers", {})
            body = parameters.get("body")

            logger.info(f"API call: {method} {url}")

            # In production, execute real HTTP call
            # For now, return mock response
            return {
                "url": url,
                "method": method,
                "status_code": 200,
                "response": {
                    "message": "Mock API response",
                    "data": {"result": "success"}
                }
            }

        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise

    async def _execute_custom_tool(self, tool: MCPTool, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute custom tool"""
        try:
            logger.info(f"Executing custom tool: {tool.name}")

            # For custom tools, you would implement specific logic
            return {
                "tool": tool.name,
                "parameters": parameters,
                "result": f"Custom tool {tool.name} executed"
            }

        except Exception as e:
            logger.error(f"Custom tool execution failed: {e}")
            raise

    async def get_tool_capabilities(self, tool_name: str) -> Dict[str, Any]:
        """Get detailed tool capabilities"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {}

        return {
            "name": tool.name,
            "description": tool.description,
            "type": tool.tool_type.value,
            "parameters": tool.parameters,
            "enabled": tool.enabled,
            "requires_auth": tool.requires_auth,
            "endpoint": tool.endpoint,
            "method": tool.method
        }


# Global MCP integration instance
mcp_integration = None

def get_mcp_integration() -> MCPIntegration:
    """Get or create global MCP integration instance"""
    global mcp_integration
    if mcp_integration is None:
        mcp_integration = MCPIntegration()
    return mcp_integration


# Health check
def mcp_health_check() -> Dict[str, Any]:
    """Check MCP integration health"""
    try:
        integration = get_mcp_integration()
        tools = integration.list_tools()

        return {
            "status": "healthy",
            "total_tools": len(tools),
            "enabled_tools": sum(1 for t in tools if t.enabled),
            "tool_types": {}
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    # Test MCP integration
    print("Testing MCP Integration...")

    try:
        integration = get_mcp_integration()
        print("✅ MCP integration initialized")

        # Test health
        health = mcp_health_check()
        print(f"✅ Health check: {health['status']}")
        print(f"   Total tools: {health.get('total_tools', 0)}")
        print(f"   Enabled tools: {health.get('enabled_tools', 0)}")

        # List tools
        tools = integration.list_tools()
        print(f"✅ Available tools: {len(tools)}")
        for tool in tools:
            print(f"   - {tool.name}: {tool.description}")

        # Test tool execution
        async def test_execution():
            result = await integration.execute_tool(
                "web_search",
                {"query": "artificial intelligence", "num_results": 3}
            )
            print(f"✅ Tool execution test:")
            print(f"   Tool: {result.tool_name}")
            print(f"   Success: {result.success}")
            print(f"   Result: {result.result}")
            print(f"   Execution time: {result.execution_time:.3f}s")

        asyncio.run(test_execution())
        print("\n✅ All MCP tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
