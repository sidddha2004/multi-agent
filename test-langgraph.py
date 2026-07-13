#!/usr/bin/env python3
"""
Test script for Phase 3 LangGraph Workflow Planning

This script tests the new LangGraph workflow planning system
by simulating requests and verifying the responses.
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, Any

# Test configuration
API_GATEWAY_URL = "http://localhost:8000"
PLANNER_URL = "http://localhost:8001"

# Test cases for different workflow types
TEST_CASES = [
    {
        "name": "Sequential Workflow Test",
        "prompt": "Research the latest developments in quantum computing, analyze their security implications, and create a comprehensive report",
        "expected_workflow_type": "sequential",
        "expected_min_tasks": 3,
        "description": "Tests sequential workflow with dependent tasks"
    },
    {
        "name": "Parallel Workflow Test",
        "prompt": "Gather market data from tech, finance, and healthcare sectors simultaneously",
        "expected_workflow_type": "parallel",
        "expected_min_tasks": 3,
        "description": "Tests parallel workflow with independent tasks"
    },
    {
        "name": "Conditional Workflow Test",
        "prompt": "Check if the website example.com is accessible. If yes, scrape the content. If no, try the backup site and send alert",
        "expected_workflow_type": "conditional",
        "expected_min_tasks": 2,
        "description": "Tests conditional workflow with branching logic"
    },
    {
        "name": "Simple Research Test",
        "prompt": "Research the benefits of microservices architecture",
        "expected_workflow_type": "sequential",
        "expected_min_tasks": 1,
        "description": "Tests simple single-task workflow"
    }
]


async def test_planner_health() -> bool:
    """Test if planner service is healthy"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{PLANNER_URL}/health")
            return response.status_code == 200
    except Exception as e:
        print(f"❌ Planner health check failed: {e}")
        return False


async def test_workflow_planning(test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Test workflow planning for a specific test case"""

    try:
        # Simulate a plan request (normally this comes from API Gateway)
        plan_request = {
            "prompt": test_case["prompt"],
            "job_id": 1,  # Test job ID
            "trace_id": "test-trace-123",
            "correlation_id": "test-correlation-456"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{PLANNER_URL}/plan",
                json=plan_request,
                timeout=30.0
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }

            result = response.json()

            # Validate response structure
            validation = validate_workflow_response(result, test_case)

            return {
                "success": True,
                "result": result,
                "validation": validation
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def validate_workflow_response(response: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Validate workflow response against expected results"""

    validation = {
        "has_workflow_type": "workflow_type" in response,
        "has_confidence": "workflow_confidence" in response,
        "has_execution_id": "workflow_execution_id" in response,
        "has_tasks": "tasks" in response and len(response.get("tasks", [])) > 0,
        "workflow_type_match": response.get("workflow_type") == test_case["expected_workflow_type"],
        "task_count_match": len(response.get("tasks", [])) >= test_case["expected_min_tasks"],
        "confidence_reasonable": response.get("workflow_confidence", 0) > 0.5,
        "execution_id_valid": response.get("workflow_execution_id", 0) > 0
    }

    # Overall pass/fail
    validation["overall_pass"] = all([
        validation["has_workflow_type"],
        validation["has_confidence"],
        validation["has_execution_id"],
        validation["has_tasks"],
        validation["task_count_match"],
        validation["confidence_reasonable"],
        validation["execution_id_valid"]
    ])

    return validation


def print_test_results(test_name: str, result: Dict[str, Any]):
    """Print formatted test results"""

    print(f"\n{'='*60}")
    print(f"🧪 Test: {test_name}")
    print(f"{'='*60}")

    if result.get("success"):
        response = result["result"]
        validation = result["validation"]

        print(f"✅ Test Passed")
        print(f"   Workflow Type: {response.get('workflow_type', 'N/A')}")
        print(f"   Confidence Score: {response.get('workflow_confidence', 0):.2f}")
        print(f"   Execution ID: {response.get('workflow_execution_id', 'N/A')}")
        print(f"   Tasks Generated: {len(response.get('tasks', []))}")

        if response.get('tasks'):
            print(f"   Task Details:")
            for i, task in enumerate(response.get('tasks', []), 1):
                print(f"      {i}. {task.get('description', 'N/A')} ({task.get('agent_type', 'N/A')})")

        # Validation details
        print(f"\n   Validation:")
        print(f"      Has workflow_type: {'✅' if validation['has_workflow_type'] else '❌'}")
        print(f"      Has confidence: {'✅' if validation['has_confidence'] else '❌'}")
        print(f"      Has execution_id: {'✅' if validation['has_execution_id'] else '❌'}")
        print(f"      Has tasks: {'✅' if validation['has_tasks'] else '❌'}")
        print(f"      Workflow type match: {'✅' if validation['workflow_type_match'] else '⚠️'}")
        print(f"      Task count match: {'✅' if validation['task_count_match'] else '⚠️'}")
        print(f"      Confidence reasonable: {'✅' if validation['confidence_reasonable'] else '❌'}")
        print(f"      Execution ID valid: {'✅' if validation['execution_id_valid'] else '❌'}")
        print(f"      Overall: {'✅ PASS' if validation['overall_pass'] else '❌ FAIL'}")

    else:
        print(f"❌ Test Failed")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        if result.get('details'):
            print(f"   Details: {result['details']}")


async def run_tests():
    """Run all LangGraph workflow planning tests"""

    print("🚀 Starting Phase 3 LangGraph Workflow Planning Tests")
    print("="*60)

    # Test planner health
    print("\n🔍 Checking planner service health...")
    if not await test_planner_health():
        print("❌ Planner service is not healthy. Exiting tests.")
        sys.exit(1)

    print("✅ Planner service is healthy")

    # Run test cases
    results = []
    for test_case in TEST_CASES:
        print(f"\n📋 Running: {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        print(f"   Prompt: {test_case['prompt'][:100]}...")

        result = await test_workflow_planning(test_case)
        print_test_results(test_case['name'], result)

        results.append({
            "test_case": test_case,
            "result": result
        })

    # Summary
    print(f"\n{'='*60}")
    print("📊 Test Summary")
    print(f"{'='*60}")

    passed = sum(1 for r in results if r["result"].get("success"))
    total = len(results)

    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")

    if passed == total:
        print(f"\n🎉 All tests passed! Phase 3 LangGraph Workflow Planning is working correctly.")
        return 0
    else:
        print(f"\n⚠️  Some tests failed. Please review the results above.")
        return 1


async def test_workflow_execution_tracking():
    """Test workflow execution tracking in database"""

    print(f"\n{'='*60}")
    print("🔍 Testing Workflow Execution Tracking")
    print(f"{'='*60}")

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        # Connect to database
        conn = psycopg2.connect(
            host="localhost",
            database="secureai",
            user="admin",
            password="admin123"
        )

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check workflow executions table
        cursor.execute("""
            SELECT
                we.id,
                we.job_id,
                we.status,
                we.current_step,
                we.total_steps,
                w.workflow_type,
                w.name as workflow_name
            FROM workflow_executions we
            LEFT JOIN workflows w ON we.workflow_id = w.id
            ORDER BY we.created_at DESC
            LIMIT 5
        """)

        executions = cursor.fetchall()

        if executions:
            print(f"✅ Found {len(executions)} workflow executions:")
            for execution in executions:
                print(f"   ID: {execution['id']}")
                print(f"   Workflow: {execution['workflow_name']} ({execution['workflow_type']})")
                print(f"   Status: {execution['status']}")
                print(f"   Progress: {execution['current_step']}/{execution['total_steps']}")
                print()
        else:
            print(f"⚠️  No workflow executions found in database")

        cursor.close()
        conn.close()

        return 0

    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return 1


async def main():
    """Main test function"""

    try:
        # Run workflow planning tests
        exit_code = await run_tests()

        if exit_code == 0:
            # Test database tracking
            await test_workflow_execution_tracking()

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
