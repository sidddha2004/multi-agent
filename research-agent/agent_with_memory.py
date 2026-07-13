"""
Enhanced Research Agent with Long-term Memory Integration

This agent demonstrates how research agents can leverage the Qdrant memory system
to improve research quality and build knowledge over time.
"""

import json
import logging
import os
import time
import asyncio
import httpx
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from openai import OpenAI
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from dotenv import load_dotenv

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TASKS_TOPIC = os.getenv("TASKS_TOPIC", "tasks.research")
RESULTS_TOPIC = os.getenv("RESULTS_TOPIC", "results")
RETRY_TOPIC = os.getenv("RETRY_TOPIC", "tasks.retry")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "tasks.dead_letter")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MEMORY_MANAGER_URL = os.getenv("MEMORY_MANAGER_URL", "http://memory-manager:8005")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Task(Base):
    """Task model - Agent writes results here"""
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

Base.metadata.create_all(bind=engine)


class MemoryIntegration:
    """Simple memory integration for research agent"""

    def __init__(self):
        self.memory_url = MEMORY_MANAGER_URL

    async def check_health(self) -> bool:
        """Check if memory system is healthy"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.memory_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Memory system health check failed: {e}")
            return False

    async def retrieve_context(self, query: str, limit: int = 3) -> str:
        """Retrieve relevant context for research query"""
        try:
            payload = {
                "query": query,
                "limit": limit,
                "agent_type": "research",
                "score_threshold": 0.6
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.memory_url}/memory/retrieve",
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                memories = result.get("memories", [])

                if memories:
                    context_parts = []
                    for memory in memories[:2]:  # Use top 2
                        if memory.get("score", 0) > 0.7:
                            context_parts.append(f"- Previous research: {memory['content'][:200]}...")

                    if context_parts:
                        return "\n".join(context_parts)

                return ""

        except Exception as e:
            logger.warning(f"Failed to retrieve context: {e}")
            return ""

    async def store_research_result(self, result: str, job_id: int, trace_id: str, metadata: dict) -> bool:
        """Store research result in long-term memory"""
        try:
            payload = {
                "content": result,
                "job_id": job_id,
                "trace_id": trace_id,
                "agent_type": "research",
                "metadata": metadata
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.memory_url}/memory/store",
                    json=payload
                )
                response.raise_for_status()

                logger.info(f"Stored research result in memory for job {job_id}")
                return True

        except Exception as e:
            logger.warning(f"Failed to store research result: {e}")
            return False


class EnhancedResearchAgent:
    """Research Agent with Long-term Memory Integration"""

    def __init__(self):
        self.consumer = KafkaConsumer(
            TASKS_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='research-agent-group'
        )
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.redis_client = redis.from_url(REDIS_URL)
        self.memory = MemoryIntegration()

        # Start heartbeat thread
        self.start_heartbeat()

        logger.info("Enhanced Research Agent with Memory initialized")

    def start_heartbeat(self):
        """Start heartbeat thread"""
        def heartbeat_loop():
            while True:
                try:
                    heartbeat_data = {
                        "agent_type": "research",
                        "status": "active",
                        "timestamp": datetime.utcnow().isoformat(),
                        "topic": TASKS_TOPIC,
                        "memory_enabled": True
                    }
                    self.redis_client.setex(
                        f"heartbeat:research-agent",
                        HEARTBEAT_INTERVAL * 2,
                        json.dumps(heartbeat_data)
                    )
                    logger.debug("Heartbeat sent")
                    time.sleep(HEARTBEAT_INTERVAL)
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    time.sleep(5)

        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()

    async def enhance_with_memory(self, description: str, job_id: int) -> str:
        """Enhance task description with relevant memory context"""
        try:
            # Check memory system health
            if not await self.memory.check_health():
                logger.info("Memory system unavailable, using original description")
                return description

            # Retrieve relevant context
            context = await self.memory.retrieve_context(
                query=description,
                limit=3
            )

            if context:
                enhanced_description = f"{description}\n\nRelevant Research Context:\n{context}"
                logger.info(f"Enhanced task with memory context for job {job_id}")
                return enhanced_description
            else:
                logger.info(f"No relevant context found for job {job_id}")
                return description

        except Exception as e:
            logger.warning(f"Failed to enhance with memory: {e}")
            return description

    def extract_topic(self, result: str) -> str:
        """Extract research topic from result"""
        try:
            # Simple keyword extraction
            keywords = ["quantum", "ai", "machine learning", "blockchain",
                       "climate", "health", "finance", "technology"]

            result_lower = result.lower()
            for keyword in keywords:
                if keyword in result_lower:
                    return keyword.replace(" ", "_")

            return "general_research"

        except Exception as e:
            logger.warning(f"Failed to extract topic: {e}")
            return "unknown"

    async def process_task(self, task_message: Dict[str, Any]):
        """Process a research task with memory enhancement"""
        try:
            task_id = task_message["task_id"]
            job_id = task_message["job_id"]
            trace_id = task_message["trace_id"]
            description = task_message["description"]

            logger.info(f"Processing task {task_id} for job {job_id} with memory enhancement")

            # Enhance description with memory context
            enhanced_description = await self.enhance_with_memory(description, job_id)

            # Perform research with enhanced context
            result = await self.research_with_openai(enhanced_description, description)

            # Update task in database
            db = Session()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.result = result
                task.status = "completed"
                task.updated_at = datetime.utcnow()
                db.commit()

            # Publish result
            result_message = {
                "task_id": task_id,
                "job_id": job_id,
                "trace_id": trace_id,
                "agent_type": "research",
                "result": result,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "memory_enhanced": enhanced_description != description
            }

            self.producer.send(RESULTS_TOPIC, value=result_message)
            self.producer.flush()

            logger.info(f"Task {task_id} completed successfully")

            # Store result in long-term memory
            await self.memory.store_research_result(
                result=result,
                job_id=job_id,
                trace_id=trace_id,
                metadata={
                    "task_type": "research",
                    "topic": self.extract_topic(result),
                    "original_description": description,
                    "was_enhanced": enhanced_description != description
                }
            )

            db.close()

        except Exception as e:
            logger.error(f"Failed to process task: {e}")
            await self.handle_task_failure(task_message, str(e))

    async def research_with_openai(self, enhanced_description: str, original_description: str) -> str:
        """Perform research using OpenAI with enhanced context"""
        try:
            system_prompt = """You are a research assistant with access to previous research findings.
Use the provided context to build upon existing knowledge rather than repeating it.
Provide comprehensive, up-to-date information on the topic."""

            user_prompt = f"""Research Request: {original_description}

{enhanced_description}

Please provide comprehensive research findings, building upon any previous context mentioned above."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI research failed: {e}")
            return f"Research failed: {str(e)}"

    async def handle_task_failure(self, task_message: Dict[str, Any], error_message: str):
        """Handle task failure with retry logic"""
        try:
            retry_count = task_message.get("retry_count", 0)

            if retry_count < MAX_RETRIES:
                # Send to retry queue
                retry_message = task_message.copy()
                retry_message["retry_count"] = retry_count + 1
                retry_message["error_message"] = error_message
                retry_message["original_topic"] = TASKS_TOPIC

                self.producer.send(RETRY_TOPIC, value=retry_message)
                self.producer.flush()

                logger.info(f"Task {task_message['task_id']} sent to retry queue (attempt {retry_count + 1})")

                # Update task status
                db = Session()
                task = db.query(Task).filter(Task.id == task_message["task_id"]).first()
                if task:
                    task.status = "retrying"
                    db.commit()
                db.close()

            else:
                # Max retries exceeded, send to DLQ
                dlq_message = task_message.copy()
                dlq_message["error_message"] = error_message
                dlq_message["final_failure"] = True

                self.producer.send(DLQ_TOPIC, value=dlq_message)
                self.producer.flush()

                logger.error(f"Task {task_message['task_id']} sent to DLQ after {MAX_RETRIES} retries")

                # Update task status
                db = Session()
                task = db.query(Task).filter(Task.id == task_message["task_id"]).first()
                if task:
                    task.status = "failed"
                    db.commit()
                db.close()

        except Exception as e:
            logger.error(f"Failed to handle task failure: {e}")

    def run(self):
        """Run the research agent"""
        logger.info("Enhanced Research Agent starting...")

        try:
            for message in self.consumer:
                try:
                    task_message = message.value
                    # Process task asynchronously
                    asyncio.run(self.process_task(task_message))

                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.consumer.close()
            self.producer.close()


if __name__ == "__main__":
    agent = EnhancedResearchAgent()
    agent.run()
