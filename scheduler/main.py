from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import httpx

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TASKS_TOPIC_PREFIX = os.getenv("TASKS_TOPIC_PREFIX", "tasks")
RESULTS_TOPIC = os.getenv("RESULTS_TOPIC", "results")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Models
class AgentRegistry(Base):
    __tablename__ = "agent_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    agent_type = Column(String, nullable=False)
    capabilities = Column(Text)  # JSON array
    kafka_topic = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    version = Column(String, default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_kafka_producer():
    """Create Kafka producer with retry logic"""
    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1
            )
            # Test connection
            producer.bootstrap_connected()
            logger.info(f"Kafka producer created and connected (attempt {attempt + 1}/{max_retries})")
            return producer
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to create Kafka producer (attempt {attempt + 1}/{max_retries}): {e}, retrying in {retry_delay}s...")
                import time
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to create Kafka producer after {max_retries} attempts: {e}")
                raise

    return None

# Pydantic Schemas
class TaskMessage(BaseModel):
    task_id: int
    job_id: int
    trace_id: str
    correlation_id: Optional[str] = None
    description: str
    agent_type: Optional[str] = None  # Legacy compatibility
    required_capability: Optional[str] = None  # New capability-based routing

class ScheduleRequest(BaseModel):
    tasks: List[TaskMessage]

class ScheduleResponse(BaseModel):
    message: str
    tasks_scheduled: int

class AgentRegistrationRequest(BaseModel):
    name: str
    agent_type: str
    capabilities: List[str]
    kafka_topic: str

# FastAPI App
app = FastAPI(title="SecureAI Scheduler", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """Initialize Agent Registry and verify Kafka connection"""
    db = SessionLocal()
    try:
        # Define all Phase 2 agents
        agents_to_register = [
            {
                "name": "Research Agent",
                "agent_type": "research",
                "capabilities": ["research", "analysis", "information_gathering"],
                "topic": f"{TASKS_TOPIC_PREFIX}.research"
            },
            {
                "name": "Browser Agent",
                "agent_type": "browser",
                "capabilities": ["web_scraping", "browser_automation", "selenium"],
                "topic": f"{TASKS_TOPIC_PREFIX}.browser"
            },
            {
                "name": "SQL Agent",
                "agent_type": "sql",
                "capabilities": ["database_queries", "sql_generation", "data_analysis"],
                "topic": f"{TASKS_TOPIC_PREFIX}.sql"
            },
            {
                "name": "Email Agent",
                "agent_type": "email",
                "capabilities": ["email_sending", "notification", "communication"],
                "topic": f"{TASKS_TOPIC_PREFIX}.email"
            }
        ]

        # Register each agent if not exists
        for agent_config in agents_to_register:
            existing = db.query(AgentRegistry).filter(
                AgentRegistry.agent_type == agent_config["agent_type"]
            ).first()

            if not existing:
                agent = AgentRegistry(
                    name=agent_config["name"],
                    agent_type=agent_config["agent_type"],
                    capabilities=json.dumps(agent_config["capabilities"]),
                    kafka_topic=agent_config["topic"],
                    is_active=True,
                    version="1.0.0"
                )
                db.add(agent)
                db.commit()
                logger.info(f"Registered {agent_config['name']}")
            else:
                logger.info(f"Found existing agent: {existing.name}")

    except Exception as e:
        logger.error(f"Failed to initialize Agent Registry: {e}")
    finally:
        db.close()

    # Verify Kafka connection (but don't fail startup if Kafka isn't ready yet)
    try:
        producer = get_kafka_producer()
        if producer:
            producer.bootstrap_connected()
            logger.info("Connected to Kafka successfully")
    except Exception as e:
        logger.warning(f"Kafka not available at startup, will retry when scheduling tasks: {e}")

@app.get("/")
def health():
    """Health check"""
    return {"status": "healthy", "service": "scheduler"}

def get_agent_topic(agent_type: str, db: Session) -> Optional[str]:
    """Query Agent Registry for the appropriate topic (legacy compatibility)"""
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.agent_type == agent_type,
        AgentRegistry.is_active == True
    ).first()

    if agent:
        return agent.kafka_topic
    else:
        logger.warning(f"No active agent found for type: {agent_type}")
        return None

def get_agent_by_capability(required_capability: str, db: Session) -> Optional[str]:
    """Query Agent Registry for agents with required capability"""
    agents = db.query(AgentRegistry).filter(
        AgentRegistry.is_active == True
    ).all()

    # Find agents with the required capability
    matching_agents = []
    for agent in agents:
        try:
            capabilities = json.loads(agent.capabilities) if agent.capabilities else []
            if required_capability in capabilities:
                matching_agents.append(agent)
        except json.JSONDecodeError:
            logger.warning(f"Invalid capabilities JSON for agent {agent.name}")
            continue

    if matching_agents:
        # Return first matching agent's topic (could implement scoring here)
        selected_agent = matching_agents[0]
        logger.info(f"Selected agent '{selected_agent.name}' for capability '{required_capability}'")
        return selected_agent.kafka_topic
    else:
        logger.warning(f"No active agent found with capability: {required_capability}")
        return None

@app.post("/schedule", response_model=ScheduleResponse)
async def schedule_tasks(request: ScheduleRequest, db: Session = Depends(get_db)):
    """Schedule tasks to Kafka using Agent Registry"""

    if not request.tasks:
        raise HTTPException(status_code=400, detail="No tasks to schedule")

    successful_tasks = []
    failed_tasks = []

    try:
        producer = get_kafka_producer()

        for task in request.tasks:
            # Query Agent Registry for topic (capability-based or agent_type-based)
            topic = None
            if task.required_capability:
                # New capability-based routing
                topic = get_agent_by_capability(task.required_capability, db)
                logger.info(f"Capability-based routing: '{task.required_capability}' -> {topic}")
            elif task.agent_type:
                # Legacy agent_type routing (backward compatibility)
                topic = get_agent_topic(task.agent_type, db)
                logger.info(f"Agent-type routing: '{task.agent_type}' -> {topic}")

            if not topic:
                error_msg = f"No agent available for capability: '{task.required_capability}' or type: '{task.agent_type}'"
                logger.error(error_msg)
                failed_tasks.append(task.task_id)
                continue

            task_message = {
                "task_id": task.task_id,
                "job_id": task.job_id,
                "trace_id": task.trace_id,
                "correlation_id": task.correlation_id or task.trace_id,
                "description": task.description,
                "agent_type": task.agent_type,
                "required_capability": task.required_capability,
                "timestamp": datetime.utcnow().isoformat()
            }

            try:
                # Send to appropriate topic
                future = producer.send(topic, value=task_message)
                record_metadata = future.get(timeout=10)

                logger.info(f"Task {task.task_id} sent to {topic} (partition {record_metadata.partition})")
                successful_tasks.append(task.task_id)

            except KafkaError as e:
                logger.error(f"Failed to send task {task.task_id}: {e}")
                failed_tasks.append(task.task_id)
            except Exception as e:
                logger.error(f"Error sending task {task.task_id}: {e}")
                failed_tasks.append(task.task_id)

        producer.flush()

        if failed_tasks:
            logger.warning(f"Failed to schedule {len(failed_tasks)} tasks")

        return ScheduleResponse(
            message=f"Scheduled {len(successful_tasks)} tasks",
            tasks_scheduled=len(successful_tasks),
            task_ids=successful_tasks
        )

    except Exception as e:
        logger.error(f"Scheduler error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule tasks: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        producer = get_kafka_producer()
        producer.bootstrap_connected()
        return {"status": "ok", "service": "scheduler", "kafka": "connected"}
    except:
        return {"status": "degraded", "service": "scheduler", "kafka": "disconnected"}

@app.post("/register")
def register_agent(request: AgentRegistrationRequest, db: Session = Depends(get_db)):
    """Register or update agent in registry"""
    try:
        # Check if agent already exists
        existing_agent = db.query(AgentRegistry).filter(AgentRegistry.name == request.name).first()

        if existing_agent:
            # Update existing agent
            existing_agent.capabilities = json.dumps(request.capabilities)
            existing_agent.kafka_topic = request.kafka_topic
            existing_agent.is_active = True
            existing_agent.updated_at = datetime.utcnow()
            logger.info(f"Updated agent: {request.name}")
        else:
            # Create new agent
            new_agent = AgentRegistry(
                name=request.name,
                agent_type=request.agent_type,
                capabilities=json.dumps(request.capabilities),
                kafka_topic=request.kafka_topic,
                is_active=True
            )
            db.add(new_agent)
            logger.info(f"Registered new agent: {request.name}")

        db.commit()
        return {"status": "registered", "agent": request.name}

    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    """List all registered agents"""
    agents = db.query(AgentRegistry).filter(AgentRegistry.is_active == True).all()
    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "agent_type": agent.agent_type,
                "kafka_topic": agent.kafka_topic,
                "capabilities": json.loads(agent.capabilities) if agent.capabilities else [],
                "version": agent.version
            }
            for agent in agents
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
