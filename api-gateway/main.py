from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field #it's used to define the structure of requests and responses.TYPE-safety
from datetime import datetime, timedelta
from typing import Optional, List#autocomplete ,readability
from jose import jwt#create and verify jwt tokens
import bcrypt#hash pwd
import redis
import httpx
import json
import uuid
import os
import asyncio
import logging
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from functools import wraps
import time
#for orm 

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Redis
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))

# Rate Limiting Config
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "100"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # seconds

def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    if "X-Forwarded-For" in request.headers:
        return request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def check_rate_limit_enhanced(identifier: str, max_requests: int = None, window: int = None) -> tuple[bool, int]:
    """Enhanced rate limiting with Redis - returns (allowed, remaining_requests)"""
    max_requests = max_requests or RATE_LIMIT_MAX_REQUESTS
    window = window or RATE_LIMIT_WINDOW

    key = f"rate_limit:{identifier}"
    try:
        current = redis_client.get(key)
        if current is None:
            redis_client.setex(key, window, 1)
            return True, max_requests - 1

        requests = int(current)
        if requests >= max_requests:
            return False, 0

        redis_client.incr(key)
        return True, max_requests - requests - 1
    except Exception as e:
        logger.error(f"Rate limit error: {e}")
        return True, max_requests  # Fail open

async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    # Skip rate limiting for WebSocket and health checks
    if request.url.path.startswith("/ws") or request.url.path == "/health":
        return await call_next(request)

    client_ip = get_client_ip(request)
    allowed, remaining = await check_rate_limit_enhanced(client_ip)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Maximum {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds",
                "retry_after": RATE_LIMIT_WINDOW,
                "limit": RATE_LIMIT_MAX_REQUESTS,
                "window": RATE_LIMIT_WINDOW
            },
            headers={
                "X-RateLimit-Limit": str(RATE_LIMIT_MAX_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(RATE_LIMIT_WINDOW)
            }
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_MAX_REQUESTS)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(RATE_LIMIT_WINDOW)
    return response

# JWT Config
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# External Services
PLANNER_URL = os.getenv("PLANNER_URL", "http://planner:8001")

# Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    trace_id = Column(String, unique=True, index=True, nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, scheduled, processing, completed, failed
    agent_type = Column(String, default="research")
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentRegistry(Base):
    __tablename__ = "agent_registry"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    agent_type = Column(String, nullable=False)  # research, coding, browser, sql, email
    capabilities = Column(Text)  # JSON array of capabilities
    kafka_topic = Column(String, nullable=False)  # tasks.research, tasks.coding, etc.
    is_active = Column(Boolean, default=True)
    version = Column(String, default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, List[WebSocket]] = {}
        self.redis_pubsub = None
        self.pubsub_task = None

    async def connect(self, websocket: WebSocket, user_id: int):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
            # Subscribe to user's Redis channel
            await self.subscribe_to_user_channel(user_id)
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            # Unsubscribe if no more connections
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def subscribe_to_user_channel(self, user_id: int):
        """Subscribe to Redis pub/sub for user updates"""
        try:
            if self.redis_pubsub is None:
                self.redis_pubsub = redis_client.pubsub()
                await self.start_pubsub_listener()

            channel = f"user_updates:{user_id}"
            self.redis_pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")

        except Exception as e:
            logger.error(f"Failed to subscribe to user channel: {e}")

    async def start_pubsub_listener(self):
        """Start listening to Redis pub/sub messages"""
        if self.pubsub_task is None:
            self.pubsub_task = asyncio.create_task(self.pubsub_listener())

    async def pubsub_listener(self):
        """Listen for Redis pub/sub messages and broadcast to WebSocket clients"""
        try:
            while True:
                message = self.redis_pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    await self.handle_redis_message(message)
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"PubSub listener error: {e}")

    async def handle_redis_message(self, message: dict):
        """Handle incoming Redis pub/sub message"""
        try:
            channel = message['channel'].decode()
            data = json.loads(message['data'])

            # Extract user_id from channel name
            if channel.startswith('user_updates:'):
                user_id = int(channel.split(':')[1])
                await self.send_update(user_id, data)

            # Handle global broadcasts
            elif channel == 'global_updates':
                await self.broadcast_to_all(data)

        except Exception as e:
            logger.error(f"Error handling Redis message: {e}")

    async def send_update(self, user_id: int, message: dict):
        """Send update to specific user's WebSocket connections"""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"WebSocket send error: {e}")

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected users"""
        for user_id in self.active_connections:
            await self.send_update(user_id, message)

    async def publish_to_redis(self, channel: str, message: dict):
        """Publish message to Redis pub/sub"""
        try:
            redis_client.publish(channel, json.dumps(message))
        except Exception as e:
            logger.error(f"Redis publish error: {e}")

    async def publish_user_update(self, user_id: int, message: dict):
        """Publish update for specific user"""
        channel = f"user_updates:{user_id}"
        await self.publish_to_redis(channel, message)

    async def publish_task_update(self, task_data: dict):
        """Publish task progress update"""
        channel = f"task_updates:{task_data.get('trace_id', '')}"
        await self.publish_to_redis(channel, task_data)

    async def publish_workflow_update(self, workflow_data: dict):
        """Publish workflow progress update"""
        channel = f"workflow_updates:{workflow_data.get('job_id', '')}"
        await self.publish_to_redis(channel, workflow_data)

manager = ConnectionManager()

# Pydantic Schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=5000)

class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]

class TaskResponse(BaseModel):
    job_id: int
    trace_id: str
    status: str
    message: str

# FastAPI App
app = FastAPI(title="SecureAI API Gateway", version="1.0.0")

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Auth Dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Verify JWT and return current user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    payload = {"user_id": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# Endpoints
@app.get("/")
def health():
    """Health check"""
    return {"status": "healthy", "service": "api-gateway"}

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: RegisterRequest, db: Session = Depends(get_db)):
    """Register new user"""
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    password_hash = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(email=user_data.email, password_hash=password_hash, name=user_data.name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/auth/login")
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Login and return JWT token"""
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not bcrypt.checkpw(login_data.password.encode('utf-8'), user.password_hash.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/jobs", response_model=TaskResponse)
async def create_job(
    task: TaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit job for processing"""
    # Rate limit
    user_identifier = f"user:{current_user.id}"
    if not await check_rate_limit(user_identifier, max_requests=10, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Generate trace_id and correlation_id for full request tracking
    trace_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    # Create job record
    job = Job(
        user_id=current_user.id,
        trace_id=trace_id,
        prompt=task.prompt,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Send to Planner with correlation_id
    try:
        async with httpx.AsyncClient() as client:
            planner_response = await client.post(
                f"{PLANNER_URL}/plan",
                json={
                    "prompt": task.prompt,
                    "job_id": job.id,
                    "trace_id": trace_id,
                    "correlation_id": correlation_id
                },
                timeout=30.0
            )
            planner_response.raise_for_status()
    except Exception as e:
        job.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to connect to planner: {str(e)}")

    # Send WebSocket update
    await manager.send_update(current_user.id, {
        "type": "job_created",
        "job_id": job.id,
        "trace_id": trace_id,
        "status": "processing"
    })

    return TaskResponse(
        job_id=job.id,
        trace_id=trace_id,
        status="processing",
        message="Job submitted successfully"
    )

@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(
    task: TaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit task for processing (alias for /api/jobs)"""
    return await create_job(task, current_user, db)

@app.get("/api/jobs/{job_id}")
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get job status with all related tasks"""
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    tasks = db.query(Task).filter(Task.job_id == job_id).all()

    return {
        "job_id": job.id,
        "trace_id": job.trace_id,
        "status": job.status,
        "prompt": job.prompt,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "tasks": [
            {
                "task_id": task.id,
                "description": task.description,
                "agent_type": task.agent_type,
                "status": task.status,
                "result": task.result
            }
            for task in tasks
        ]
    }

@app.get("/api/jobs")
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """List user's jobs"""
    jobs = db.query(Job).filter(Job.user_id == current_user.id).order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "jobs": [
            {
                "job_id": job.id,
                "trace_id": job.trace_id,
                "status": job.status,
                "prompt": job.prompt[:100],
                "created_at": job.created_at
            }
            for job in jobs
        ],
        "total": len(jobs)
    }

@app.get("/api/tasks/{job_id}")
async def get_task_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get task status with all related tasks (alias for /api/jobs/{job_id})"""
    return await get_job_status(job_id, current_user, db)

@app.get("/api/tasks")
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 10
):
    """List user's tasks (alias for /api/jobs)"""
    result = await list_jobs(current_user, db, skip, limit)
    # Transform response to use 'tasks' instead of 'jobs' for backward compatibility
    return {
        "tasks": result["jobs"],
        "total": result["total"]
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """Enhanced WebSocket endpoint with Redis pub/sub for real-time updates"""
    await websocket.accept()  # Important: Accept the WebSocket connection first

    # Verify token
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception as e:
        logger.error(f"JWT decode error: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return

    await manager.connect(websocket, user_id)

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Connected to SecureAI real-time updates"
    })

    logger.info(f"WebSocket connected for user {user_id} with Redis pub/sub")

    try:
        # Enhanced message handling loop
        while True:
            # Wait for client messages (heartbeat/ping, subscriptions, etc.)
            data = await websocket.receive_text()
            message_data = json.loads(data) if data else {}

            # Handle different message types
            if message_data.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})

            elif message_data.get("type") == "subscribe_task":
                # Subscribe to specific task updates
                task_id = message_data.get("task_id")
                await websocket.send_json({
                    "type": "subscribed",
                    "target": f"task:{task_id}",
                    "timestamp": datetime.utcnow().isoformat()
                })

            elif message_data.get("type") == "subscribe_workflow":
                # Subscribe to workflow updates
                job_id = message_data.get("job_id")
                await websocket.send_json({
                    "type": "subscribed",
                    "target": f"workflow:{job_id}",
                    "timestamp": datetime.utcnow().isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        manager.disconnect(websocket, user_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
