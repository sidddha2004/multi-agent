"""
FastAPI Service for Qdrant Memory Manager

Provides REST API endpoints for managing long-term memory.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from main import get_memory_manager, health_check

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="SecureAI Memory Manager",
    description="Long-term memory management using Qdrant vector database",
    version="1.0.0"
)


# Pydantic Schemas
class MemoryStoreRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Content to store in memory")
    job_id: Optional[int] = Field(None, description="Associated job ID")
    trace_id: Optional[str] = Field(None, description="Associated trace ID")
    agent_type: Optional[str] = Field(None, description="Agent type that created the memory")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class MemoryRetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query to search for relevant memories")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")
    agent_type: Optional[str] = Field(None, description="Filter by agent type")
    job_id: Optional[int] = Field(None, description="Filter by job ID")
    score_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity score")

class MemoryResponse(BaseModel):
    id: str
    score: Optional[float] = None
    content: str
    job_id: Optional[int] = None
    trace_id: Optional[str] = None
    agent_type: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MemoryListResponse(BaseModel):
    memories: List[MemoryResponse]
    count: int

class MemoryStatsResponse(BaseModel):
    total_memories: int
    vector_dimension: int
    collection_name: str
    memory_expiry_days: int
    max_results: int

class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    openai_connected: bool
    stats: Optional[Dict[str, Any]] = None


# Endpoints
@app.get("/", tags=["Health"])
def root():
    """Root endpoint"""
    return {
        "service": "memory-manager",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def get_health():
    """Health check endpoint"""
    return health_check()


@app.post("/memory/store", response_model=Dict[str, str], tags=["Memory"])
def store_memory(request: MemoryStoreRequest):
    """Store a memory in Qdrant"""
    try:
        memory_manager = get_memory_manager()

        memory_id = memory_manager.store_memory(
            content=request.content,
            metadata=request.metadata,
            job_id=request.job_id,
            trace_id=request.trace_id,
            agent_type=request.agent_type
        )

        return {
            "status": "success",
            "memory_id": memory_id,
            "message": "Memory stored successfully"
        }

    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")


@app.post("/memory/retrieve", response_model=MemoryListResponse, tags=["Memory"])
def retrieve_memories(request: MemoryRetrieveRequest):
    """Retrieve relevant memories based on query"""
    try:
        memory_manager = get_memory_manager()

        memories = memory_manager.retrieve_memories(
            query=request.query,
            limit=request.limit,
            agent_type=request.agent_type,
            job_id=request.job_id,
            score_threshold=request.score_threshold
        )

        # Format memories for response
        formatted_memories = []
        for memory in memories:
            formatted_memories.append(MemoryResponse(
                id=memory.get("id", ""),
                score=memory.get("score"),
                content=memory.get("content", ""),
                job_id=memory.get("job_id"),
                trace_id=memory.get("trace_id"),
                agent_type=memory.get("agent_type"),
                timestamp=memory.get("timestamp", datetime.utcnow().isoformat()),
                metadata={k: v for k, v in memory.items()
                         if k not in ["id", "score", "content", "job_id", "trace_id", "agent_type", "timestamp"]}
            ))

        return MemoryListResponse(
            memories=formatted_memories,
            count=len(formatted_memories)
        )

    except Exception as e:
        logger.error(f"Failed to retrieve memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {str(e)}")


@app.get("/memory/job/{job_id}", response_model=MemoryListResponse, tags=["Memory"])
def get_memories_by_job(job_id: int):
    """Get all memories associated with a specific job"""
    try:
        memory_manager = get_memory_manager()

        memories = memory_manager.get_memories_by_job(job_id)

        # Format memories for response
        formatted_memories = []
        for memory in memories:
            formatted_memories.append(MemoryResponse(
                id=memory.get("id", ""),
                score=None,  # No score for direct retrieval
                content=memory.get("content", ""),
                job_id=memory.get("job_id"),
                trace_id=memory.get("trace_id"),
                agent_type=memory.get("agent_type"),
                timestamp=memory.get("timestamp", datetime.utcnow().isoformat()),
                metadata={k: v for k, v in memory.items()
                         if k not in ["id", "content", "job_id", "trace_id", "agent_type", "timestamp"]}
            ))

        return MemoryListResponse(
            memories=formatted_memories,
            count=len(formatted_memories)
        )

    except Exception as e:
        logger.error(f"Failed to get memories by job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get memories: {str(e)}")


@app.get("/memory/stats", response_model=MemoryStatsResponse, tags=["Memory"])
def get_memory_stats():
    """Get statistics about stored memories"""
    try:
        memory_manager = get_memory_manager()
        stats = memory_manager.get_memory_stats()

        return MemoryStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.delete("/memory/expired", response_model=Dict[str, Any], tags=["Memory"])
def delete_expired_memories():
    """Delete expired memories from the database"""
    try:
        memory_manager = get_memory_manager()
        deleted_count = memory_manager.delete_expired_memories()

        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} expired memories"
        }

    except Exception as e:
        logger.error(f"Failed to delete expired memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete expired memories: {str(e)}")


@app.delete("/memory/all", response_model=Dict[str, str], tags=["Memory"])
def clear_all_memories():
    """Clear all memories from the database (use with caution)"""
    try:
        memory_manager = get_memory_manager()
        success = memory_manager.clear_all_memories()

        if success:
            return {
                "status": "success",
                "message": "All memories cleared successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear memories")

    except Exception as e:
        logger.error(f"Failed to clear memories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear memories: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
