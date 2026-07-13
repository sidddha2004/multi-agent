import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any

from kafka import KafkaConsumer
from kafka.errors import KafkaError
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from dotenv import load_dotenv

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RESULTS_TOPIC = os.getenv("RESULTS_TOPIC", "results")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")

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


class Job(Base):
    """Job model"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    trace_id = Column(String, unique=True, index=True, nullable=False)
    prompt = Column(Text, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(Base):
    """Task model"""
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


def get_db():
    """Get database session"""
    db = Session()
    try:
        return db
    finally:
        pass


def publish_websocket_update(job_id: int, trace_id: str, status: str, result: str = None):
    """Publish update to Redis for WebSocket Gateway"""
    try:
        redis_client = redis.from_url(REDIS_URL)

        update_message = {
            "type": "task_update",
            "job_id": job_id,
            "trace_id": trace_id,
            "status": status,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Publish to Redis channel for WebSocket Gateway
        channel = f"job_updates:{job_id}"
        redis_client.publish(channel, json.dumps(update_message))

        # Also set in Redis for polling fallback
        key = f"job_status:{job_id}"
        redis_client.setex(key, 3600, json.dumps(update_message))

        logger.info(f"Published WebSocket update for job {job_id} ({trace_id})")

    except Exception as e:
        logger.error(f"Failed to publish WebSocket update: {e}")


def aggregate_results(job_id: int, trace_id: str) -> Dict[str, Any]:
    """Aggregate all task results for a job"""
    try:
        db = get_db()
        tasks = db.query(Task).filter(Task.job_id == job_id).all()

        aggregated = {
            "job_id": job_id,
            "trace_id": trace_id,
            "total_tasks": len(tasks),
            "completed_tasks": sum(1 for t in tasks if t.status == "completed"),
            "failed_tasks": sum(1 for t in tasks if t.status == "failed"),
            "pending_tasks": sum(1 for t in tasks if t.status in ["pending", "processing"]),
            "results": []
        }

        for task in tasks:
            if task.result:
                aggregated["results"].append({
                    "task_id": task.id,
                    "agent_type": task.agent_type,
                    "description": task.description,
                    "result": task.result,
                    "status": task.status
                })

        db.close()
        return aggregated

    except Exception as e:
        logger.error(f"Failed to aggregate results: {e}")
        return {
            "job_id": job_id,
            "trace_id": trace_id,
            "error": str(e)
        }


def process_result(result_message: Dict[str, Any]):
    """Process a single result message"""
    task_id = result_message.get("task_id")
    job_id = result_message.get("job_id")
    trace_id = result_message.get("trace_id")
    result = result_message.get("result")
    agent_type = result_message.get("agent_type")
    status = result_message.get("status", "completed")

    logger.info(f"Processing result from {agent_type} agent for task {task_id}, job {job_id} ({trace_id})")

    try:
        # Update task in database
        db = get_db()
        task = db.query(Task).filter(Task.id == task_id, Task.trace_id == trace_id).first()

        if task:
            task.status = status
            task.result = result
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Updated task {task_id} with result")
        else:
            logger.warning(f"Task {task_id} ({trace_id}) not found")

        # Check if all tasks in job are complete
        tasks = db.query(Task).filter(Task.job_id == job_id).all()
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")

        job_status = "processing"
        if completed + failed == len(tasks):
            job_status = "completed" if failed == 0 else "partial"

        job = db.query(Job).filter(Job.id == job_id, Job.trace_id == trace_id).first()
        if job:
            job.status = job_status
            job.updated_at = datetime.utcnow()
            db.commit()

        db.close()

        # Publish WebSocket update
        publish_websocket_update(job_id, trace_id, job_status, result)

        # If job is complete, aggregate and publish final results
        if job_status in ["completed", "partial"]:
            aggregated = aggregate_results(job_id, trace_id)
            publish_websocket_update(job_id, trace_id, job_status, json.dumps(aggregated))

    except Exception as e:
        logger.error(f"Failed to process result: {e}")


def main():
    """Main consumer loop"""
    logger.info("Starting Result Aggregator...")

    # Create Kafka consumer for results
    consumer = None
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            consumer = KafkaConsumer(
                RESULTS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',  # Start from beginning to catch all results
                enable_auto_commit=True,
                group_id='result-aggregator-group'
            )
            logger.info(f"Connected to Kafka, subscribed to {RESULTS_TOPIC}")
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(5)

    if not consumer:
        logger.error("Failed to connect to Kafka after maximum retries")
        return

    logger.info("Result Aggregator ready, listening for results...")

    # Consume messages
    try:
        for message in consumer:
            try:
                result_data = message.value
                process_result(result_data)
            except Exception as e:
                logger.error(f"Error processing result message: {e}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if consumer:
            consumer.close()


if __name__ == "__main__":
    main()
