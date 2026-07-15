from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import os
import json
import redis
import sys
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import logging

# Add shared utilities to path
sys.path.append('/shared')
try:
    from shared.redis_utils import set_workflow_state, get_workflow_state, update_task_status as update_redis_task_status
except ImportError:
    logger.warning("Shared utilities not available")

# Redis for workflow state management
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
redis_client = redis.from_url(REDIS_URL)

# Load environment variables
load_dotenv()

# Basic workflow planning function (replacement for LangGraph)
def plan_basic_workflow(prompt: str, job_id: str, trace_id: str, correlation_id: str) -> dict:
    """Simple rule-based workflow planning"""

    prompt_lower = prompt.lower()
    tasks = []

    # Determine task type based on prompt keywords
    if any(word in prompt_lower for word in ['research', 'search', 'find', 'look up', 'investigate']):
        tasks.append({
            "task_type": "research",
            "required_capability": "web_research",
            "agent_type": "research",
            "description": f"Research: {prompt}",
            "task_data": {"query": prompt, "max_results": 5},
            "depends_on": []
        })

    if any(word in prompt_lower for word in ['sql', 'database', 'query', 'table', 'data']):
        tasks.append({
            "task_type": "sql",
            "required_capability": "database_query",
            "agent_type": "sql",
            "description": f"SQL Query: {prompt}",
            "task_data": {"query": prompt},
            "depends_on": []
        })

    if any(word in prompt_lower for word in ['browse', 'website', 'scrape', 'web page']):
        tasks.append({
            "task_type": "browse",
            "required_capability": "web_browsing",
            "agent_type": "browser",
            "description": f"Browse: {prompt}",
            "task_data": {"url": prompt, "actions": ["navigate", "extract"]},
            "depends_on": []
        })

    if any(word in prompt_lower for word in ['email', 'send', 'notify', 'message']):
        tasks.append({
            "task_type": "email",
            "required_capability": "email_sending",
            "agent_type": "email",
            "description": f"Email: {prompt}",
            "task_data": {"to": "recipient@example.com", "subject": prompt, "body": prompt},
            "depends_on": []
        })

    # Default to research if no specific type detected
    if not tasks:
        tasks.append({
            "task_type": "research",
            "required_capability": "web_research",
            "agent_type": "research",
            "description": f"Research: {prompt}",
            "task_data": {"query": prompt, "max_results": 5},
            "depends_on": []
        })

    return {
        "workflow_id": f"workflow_{job_id}",
        "tasks": tasks,
        "execution_plan": "sequential"
    }

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# External Services
SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://scheduler:8002")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")
    agent_type = Column(String, default="research")
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    trace_id = Column(String, unique=True, index=True, nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    workflow_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    tasks_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Pydantic Schemas
class PlanRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    job_id: int
    trace_id: str
    correlation_id: Optional[str] = None

class TaskCreate(BaseModel):
    job_id: int
    trace_id: str
    description: str
    agent_type: str = "research"

class TaskResponse(BaseModel):
    task_id: int
    description: str
    agent_type: str
    status: str

class PlanResponse(BaseModel):
    job_id: int
    trace_id: str
    tasks: List[TaskResponse]
    message: str
    workflow_type: Optional[str] = None
    workflow_confidence: Optional[float] = None
    workflow_execution_id: Optional[int] = None

# FastAPI App
app = FastAPI(title="SecureAI Planner", version="1.0.0")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def health():
    """Health check"""
    return {"status": "healthy", "service": "planner"}

@app.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest, db: Session = Depends(get_db)):
    """Plan workflow using basic rule-based routing"""

    logger.info(f"Planning workflow for job {request.job_id}")

    job = None  # Initialize to prevent UnboundLocalError in exception handler

    try:
        # Simple rule-based workflow planning
        workflow_result = plan_basic_workflow(
            request.prompt,
            request.job_id,
            request.trace_id,
            request.correlation_id or request.trace_id
        )

        if not workflow_result or not workflow_result.get("tasks"):
            raise HTTPException(status_code=500, detail="Failed to generate workflow plan")

        # Update job status
        job = db.query(Job).filter(Job.id == request.job_id).first()
        if job:
            job.status = "planning"
            db.commit()

        # Create tasks with correlation_id and capabilities
        created_tasks = []
        for task_data in workflow_result["tasks"]:
            # Get capability (new) or agent_type (legacy fallback)
            required_capability = task_data.get("required_capability")
            agent_type = task_data.get("agent_type")  # Legacy compatibility

            task = Task(
                job_id=request.job_id,
                trace_id=request.trace_id,
                description=task_data["description"],
                agent_type=agent_type or required_capability or "research",  # Store capability as agent_type for now
                status="pending"
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            created_tasks.append(task)

        # Save workflow execution to database (simplified)
        try:
            workflow_execution = WorkflowExecution(
                job_id=request.job_id,
                workflow_id=workflow_result.get("workflow_id", f"workflow_{request.job_id}"),
                status="pending",
                tasks_json=json.dumps(workflow_result),
                created_at=datetime.now()
            )
            db.add(workflow_execution)
            db.commit()
            workflow_execution_id = workflow_execution.id
        except Exception as e:
            logger.error(f"Failed to save workflow execution: {e}")
            workflow_execution_id = None

        # Store workflow state in Redis for real-time tracking
        try:
            workflow_state = {
                "job_id": request.job_id,
                "trace_id": request.trace_id,
                "workflow_id": workflow_result.get("workflow_id"),
                "workflow_type": workflow_result.get("workflow_type", "sequential"),
                "status": "pending",
                "tasks": [
                    {
                        "task_id": task.id,
                        "description": task.description,
                        "agent_type": task.agent_type,
                        "status": "scheduled"
                    }
                    for task in created_tasks
                ],
                "created_at": datetime.now().isoformat(),
                "total_tasks": len(created_tasks),
                "completed_tasks": 0
            }
            set_workflow_state(request.job_id, workflow_state, ttl=3600)
            logger.info(f"Workflow state stored in Redis for job {request.job_id}")
        except Exception as e:
            logger.warning(f"Failed to store workflow state in Redis: {e}")

        # Send tasks to Scheduler (with trace_id, correlation_id, and capabilities)
        async with httpx.AsyncClient(timeout=30.0) as client:
            scheduler_payload = []
            for i, task in enumerate(created_tasks):
                task_data = workflow_result["tasks"][i]
                required_capability = task_data.get("required_capability")
                agent_type = task_data.get("agent_type")  # Legacy compatibility

                scheduler_payload.append({
                    "task_id": task.id,
                    "job_id": task.job_id,
                    "trace_id": task.trace_id,
                    "correlation_id": request.correlation_id or task.trace_id,
                    "description": task.description,
                    "required_capability": required_capability,  # New capability-based routing
                    "agent_type": agent_type  # Legacy compatibility
                })

            scheduler_response = await client.post(
                f"{SCHEDULER_URL}/schedule",
                json={"tasks": scheduler_payload},
                timeout=30.0
            )
            scheduler_response.raise_for_status()

        # Update job status
        if job:
            job.status = "scheduled"
            db.commit()

        # Update tasks status
        for task in created_tasks:
            task.status = "scheduled"
        db.commit()

    except Exception as e:
        logger.error(f"Error planning workflow: {e}")
        if job:
            job.status = "failed"
            db.commit()
        raise HTTPException(status_code=500, detail=f"Workflow planning failed: {str(e)}")

    return PlanResponse(
        job_id=request.job_id,
        trace_id=request.trace_id,
        tasks=[
            TaskResponse(
                task_id=task.id,
                description=task.description,
                agent_type=task.agent_type,
                status=task.status
            )
            for task in created_tasks
        ],
        message=f"Created {len(created_tasks)} tasks using {workflow_result.get('workflow_type', 'sequential')} workflow",
        workflow_type=workflow_result.get('workflow_type'),
        workflow_confidence=workflow_result.get('confidence'),
        workflow_execution_id=workflow_execution_id
    )

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "planner"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
