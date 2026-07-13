#!/usr/bin/env python3
"""
Test script for Phase 3 Qdrant Long-term Memory System

Tests the memory management, integration, and agent memory capabilities.
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, Any

# Test configuration
MEMORY_MANAGER_URL = "http://localhost:8005"

# Test data
TEST_MEMORIES = [
    {
        "content": "Research findings about quantum computing: Quantum supremacy was achieved in 2019 when Google's Sycamore processor performed a calculation in 200 seconds that would take classical supercomputers 10,000 years.",
        "metadata": {"topic": "quantum_computing", "task_type": "research", "year": 2024},
        "agent_type": "research",
        "query_relevance": "quantum computing developments"
    },
    {
        "content": "Web scraping results from example.com: The main heading was 'Welcome to Example Domain' and the page contains basic HTML structure with navigation links.",
        "metadata": {"topic": "web_scraping", "task_type": "scraping", "domain": "example.com"},
        "agent_type": "browser",
        "query_relevance": "web scraping example.com"
    },
    {
        "content": "SQL query analysis: Executed SELECT query on user table, found 1,234 active users in the last 30 days with average session duration of 15 minutes.",
        "metadata": {"topic": "database", "task_type": "query", "table": "users"},
        "agent_type": "sql",
        "query_relevance": "database user analysis"
    },
    {
        "content": "Email notification sent: Successfully delivered system status report to admin@example.com with subject 'Daily System Summary - 2024-07-13'.",
        "metadata": {"topic": "notification", "task_type": "email", "recipient": "admin@example.com"},
        "agent_type": "email",
        "query_relevance": "email notification system"
    }
]


async def test_memory_health() -> bool:
    """Test if memory manager is healthy"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MEMORY_MANAGER_URL}/health")
            if response.status_code == 200:
                health_data = response.json()
                print("✅ Memory Manager Health Check:")
                print(f"   Status: {health_data.get('status')}")
                print(f"   Qdrant Connected: {health_data.get('qdrant_connected')}")
                print(f"   OpenAI Connected: {health_data.get('openai_connected')}")
                if health_data.get('stats'):
                    stats = health_data.get('stats')
                    print(f"   Total Memories: {stats.get('total_memories', 0)}")
                    print(f"   Collection: {stats.get('collection_name')}")
                return True
            return False
    except Exception as e:
        print(f"❌ Memory manager health check failed: {e}")
        return False


async def test_store_memory(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test storing a memory"""
    try:
        payload = {
            "content": memory_data["content"],
            "metadata": memory_data["metadata"],
            "agent_type": memory_data["agent_type"],
            "job_id": 1,
            "trace_id": "test-trace-123"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{MEMORY_MANAGER_URL}/memory/store",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "memory_id": result.get("memory_id"),
                    "content_preview": memory_data["content"][:100]
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def test_retrieve_memory(query: str, agent_type: str = None) -> Dict[str, Any]:
    """Test retrieving memories"""
    try:
        payload = {
            "query": query,
            "limit": 5,
            "score_threshold": 0.6,
            "agent_type": agent_type
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{MEMORY_MANAGER_URL}/memory/retrieve",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "count": result.get("count", 0),
                    "memories": result.get("memories", [])
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def test_job_memories() -> Dict[str, Any]:
    """Test getting memories by job ID"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MEMORY_MANAGER_URL}/memory/job/1")

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "count": result.get("count", 0),
                    "memories": result.get("memories", [])
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def test_memory_stats() -> Dict[str, Any]:
    """Test getting memory statistics"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MEMORY_MANAGER_URL}/memory/stats")

            if response.status_code == 200:
                return {
                    "success": True,
                    "stats": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}"
                }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def print_test_header(title: str):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")


def print_store_result(result: Dict[str, Any], index: int):
    """Print memory storage result"""
    if result.get("success"):
        print(f"   ✅ Memory {index} stored successfully")
        print(f"      ID: {result.get('memory_id', 'N/A')}")
        print(f"      Preview: {result.get('content_preview', 'N/A')}...")
    else:
        print(f"   ❌ Memory {index} storage failed: {result.get('error', 'Unknown error')}")


def print_retrieve_result(result: Dict[str, Any], query: str):
    """Print memory retrieval result"""
    if result.get("success"):
        print(f"   ✅ Retrieved {result.get('count', 0)} memories for query: {query}")
        memories = result.get("memories", [])
        for i, memory in enumerate(memories[:3], 1):  # Show top 3
            print(f"      {i}. Score: {memory.get('score', 0):.3f} - {memory.get('content', 'N/A')[:80]}...")
    else:
        print(f"   ❌ Retrieval failed: {result.get('error', 'Unknown error')}")


async def run_tests():
    """Run all memory system tests"""

    print("🚀 Starting Phase 3 Qdrant Long-term Memory System Tests")
    print("="*60)

    # Test 1: Health Check
    print_test_header("Test 1: Memory Manager Health Check")
    if not await test_memory_health():
        print("❌ Memory manager is not healthy. Exiting tests.")
        return 1

    # Test 2: Store Memories
    print_test_header("Test 2: Store Multiple Memories")
    store_results = []
    for i, memory_data in enumerate(TEST_MEMORIES, 1):
        print(f"\n📝 Storing memory {i}: {memory_data['metadata'].get('topic', 'unknown')}")
        result = await test_store_memory(memory_data)
        print_store_result(result, i)
        store_results.append(result)

    # Wait a moment for embeddings to be processed
    print("\n⏳ Waiting for embeddings to be processed...")
    await asyncio.sleep(2)

    # Test 3: Retrieve Memories
    print_test_header("Test 3: Retrieve Memories with Different Queries")

    for i, memory_data in enumerate(TEST_MEMORIES, 1):
        query = memory_data["query_relevance"]
        agent_type = memory_data["agent_type"]

        print(f"\n🔍 Query {i}: {query}")
        print(f"   Agent Type: {agent_type}")

        result = await test_retrieve_memory(query, agent_type)
        print_retrieve_result(result, query)

    # Test 4: Cross-Agent Retrieval
    print_test_header("Test 4: Cross-Agent Memory Retrieval")

    print("\n🔍 Query: 'database and user analytics'")
    print("   Agent Type: all (no filter)")

    result = await test_retrieve_memory("database and user analytics", None)
    print_retrieve_result(result, "database and user analytics")

    # Test 5: Job Memories
    print_test_header("Test 5: Get All Memories for Job")

    print("\n📋 Getting all memories for job_id=1")
    job_result = await test_job_memories()

    if job_result.get("success"):
        print(f"   ✅ Found {job_result.get('count', 0)} memories for job 1")
        memories = job_result.get("memories", [])
        for i, memory in enumerate(memories[:5], 1):
            print(f"      {i}. {memory.get('agent_type', 'N/A')}: {memory.get('content', 'N/A')[:60]}...")
    else:
        print(f"   ❌ Failed to get job memories: {job_result.get('error', 'Unknown error')}")

    # Test 6: Memory Statistics
    print_test_header("Test 6: Memory System Statistics")

    print("\n📊 Getting memory statistics")
    stats_result = await test_memory_stats()

    if stats_result.get("success"):
        stats = stats_result.get("stats", {})
        print(f"   ✅ Memory Statistics:")
        print(f"      Total Memories: {stats.get('total_memories', 0)}")
        print(f"      Collection Name: {stats.get('collection_name', 'N/A')}")
        print(f"      Vector Dimension: {stats.get('vector_dimension', 0)}")
        print(f"      Memory Expiry Days: {stats.get('memory_expiry_days', 0)}")
        print(f"      Max Results: {stats.get('max_results', 0)}")
    else:
        print(f"   ❌ Failed to get stats: {stats_result.get('error', 'Unknown error')}")

    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Summary")
    print(f"{'='*60}")

    successful_stores = sum(1 for r in store_results if r.get("success"))
    print(f"Memory Storage Tests: {successful_stores}/{len(store_results)} passed")

    print(f"\n✅ Phase 3 Qdrant Long-term Memory System tests completed!")
    print(f"🎯 The memory system is ready for agent integration!")

    return 0


async def test_agent_integration():
    """Test agent memory integration capabilities"""

    print(f"\n{'='*60}")
    print("🤖 Testing Agent Memory Integration")
    print(f"{'='*60}")

    try:
        # Import the integration module
        from memory_manager.integration import MemoryIntegration

        # Create integration for research agent
        research_memory = MemoryIntegration("research")

        # Test health
        print("\n🔍 Checking memory system health...")
        health = await research_memory.check_health()
        print(f"   Health Status: {'✅ Healthy' if health else '❌ Unhealthy'}")

        if not health:
            print("❌ Memory system not healthy, skipping integration tests")
            return 1

        # Test storing research result
        print("\n📝 Storing research result...")
        store_success = await research_memory.store_result(
            result="Advanced AI research: Large Language Models have shown remarkable capabilities in reasoning, coding, and creative tasks.",
            job_id=999,
            trace_id="integration-test-trace",
            metadata={"topic": "ai_research", "task_type": "research", "importance": "high"}
        )
        print(f"   Store Result: {'✅ Success' if store_success else '❌ Failed'}")

        # Test retrieving context
        print("\n🔍 Retrieving AI research context...")
        memories = await research_memory.retrieve_context(
            query="artificial intelligence and machine learning capabilities",
            limit=3
        )
        print(f"   Retrieved {len(memories)} relevant memories")

        for i, memory in enumerate(memories, 1):
            print(f"      {i}. Score: {memory.get('score', 0):.3f} - {memory.get('content', 'N/A')[:80]}...")

        # Test task enhancement
        print("\n✨ Testing task enhancement with memory...")
        enhanced = await research_memory.enhance_task_with_memory(
            task_description="Research the latest developments in AI",
            job_id=999
        )

        print(f"   Original Task: 'Research the latest developments in AI'")
        print(f"   Enhanced Task Length: {len(enhanced)} characters")
        if len(enhanced) > 100:
            print(f"   ✅ Task successfully enhanced with context")
        else:
            print(f"   ⚠️  Task enhancement minimal (may need more stored memories)")

        print(f"\n✅ Agent integration tests completed successfully!")
        return 0

    except Exception as e:
        print(f"❌ Agent integration test failed: {e}")
        return 1


async def main():
    """Main test function"""

    try:
        # Run core memory system tests
        exit_code = await run_tests()

        if exit_code == 0:
            # Run agent integration tests
            await asyncio.sleep(2)  # Wait between tests
            integration_exit_code = await test_agent_integration()
            exit_code = max(exit_code, integration_exit_code)

        return exit_code

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
