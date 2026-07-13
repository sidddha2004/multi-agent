"""
Qdrant Long-term Memory Manager for SecureAI

Provides persistent memory across sessions using vector embeddings.
Enables agents to remember and retrieve past research, analysis, and context.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)

import openai
from openai import OpenAI

load_dotenv()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "secureai_memory")

# Memory configuration
MEMORY_EXPIRY_DAYS = int(os.getenv("MEMORY_EXPIRY_DAYS", "30"))  # Default 30 days
MAX_MEMORY_RESULTS = int(os.getenv("MAX_MEMORY_RESULTS", "10"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1536"))  # OpenAI small embedding dimension

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QdrantMemoryManager:
    """Manages long-term memory using Qdrant vector database"""

    def __init__(self):
        """Initialize Qdrant client and OpenAI for embeddings"""
        try:
            # Initialize Qdrant client
            if QDRANT_API_KEY:
                self.qdrant_client = QdrantClient(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY,
                    timeout=20
                )
            else:
                self.qdrant_client = QdrantClient(
                    url=QDRANT_URL,
                    timeout=20
                )

            # Initialize OpenAI client
            self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

            # Create collection if it doesn't exist
            self._ensure_collection_exists()

            logger.info("QdrantMemoryManager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize QdrantMemoryManager: {e}")
            raise

    def _ensure_collection_exists(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_exists = any(
                collection.name == COLLECTION_NAME
                for collection in collections
            )

            if not collection_exists:
                logger.info(f"Creating collection: {COLLECTION_NAME}")
                self.qdrant_client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Collection {COLLECTION_NAME} created successfully")
            else:
                logger.info(f"Collection {COLLECTION_NAME} already exists")

        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def store_memory(
        self,
        content: str,
        metadata: Dict[str, Any],
        job_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> str:
        """
        Store a memory in Qdrant

        Args:
            content: The content to store
            metadata: Additional metadata (task_type, result, etc.)
            job_id: Optional job ID for reference
            trace_id: Optional trace ID for reference
            agent_type: Optional agent type for categorization

        Returns:
            memory_id: The ID of the stored memory
        """
        try:
            # Generate embedding
            embedding = self._generate_embedding(content)

            # Generate unique memory ID
            memory_id = f"memory_{datetime.utcnow().timestamp()}_{job_id or 'no_job'}"

            # Prepare point structure
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload={
                    "content": content,
                    "job_id": job_id,
                    "trace_id": trace_id,
                    "agent_type": agent_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "expiry_date": (datetime.utcnow() + timedelta(days=MEMORY_EXPIRY_DAYS)).isoformat(),
                    **metadata
                }
            )

            # Store in Qdrant
            self.qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=[point]
            )

            logger.info(f"Stored memory {memory_id} for job {job_id}")
            return memory_id

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise

    def retrieve_memories(
        self,
        query: str,
        limit: int = MAX_MEMORY_RESULTS,
        agent_type: Optional[str] = None,
        job_id: Optional[int] = None,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories based on query

        Args:
            query: The query to search for
            limit: Maximum number of results to return
            agent_type: Filter by agent type
            job_id: Filter by job ID
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of relevant memories with scores
        """
        try:
            # Generate query embedding
            query_embedding = self._generate_embedding(query)

            # Build filter if specified
            query_filter = None
            if agent_type or job_id:
                conditions = []
                if agent_type:
                    conditions.append(
                        FieldCondition(
                            key="agent_type",
                            match=MatchValue(value=agent_type)
                        )
                    )
                if job_id:
                    conditions.append(
                        FieldCondition(
                            key="job_id",
                            match=MatchValue(value=job_id)
                        )
                    )
                if conditions:
                    query_filter = Filter(must=conditions)

            # Search in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold
            )

            # Format results
            memories = []
            for result in search_results:
                memory = {
                    "id": result.id,
                    "score": result.score,
                    "content": result.payload.get("content"),
                    "job_id": result.payload.get("job_id"),
                    "trace_id": result.payload.get("trace_id"),
                    "agent_type": result.payload.get("agent_type"),
                    "timestamp": result.payload.get("timestamp"),
                    **{k: v for k, v in result.payload.items()
                       if k not in ["content", "job_id", "trace_id", "agent_type", "timestamp", "expiry_date"]}
                }
                memories.append(memory)

            logger.info(f"Retrieved {len(memories)} memories for query: {query[:50]}...")
            return memories

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    def get_memories_by_job(self, job_id: int) -> List[Dict[str, Any]]:
        """Get all memories associated with a specific job"""
        try:
            # Search with job filter
            results = self.qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="job_id",
                            match=MatchValue(value=job_id)
                        )
                    ]
                ),
                limit=100
            )

            memories = []
            for point in results[0]:
                memory = {
                    "id": point.id,
                    "content": point.payload.get("content"),
                    "job_id": point.payload.get("job_id"),
                    "trace_id": point.payload.get("trace_id"),
                    "agent_type": point.payload.get("agent_type"),
                    "timestamp": point.payload.get("timestamp"),
                    **{k: v for k, v in point.payload.items()
                       if k not in ["content", "job_id", "trace_id", "agent_type", "timestamp", "expiry_date"]}
                }
                memories.append(memory)

            return memories

        except Exception as e:
            logger.error(f"Failed to get memories by job: {e}")
            return []

    def delete_expired_memories(self) -> int:
        """Delete memories that have expired"""
        try:
            now = datetime.utcnow()
            expiry_count = 0

            # Scroll through all memories
            results = self.qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000
            )

            expired_ids = []
            for point in results[0]:
                expiry_date_str = point.payload.get("expiry_date")
                if expiry_date_str:
                    expiry_date = datetime.fromisoformat(expiry_date_str)
                    if expiry_date < now:
                        expired_ids.append(point.id)

            # Delete expired memories
            if expired_ids:
                self.qdrant_client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=expired_ids
                )
                expiry_count = len(expired_ids)
                logger.info(f"Deleted {expiry_count} expired memories")

            return expiry_count

        except Exception as e:
            logger.error(f"Failed to delete expired memories: {e}")
            return 0

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories"""
        try:
            collection_info = self.qdrant_client.get_collection(COLLECTION_NAME)

            stats = {
                "total_memories": collection_info.points_count,
                "vector_dimension": collection_info.config.params.vectors.size,
                "collection_name": COLLECTION_NAME,
                "memory_expiry_days": MEMORY_EXPIRY_DAYS,
                "max_results": MAX_MEMORY_RESULTS
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}

    def clear_all_memories(self) -> bool:
        """Clear all memories from the collection"""
        try:
            self.qdrant_client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=Filter()
            )
            logger.warning("Cleared all memories from collection")
            return True

        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
            return False


# Global memory manager instance
memory_manager = None

def get_memory_manager() -> QdrantMemoryManager:
    """Get or create global memory manager instance"""
    global memory_manager
    if memory_manager is None:
        memory_manager = QdrantMemoryManager()
    return memory_manager


# Health check
def health_check() -> Dict[str, Any]:
    """Check if memory manager is healthy"""
    try:
        manager = get_memory_manager()
        stats = manager.get_memory_stats()

        return {
            "status": "healthy",
            "qdrant_connected": True,
            "openai_connected": True,
            "stats": stats
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "qdrant_connected": False,
            "openai_connected": False
        }


if __name__ == "__main__":
    # Test the memory manager
    print("Testing Qdrant Memory Manager...")

    try:
        manager = get_memory_manager()
        print("✅ Memory manager initialized")

        # Test health
        health = health_check()
        print(f"✅ Health check: {health['status']}")

        # Test storing memory
        memory_id = manager.store_memory(
            content="Test memory about quantum computing research",
            metadata={"task_type": "research", "topic": "quantum_computing"},
            job_id=1,
            agent_type="research"
        )
        print(f"✅ Stored test memory: {memory_id}")

        # Test retrieving memories
        memories = manager.retrieve_memories("quantum computing research")
        print(f"✅ Retrieved {len(memories)} memories")

        # Get stats
        stats = manager.get_memory_stats()
        print(f"✅ Memory stats: {stats}")

        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
