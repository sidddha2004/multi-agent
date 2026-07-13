import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
RETRY_TOPIC = os.getenv("RETRY_TOPIC", "tasks.retry")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "tasks.dead_letter")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min

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


class FailedTask(Base):
    """Failed task tracking"""
    __tablename__ = "failed_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False)
    job_id = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False, index=True)
    correlation_id = Column(String, index=True)
    original_topic = Column(String, nullable=False)
    agent_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    status = Column(String, default="pending_retry")  # pending_retry, moved_to_dlq, manual_intervention
    next_retry_at = Column(DateTime)
    last_attempt_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = Session()
    try:
        return db
    finally:
        pass


def save_failed_task(task_message: Dict[str, Any], error_message: str, retry_count: int = 0):
    """Save failed task to database"""
    try:
        db = get_db()

        # Check if task already exists
        existing = db.query(FailedTask).filter(
            FailedTask.task_id == task_message.get("task_id"),
            FailedTask.trace_id == task_message.get("trace_id")
        ).first()

        if existing:
            # Update retry count and schedule
            existing.retry_count = retry_count
            existing.error_message = error_message
            existing.last_attempt_at = datetime.utcnow()

            # Calculate next retry time
            if retry_count < len(RETRY_DELAYS):
                existing.next_retry_at = datetime.utcnow() + timedelta(seconds=RETRY_DELAYS[retry_count])
                existing.status = "pending_retry"
            else:
                existing.status = "moved_to_dlq"
                existing.next_retry_at = None

            db.commit()
            logger.info(f"Updated failed task {task_message.get('task_id')} - retry #{retry_count}")
        else:
            # Create new failed task record
            failed_task = FailedTask(
                task_id=task_message.get("task_id"),
                job_id=task_message.get("job_id"),
                trace_id=task_message.get("trace_id"),
                correlation_id=task_message.get("correlation_id"),
                original_topic=task_message.get("original_topic", "unknown"),
                agent_type=task_message.get("agent_type", "unknown"),
                description=task_message.get("description", ""),
                error_message=error_message,
                retry_count=retry_count,
                next_retry_at=datetime.utcnow() + timedelta(seconds=RETRY_DELAYS[0]) if retry_count < len(RETRY_DELAYS) else None,
                last_attempt_at=datetime.utcnow()
            )
            db.add(failed_task)
            db.commit()
            logger.info(f"Saved new failed task {task_message.get('task_id')}")

        db.close()

    except Exception as e:
        logger.error(f"Failed to save failed task: {e}")


def send_to_dlq(task_message: Dict[str, Any], error_message: str, producer: KafkaProducer):
    """Send task to Dead Letter Queue"""
    try:
        dlq_message = {
            **task_message,
            "sent_to_dlq_at": datetime.utcnow().isoformat(),
            "error_message": error_message,
            "total_retries": task_message.get("retry_count", 0),
            "status": "dead_letter"
        }

        producer.send(DLQ_TOPIC, value=dlq_message)
        producer.flush()

        logger.warning(f"Task {task_message.get('task_id')} sent to DLQ after {task_message.get('retry_count', 0)} retries")

    except Exception as e:
        logger.error(f"Failed to send task to DLQ: {e}")


def process_retry_queue():
    """Process tasks ready for retry"""
    try:
        db = get_db()

        # Find tasks ready for retry
        ready_tasks = db.query(FailedTask).filter(
            FailedTask.status == "pending_retry",
            FailedTask.next_retry_at <= datetime.utcnow()
        ).all()

        if not ready_tasks:
            return

        logger.info(f"Found {len(ready_tasks)} tasks ready for retry")

        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=3
        )

        for task in ready_tasks:
            try:
                # Increment retry count
                new_retry_count = task.retry_count + 1

                # Create retry message
                retry_message = {
                    "task_id": task.task_id,
                    "job_id": task.job_id,
                    "trace_id": task.trace_id,
                    "correlation_id": task.correlation_id,
                    "description": task.description,
                    "agent_type": task.agent_type,
                    "original_topic": task.original_topic,
                    "retry_count": new_retry_count,
                    "max_retries": MAX_RETRIES,
                    "previous_error": task.error_message,
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Check if max retries exceeded
                if new_retry_count >= MAX_RETRIES:
                    # Send to DLQ
                    send_to_dlq(retry_message, task.error_message, producer)
                    task.status = "moved_to_dlq"
                    task.next_retry_at = None
                else:
                    # Send back to retry queue
                    producer.send(RETRY_TOPIC, value=retry_message)
                    producer.flush()

                    # Update next retry time
                    task.retry_count = new_retry_count
                    task.last_attempt_at = datetime.utcnow()

                    if new_retry_count < len(RETRY_DELAYS):
                        task.next_retry_at = datetime.utcnow() + timedelta(seconds=RETRY_DELAYS[new_retry_count])
                    else:
                        task.status = "moved_to_dlq"
                        task.next_retry_at = None

                    logger.info(f"Task {task.task_id} - retry #{new_retry_count}/{MAX_RETRIES}")

                db.commit()

            except Exception as e:
                logger.error(f"Failed to process retry for task {task.task_id}: {e}")

        producer.close()
        db.close()

    except Exception as e:
        logger.error(f"Failed to process retry queue: {e}")


def consume_retry_queue():
    """Consume messages from retry queue"""
    consumer = None
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            consumer = KafkaConsumer(
                RETRY_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='dlq-handler-group'
            )
            logger.info(f"Connected to Kafka, subscribed to {RETRY_TOPIC}")
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(5)

    if not consumer:
        logger.error("Failed to connect to Kafka after maximum retries")
        return

    producer = None
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=3
        )
    except Exception as e:
        logger.error(f"Failed to create producer: {e}")
        return

    logger.info("DLQ Handler ready, processing retry queue...")

    try:
        for message in consumer:
            try:
                task_data = message.value

                # Republish to original topic for retry
                original_topic = task_data.get("original_topic")
                if original_topic:
                    retry_message = {
                        **task_data,
                        "is_retry": True,
                        "retry_at": datetime.utcnow().isoformat()
                    }

                    producer.send(original_topic, value=retry_message)
                    producer.flush()

                    logger.info(f"Republished task {task_data.get('task_id')} to {original_topic} (retry #{task_data.get('retry_count', 0)})")
                else:
                    logger.error(f"No original topic for task {task_data.get('task_id')}, sending to DLQ")
                    send_to_dlq(task_data, "No original topic specified", producer)

            except Exception as e:
                logger.error(f"Error processing retry message: {e}")

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if consumer:
            consumer.close()
        if producer:
            producer.close()


def main():
    """Main DLQ Handler loop"""
    logger.info("Starting DLQ Handler...")

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Start retry queue processor in background
    import threading
    retry_processor = threading.Thread(target=lambda: [
        time.sleep(10),
        process_retry_queue()
    ], daemon=True)
    retry_processor.start()

    # Start retry queue consumer
    consume_retry_queue()


if __name__ == "__main__":
    main()
