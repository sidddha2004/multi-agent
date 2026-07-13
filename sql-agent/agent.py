import json
import logging
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from dotenv import load_dotenv

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
TASKS_TOPIC = os.getenv("TASKS_TOPIC", "tasks.sql")
RESULTS_TOPIC = os.getenv("RESULTS_TOPIC", "results")
RETRY_TOPIC = os.getenv("RETRY_TOPIC", "tasks.retry")
DLQ_TOPIC = os.getenv("DLQ_TOPIC", "tasks.dead_letter")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # seconds
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
    """Task model"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")
    agent_type = Column(String, default="sql")
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
        agent_key = f"heartbeat:sql-agent"

        heartbeat_data = {
            "agent_type": "sql",
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


def get_database_schema() -> str:
    """Get database schema information"""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        schema_info = []
        for table in tables:
            columns = inspector.get_columns(table)
            column_info = [f"{col['name']} ({col['type']})" for col in columns]
            schema_info.append(f"{table}: {', '.join(column_info)}")

        return "\n".join(schema_info)

    except Exception as e:
        logger.error(f"Failed to get schema: {e}")
        return "Unable to retrieve schema"


def execute_safe_query(query: str) -> List[Dict[str, Any]]:
    """Execute a safe read-only query"""
    try:
        # Only allow SELECT queries
        query = query.strip()
        if not query.upper().startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed for security")

        with engine.connect() as connection:
            result = connection.execute(query)
            columns = result.keys()
            rows = result.fetchall()

            # Convert to list of dictionaries
            results = [dict(zip(columns, row)) for row in rows]

            return results

    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise


def generate_sql_query(description: str, schema: str) -> str:
    """Generate SQL query using LLM"""
    if not OPENAI_API_KEY:
        # Fallback: simple extraction
        if "SELECT" in description.upper():
            return description
        else:
            return "SELECT 'Please provide OpenAI API key for natural language query generation' as message"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        system_prompt = f"""You are a SQL expert. Convert natural language requests into SQL queries.
Available schema:\n{schema}

Return ONLY the SQL query, no explanations. Only SELECT queries are allowed for security.
If the request cannot be fulfilled with a SELECT query, return a helpful message."""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": description}
            ],
            temperature=0.1,
            max_tokens=500
        )

        query = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if query.startswith("```"):
            query = query.split("```")[1].replace("sql", "").replace("SQL", "").strip()

        return query

    except Exception as e:
        logger.error(f"LLM Error: {e}")
        return "SELECT 'Failed to generate query' as message"


def format_results(results: List[Dict[str, Any]], max_rows: int = 10) -> str:
    """Format query results for display"""
    if not results:
        return "No results found"

    formatted = []
    formatted.append(f"Query returned {len(results)} rows:\n")

    # Headers
    headers = list(results[0].keys())
    formatted.append(" | ".join(headers))
    formatted.append("-" * 80)

    # Data rows
    for i, row in enumerate(results[:max_rows]):
        row_str = " | ".join(str(row.get(h, "")) for h in headers)
        formatted.append(row_str)

    if len(results) > max_rows:
        formatted.append(f"\n... and {len(results) - max_rows} more rows")

    return "\n".join(formatted)


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
            "agent_type": task_message.get("agent_type", "sql"),
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
    """Process a single SQL task with retry logic"""
    task_id = task_message.get("task_id")
    job_id = task_message.get("job_id")
    trace_id = task_message.get("trace_id")
    correlation_id = task_message.get("correlation_id", trace_id)
    description = task_message.get("description")
    agent_type = task_message.get("agent_type", "sql")
    is_retry = task_message.get("is_retry", False)
    retry_count = task_message.get("retry_count", 0)

    logger.info(f"Processing SQL task {task_id} for job {job_id} (trace_id: {trace_id}, correlation_id: {correlation_id}): {description}")
    if is_retry:
        logger.info(f"This is a retry attempt #{retry_count}")

    try:
        # Update job status to processing
        update_job_status(job_id, trace_id, "processing")

        # Update task status to processing
        update_task_status(task_id, trace_id, "processing")

        # Get database schema
        schema = get_database_schema()

        # Generate SQL query
        query = generate_sql_query(description, schema)

        # Execute query
        try:
            results = execute_safe_query(query)
            result_text = format_results(results)
        except Exception as e:
            result_text = f"Query execution failed: {str(e)}"

        # Update task status to completed with result
        update_task_status(task_id, trace_id, "completed", result_text)

        # Publish result to results topic
        publish_result(task_id, job_id, trace_id, result_text, agent_type, producer, correlation_id)

        # Update job status to completed
        update_job_status(job_id, trace_id, "completed")

        logger.info(f"Successfully completed SQL task {task_id} (trace_id: {trace_id}, correlation_id: {correlation_id})")

    except Exception as e:
        logger.error(f"Failed to process SQL task {task_id} (trace_id: {trace_id}): {e}")

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
    logger.info("Starting SQL Agent...")

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
                group_id='sql-agent-group'
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

    logger.info("SQL Agent ready, waiting for tasks...")

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
