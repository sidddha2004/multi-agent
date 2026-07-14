import json
import logging
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any
import re

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from dotenv import load_dotenv

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TASKS_TOPIC = os.getenv("TASKS_TOPIC", "tasks.email")
RESULTS_TOPIC = os.getenv("RESULTS_TOPIC", "results")
RETRY_TOPIC = os.getenv("RETRY_TOPIC", "tasks.retry")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "tasks.dead_letter")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # seconds
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Email Configuration (use environment variables in production)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@secureai.com")

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
    """Task model"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")
    agent_type = Column(String, default="email")
    result = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


def get_db():
    """Get database session"""
    db = Session()
    try:
        return db
    finally:
        pass


def update_task_status(task_id: int, trace_id: str, status: str, result: str = None):
    """Update task status in database"""
    try:
        db = get_db()
        task = db.query(Task).filter(Task.id == task_id, Task.trace_id == trace_id).first()

        if task:
            task.status = status
            if result:
                task.result = result
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Updated task {task_id} ({trace_id}) to {status}")
        else:
            logger.warning(f"Task {task_id} ({trace_id}) not found in database")

        db.close()
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")


def update_job_status(job_id: int, trace_id: str, status: str):
    """Update job status in database"""
    try:
        db = get_db()
        job = db.query(Job).filter(Job.id == job_id, Job.trace_id == trace_id).first()

        if job:
            job.status = status
            job.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Updated job {job_id} ({trace_id}) to {status}")
        else:
            logger.warning(f"Job {job_id} ({trace_id}) not found in database")

        db.close()
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")


def send_heartbeat():
    """Send heartbeat to Redis"""
    try:
        redis_client = redis.from_url(REDIS_URL)
        agent_key = f"heartbeat:email-agent"

        heartbeat_data = {
            "agent_type": "email",
            "status": "active",
            "timestamp": datetime.utcnow().isoformat(),
            "topic": TASKS_TOPIC
        }

        # Set with expiry (2x heartbeat interval)
        redis_client.setex(
            agent_key,
            HEARTBEAT_INTERVAL * 2,
            json.dumps(heartbeat_data)
        )

        logger.debug(f"Heartbeat sent: {agent_key}")

    except Exception as e:
        logger.error(f"Failed to send heartbeat: {e}")


def heartbeat_loop():
    """Background heartbeat loop"""
    while True:
        send_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)


def parse_email_request(description: str) -> Dict[str, Any]:
    """Parse email request using LLM or regex"""
    if not OPENAI_API_KEY:
        # Simple regex-based parsing
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        emails = re.findall(email_pattern, description)

        return {
            "to": emails,
            "subject": "AI Generated Email",
            "body": description,
            "parsed": len(emails) > 0
        }

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=OPENAI_API_KEY
        )

        system_prompt = """Extract email details from the user request.
Return JSON format:
{
    "to": ["email1@example.com", "email2@example.com"],
    "subject": "Email subject",
    "body": "Email body content"
}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": description}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=500
        )

        result = json.loads(response.choices[0].message.content)
        result["parsed"] = True
        return result

    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return {
            "to": [],
            "subject": "Parse Error",
            "body": str(e),
            "parsed": False
        }


def send_email(to: list, subject: str, body: str) -> Dict[str, Any]:
    """Send email using SMTP"""
    try:
        if not SMTP_USER or not SMTP_PASSWORD:
            return {
                "success": False,
                "message": "Email credentials not configured. Set SMTP_USER and SMTP_PASSWORD environment variables."
            }

        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = ', '.join(to)
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        return {
            "success": True,
            "message": f"Email sent to {len(to)} recipients",
            "recipients": to
        }

    except Exception as e:
        logger.error(f"Email sending error: {e}")
        return {
            "success": False,
            "message": f"Failed to send email: {str(e)}"
        }


def publish_result(task_id: int, job_id: int, trace_id: str, result: str, agent_type: str, producer: KafkaProducer, correlation_id: str = None):
    """Publish result to Kafka results topic"""
    try:
        result_message = {
            "task_id": task_id,
            "job_id": job_id,
            "trace_id": trace_id,
            "correlation_id": correlation_id or trace_id,
            "result": result,
            "agent_type": agent_type,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed"
        }

        producer.send(RESULTS_TOPIC, value=result_message)
        producer.flush()

        logger.info(f"Published result for task {task_id} ({trace_id}) to {RESULTS_TOPIC}")
    except Exception as e:
        logger.error(f"Failed to publish result: {e}")


def send_to_retry_queue(task_message: Dict[str, Any], error_message: str, producer: KafkaProducer):
    """Send failed task to retry queue"""
    try:
        retry_count = task_message.get("retry_count", 0)

        retry_message = {
            "task_id": task_message.get("task_id"),
            "job_id": task_message.get("job_id"),
            "trace_id": task_message.get("trace_id"),
            "correlation_id": task_message.get("correlation_id", task_message.get("trace_id")),
            "description": task_message.get("description"),
            "agent_type": task_message.get("agent_type", "email"),
            "original_topic": TASKS_TOPIC,
            "error_message": error_message,
            "retry_count": retry_count + 1,
            "max_retries": MAX_RETRIES,
            "timestamp": datetime.utcnow().isoformat()
        }

        producer.send(RETRY_TOPIC, value=retry_message)
        producer.flush()

        logger.warning(f"Task {task_message.get('task_id')} sent to retry queue (attempt {retry_count + 1}/{MAX_RETRIES})")

    except Exception as e:
        logger.error(f"Failed to send task to retry queue: {e}")


def process_task(task_message: Dict[str, Any], producer: KafkaProducer):
    """Process a single email task with retry logic"""
    task_id = task_message.get("task_id")
    job_id = task_message.get("job_id")
    trace_id = task_message.get("trace_id")
    correlation_id = task_message.get("correlation_id", trace_id)
    description = task_message.get("description")
    agent_type = task_message.get("agent_type", "email")
    is_retry = task_message.get("is_retry", False)
    retry_count = task_message.get("retry_count", 0)

    logger.info(f"Processing email task {task_id} for job {job_id} (trace_id: {trace_id}, correlation_id: {correlation_id}): {description}")
    if is_retry:
        logger.info(f"This is a retry attempt #{retry_count}")

    try:
        # Update job status to processing
        update_job_status(job_id, trace_id, "processing")

        # Update task status to processing
        update_task_status(task_id, trace_id, "processing")

        # Parse email request
        email_details = parse_email_request(description)

        if not email_details.get("parsed") or not email_details.get("to"):
            result_text = f"Failed to parse email request. Please provide recipient email addresses."
            update_task_status(task_id, trace_id, "failed", result_text)
            update_job_status(job_id, trace_id, "failed")
            return

        # Send email
        email_result = send_email(
            to=email_details["to"],
            subject=email_details.get("subject", "AI Generated Email"),
            body=email_details.get("body", description)
        )

        # Format result
        if email_result["success"]:
            result_text = f"✅ {email_result['message']}\nSubject: {email_details.get('subject')}\nRecipients: {', '.join(email_details['to'])}"
        else:
            result_text = f"❌ {email_result['message']}"

        # Update task status to completed with result
        status = "completed" if email_result["success"] else "failed"
        update_task_status(task_id, trace_id, status, result_text)

        # Publish result to results topic
        publish_result(task_id, job_id, trace_id, result_text, agent_type, producer, correlation_id)

        # Update job status
        update_job_status(job_id, trace_id, status)

        logger.info(f"Successfully processed email task {task_id} (trace_id: {trace_id}, correlation_id: {correlation_id})")

    except Exception as e:
        logger.error(f"Failed to process email task {task_id} (trace_id: {trace_id}): {e}")

        # Check if we should retry
        current_retry_count = retry_count if is_retry else 0
        if current_retry_count < MAX_RETRIES:
            logger.info(f"Sending task {task_id} to retry queue (attempt {current_retry_count + 1}/{MAX_RETRIES})")

            # Update task status to retrying
            update_task_status(task_id, trace_id, "retrying", f"Retry {current_retry_count + 1}: {str(e)}")

            # Send to retry queue
            send_to_retry_queue(task_message, str(e), producer)
        else:
            logger.error(f"Task {task_id} exceeded max retries ({MAX_RETRIES}), marking as failed")

            # Update status to failed
            update_task_status(task_id, trace_id, "failed", f"Failed after {MAX_RETRIES} retries: {str(e)}")
            update_job_status(job_id, trace_id, "failed")


def main():
    """Main consumer loop"""
    logger.info("Starting Email Agent...")

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    logger.info(f"Heartbeat thread started (interval: {HEARTBEAT_INTERVAL}s)")

    # Create Kafka producer for results
    producer = None
    producer_retry_count = 0
    max_producer_retries = 10

    while producer_retry_count < max_producer_retries:
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
            logger.info("Kafka producer created")
            break
        except Exception as e:
            producer_retry_count += 1
            logger.warning(f"Failed to create producer (attempt {producer_retry_count}/{max_producer_retries}): {e}")
            if producer_retry_count < max_producer_retries:
                time.sleep(5)

    if not producer:
        logger.error("Failed to create producer after maximum retries")
        return

    # Create Kafka consumer for tasks
    consumer = None
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            consumer = KafkaConsumer(
                TASKS_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='email-agent-group'
            )
            logger.info(f"Connected to Kafka, subscribed to {TASKS_TOPIC}")
            break
        except Exception as e:
            retry_count += 1
            logger.warning(f"Failed to connect to Kafka (attempt {retry_count}/{max_retries}): {e}")
            time.sleep(5)

    if not consumer:
        logger.error("Failed to connect to Kafka after maximum retries")
        return

    logger.info("Email Agent ready, waiting for tasks...")

    # Consume messages
    try:
        for message in consumer:
            try:
                task_data = message.value
                process_task(task_data, producer)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if consumer:
            consumer.close()
        if producer:
            producer.close()


if __name__ == "__main__":
    main()
