"""
Memory Integration Module for SecureAI Agents

Provides easy-to-use functions for agents to interact with the long-term memory system.
"""

import os
import logging
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Configuration
MEMORY_MANAGER_URL = os.getenv("MEMORY_MANAGER_URL", "http://memory-manager:8005")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryIntegration:
    """Integration class for agents to interact with memory system"""

    def __init__(self, agent_type: str):
        """
        Initialize memory integration for an agent

        Args:
            agent_type: Type of agent (research, browser, sql, email, etc.)
        """
        self.agent_type = agent_type
        self.memory_url = MEMORY_MANAGER_URL

    async def store_result(
        self,
        result: str,
        job_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store agent result in long-term memory

        Args:
            result: The result content to store
            job_id: Associated job ID
            trace_id: Associated trace ID
            metadata: Additional metadata

        Returns:
            Success status
        """
        try:
            payload = {
                "content": result,
                "agent_type": self.agent_type,
                "job_id": job_id,
                "trace_id": trace_id,
                "metadata": metadata or {}
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.memory_url}/memory/store",
                    json=payload
                )
                response.raise_for_status()

                logger.info(f"Stored result in memory for job {job_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to store result in memory: {e}")
            return False

    async def retrieve_context(
        self,
        query: str,
        limit: int = 5,
        job_id: Optional[int] = None,
        agent_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from memory

        Args:
            query: Query to search for
            limit: Maximum number of results
            job_id: Optional job ID filter
            agent_type: Optional agent type filter

        Returns:
            List of relevant memories
        """
        try:
            payload = {
                "query": query,
                "limit": limit,
                "agent_type": agent_type or self.agent_type,
                "job_id": job_id
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.memory_url}/memory/retrieve",
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                memories = result.get("memories", [])

                logger.info(f"Retrieved {len(memories)} memories for query: {query[:50]}...")
                return memories

        except Exception as e:
            logger.error(f"Failed to retrieve context from memory: {e}")
            return []

    async def get_job_history(self, job_id: int) -> List[Dict[str, Any]]:
        """
        Get all memories associated with a specific job

        Args:
            job_id: Job ID to get history for

        Returns:
            List of job-related memories
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.memory_url}/memory/job/{job_id}"
                )
                response.raise_for_status()

                result = response.json()
                memories = result.get("memories", [])

                logger.info(f"Retrieved {len(memories)} memories for job {job_id}")
                return memories

        except Exception as e:
            logger.error(f"Failed to get job history: {e}")
            return []

    async def enhance_task_with_memory(
        self,
        task_description: str,
        job_id: Optional[int] = None
    ) -> str:
        """
        Enhance task description with relevant context from memory

        Args:
            task_description: Original task description
            job_id: Optional job ID for context

        Returns:
            Enhanced task description with context
        """
        try:
            # Retrieve relevant context
            memories = await self.retrieve_context(
                query=task_description,
                limit=3,
                job_id=job_id
            )

            if not memories:
                return task_description

            # Build enhanced description
            context_parts = []
            for memory in memories[:2]:  # Use top 2 relevant memories
                if memory.get("score", 0) > 0.75:  # Only use high-confidence matches
                    context_parts.append(f"- Previous: {memory['content'][:200]}...")

            if context_parts:
                enhanced = f"{task_description}\n\nRelevant Context:\n" + "\n".join(context_parts)
                return enhanced
            else:
                return task_description

        except Exception as e:
            logger.error(f"Failed to enhance task with memory: {e}")
            return task_description

    async def check_health(self) -> bool:
        """
        Check if memory system is healthy

        Returns:
            Health status
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.memory_url}/health")
                response.raise_for_status()
                return response.json().get("status") == "healthy"
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            return False


# Helper functions for easy integration
def create_memory_integration(agent_type: str) -> MemoryIntegration:
    """Create memory integration instance for an agent"""
    return MemoryIntegration(agent_type)


async def store_research_result(
    result: str,
    job_id: Optional[int] = None,
    trace_id: Optional[str] = None,
    research_topic: Optional[str] = None
) -> bool:
    """
    Helper function to store research results

    Args:
        result: Research result content
        job_id: Associated job ID
        trace_id: Associated trace ID
        research_topic: Optional research topic

    Returns:
        Success status
    """
    integration = MemoryIntegration("research")

    metadata = {}
    if research_topic:
        metadata["research_topic"] = research_topic
        metadata["task_type"] = "research"

    return await integration.store_result(
        result=result,
        job_id=job_id,
        trace_id=trace_id,
        metadata=metadata
    )


async def retrieve_research_context(
    query: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Helper function to retrieve research context

    Args:
        query: Query to search for
        limit: Maximum number of results

    Returns:
        List of relevant research memories
    """
    integration = MemoryIntegration("research")
    return await integration.retrieve_context(query, limit)


# Example usage for testing
async def test_memory_integration():
    """Test the memory integration"""
    print("Testing Memory Integration...")

    # Create integration for research agent
    research_memory = MemoryIntegration("research")

    # Test health
    health = await research_memory.check_health()
    print(f"Memory system health: {health}")

    if not health:
        print("❌ Memory system is not healthy")
        return False

    # Test storing a result
    store_success = await research_memory.store_result(
        result="Research findings about quantum computing: Quantum supremacy was achieved in 2019...",
        job_id=1,
        trace_id="test-trace-123",
        metadata={"topic": "quantum_computing", "task_type": "research"}
    )
    print(f"Store result: {store_success}")

    # Test retrieving context
    memories = await research_memory.retrieve_context(
        query="quantum computing developments",
        limit=3
    )
    print(f"Retrieved {len(memories)} memories")

    # Test task enhancement
    enhanced = await research_memory.enhance_task_with_memory(
        task_description="Research recent advances in quantum computing",
        job_id=1
    )
    print(f"Enhanced task: {enhanced[:200]}...")

    print("✅ Memory integration test passed!")
    return True


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_memory_integration())
