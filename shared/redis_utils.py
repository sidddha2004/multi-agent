"""
Shared Redis utilities for distributed systems
"""
import redis
import json
import logging
import uuid
from typing import Optional, Any
from contextlib import contextmanager
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
redis_client = redis.from_url(REDIS_URL)


class DistributedLock:
    """Distributed lock using Redis"""

    def __init__(self, lock_key: str, ttl: int = 300):
        """
        Initialize distributed lock

        Args:
            lock_key: Unique identifier for the lock
            ttl: Time to live in seconds (default 5 minutes)
        """
        self.lock_key = f"lock:{lock_key}"
        self.ttl = ttl
        self.lock_value = None
        self.acquired = False

    def acquire(self, timeout: int = 10) -> bool:
        """
        Acquire the lock with timeout

        Args:
            timeout: How long to wait for lock acquisition (seconds)

        Returns:
            bool: True if lock acquired, False otherwise
        """
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            try:
                # Generate unique lock value
                self.lock_value = str(uuid.uuid4())

                # Try to acquire lock (SET NX EX)
                acquired = redis_client.set(
                    self.lock_key,
                    self.lock_value,
                    nx=True,  # Only set if not exists
                    ex=self.ttl  # Expire after TTL
                )

                if acquired:
                    self.acquired = True
                    logger.info(f"Lock acquired: {self.lock_key}")
                    return True

                # Lock exists, wait and retry
                import time
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Lock acquisition error: {e}")
                return False

        logger.warning(f"Lock timeout: {self.lock_key}")
        return False

    def release(self) -> bool:
        """
        Release the lock if held by this instance

        Returns:
            bool: True if lock released, False otherwise
        """
        if not self.acquired:
            return False

        try:
            # Use Lua script to safely release only if we own the lock
            lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
            """

            result = redis_client.eval(
                lua_script,
                1,  # Number of keys
                self.lock_key,
                self.lock_value
            )

            if result:
                logger.info(f"Lock released: {self.lock_key}")
                self.acquired = False
                return True
            else:
                logger.warning(f"Lock release failed (not owned): {self.lock_key}")
                return False

        except Exception as e:
            logger.error(f"Lock release error: {e}")
            return False

    def extend(self, additional_time: int = None) -> bool:
        """
        Extend lock TTL if we still own it

        Args:
            additional_time: Additional seconds to extend (default uses original TTL)

        Returns:
            bool: True if extended, False otherwise
        """
        if not self.acquired:
            return False

        try:
            extend_time = additional_time or self.ttl

            # Use Lua script to safely extend only if we own the lock
            lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("expire", KEYS[1], ARGV[2])
                else
                    return 0
                end
            """

            result = redis_client.eval(
                lua_script,
                1,
                self.lock_key,
                self.lock_value,
                extend_time
            )

            if result:
                logger.info(f"Lock extended: {self.lock_key} by {extend_time}s")
                return True
            else:
                logger.warning(f"Lock extend failed (not owned): {self.lock_key}")
                return False

        except Exception as e:
            logger.error(f"Lock extend error: {e}")
            return False

    def __enter__(self):
        """Context manager entry"""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()


@contextmanager
def task_lock(task_id: int, trace_id: str, ttl: int = 300):
    """
    Context manager for task locking

    Args:
        task_id: Task ID to lock
        trace_id: Trace ID for lock uniqueness
        ttl: Lock time to live in seconds

    Yields:
        DistributedLock: The acquired lock
    """
    lock_key = f"task:{task_id}:{trace_id}"
    lock = DistributedLock(lock_key, ttl)

    try:
        if lock.acquire():
            yield lock
        else:
            raise Exception(f"Could not acquire lock for task {task_id}")
    finally:
        lock.release()


def acquire_task_lock(task_id: int, trace_id: str, ttl: int = 300, timeout: int = 10) -> Optional[DistributedLock]:
    """
    Acquire task lock with timeout

    Args:
        task_id: Task ID to lock
        trace_id: Trace ID for lock uniqueness
        ttl: Lock time to live in seconds
        timeout: How long to wait for lock

    Returns:
        DistributedLock if acquired, None otherwise
    """
    lock_key = f"task:{task_id}:{trace_id}"
    lock = DistributedLock(lock_key, ttl)

    if lock.acquire(timeout):
        return lock
    return None


def is_task_locked(task_id: int, trace_id: str) -> bool:
    """
    Check if task is currently locked

    Args:
        task_id: Task ID to check
        trace_id: Trace ID for lock uniqueness

    Returns:
        bool: True if locked, False otherwise
    """
    lock_key = f"task:{task_id}:{trace_id}"
    try:
        return redis_client.exists(lock_key) > 0
    except Exception as e:
        logger.error(f"Lock check error: {e}")
        return False


def get_task_lock_info(task_id: int, trace_id: str) -> Optional[dict]:
    """
    Get information about task lock

    Args:
        task_id: Task ID to check
        trace_id: Trace ID for lock uniqueness

    Returns:
        dict with lock info or None if not locked
    """
    lock_key = f"task:{task_id}:{trace_id}"
    try:
        if redis_client.exists(lock_key):
            ttl = redis_client.ttl(lock_key)
            return {
                "locked": True,
                "lock_key": lock_key,
                "remaining_ttl": ttl,
                "expires_in": timedelta(seconds=ttl) if ttl > 0 else "expired"
            }
        return {"locked": False}
    except Exception as e:
        logger.error(f"Lock info error: {e}")
        return None


# Workflow State Management Functions

def set_workflow_state(job_id: int, state: dict, ttl: int = 3600):
    """Store workflow execution state in Redis"""
    state_key = f"workflow:{job_id}"
    try:
        redis_client.setex(
            state_key,
            ttl,
            json.dumps({
                "state": state,
                "updated_at": datetime.utcnow().isoformat()
            })
        )
        logger.info(f"Workflow state stored: {state_key}")
    except Exception as e:
        logger.error(f"Workflow state storage error: {e}")


def get_workflow_state(job_id: int) -> Optional[dict]:
    """Get workflow execution state from Redis"""
    state_key = f"workflow:{job_id}"
    try:
        data = redis_client.get(state_key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Workflow state retrieval error: {e}")
        return None


def update_task_status(task_id: int, status: str, trace_id: str, ttl: int = 3600):
    """Update task status in Redis"""
    status_key = f"task:{task_id}:status"
    try:
        redis_client.setex(
            status_key,
            ttl,
            json.dumps({
                "task_id": task_id,
                "trace_id": trace_id,
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            })
        )
    except Exception as e:
        logger.error(f"Task status update error: {e}")


def get_task_status(task_id: int) -> Optional[dict]:
    """Get task status from Redis"""
    status_key = f"task:{task_id}:status"
    try:
        data = redis_client.get(status_key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Task status retrieval error: {e}")
        return None


# Result Cache Functions

def cache_result(result_hash: str, result: dict, ttl: int = 1800):
    """Cache completed task result"""
    cache_key = f"result:{result_hash}"
    try:
        redis_client.setex(
            cache_key,
            ttl,
            json.dumps({
                "result": result,
                "cached_at": datetime.utcnow().isoformat()
            })
        )
        logger.info(f"Result cached: {cache_key}")
    except Exception as e:
        logger.error(f"Result caching error: {e}")


def get_cached_result(result_hash: str) -> Optional[dict]:
    """Get cached result"""
    cache_key = f"result:{result_hash}"
    try:
        data = redis_client.get(cache_key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.error(f"Cached result retrieval error: {e}")
        return None


def generate_result_hash(task_data: dict) -> str:
    """Generate hash for result caching"""
    import hashlib
    canonical_string = json.dumps(task_data, sort_keys=True)
    return hashlib.md5(canonical_string.encode()).hexdigest()
