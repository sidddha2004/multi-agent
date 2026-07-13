import logging
import os
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@postgres:5432/secureai")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()


# Workflow State
class WorkflowState(TypedDict):
    """State for LangGraph workflow planning"""
    prompt: str
    job_id: int
    trace_id: str
    correlation_id: str
    tasks: List[Dict[str, Any]]
    analysis: Optional[str]
    capabilities_required: List[str]
    workflow_type: str
    confidence: float
    error_message: Optional[str]


# Database Models
class Workflow(Base):
    """Workflow definitions and executions"""
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    workflow_type = Column(String, nullable=False)  # sequential, parallel, conditional, hybrid
    definition = Column(Text, nullable=False)  # JSON workflow definition
    capabilities = Column(Text)  # JSON array of required capabilities
    is_active = Column(Boolean, default=True)
    version = Column(String, default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowExecution(Base):
    """Workflow execution tracking"""
    __tablename__ = "workflow_executions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=False)
    job_id = Column(Integer, nullable=False)
    trace_id = Column(String, nullable=False)
    correlation_id = Column(String, index=True)
    status = Column(String, default="pending")  # pending, running, completed, failed, rolled_back
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer)
    execution_context = Column(Text)  # JSON execution state
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# LangGraph Workflow Nodes
def analyze_prompt(state: WorkflowState) -> WorkflowState:
    """Analyze the prompt and determine workflow type"""
    try:
        logger.info(f"Analyzing prompt for job {state['job_id']}")

        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4", temperature=0.7)

        analysis_prompt = f"""Analyze this user request and determine:
1. What type of workflow is needed (sequential, parallel, conditional, hybrid)
2. What capabilities are required
3. How complex is this task (1-10)
4. What are the main steps needed

User request: {state['prompt']}

Respond in JSON format:
{{
    "workflow_type": "sequential|parallel|conditional|hybrid",
    "capabilities_required": ["capability1", "capability2"],
    "complexity": 1-10,
    "steps": ["step1", "step2", "step3"],
    "confidence": 0.0-1.0
}}
"""

        response = llm.invoke([HumanMessage(content=analysis_prompt)])
        result = json.loads(response.content)

        state['analysis'] = str(result)
        state['workflow_type'] = result.get('workflow_type', 'sequential')
        state['capabilities_required'] = result.get('capabilities_required', [])
        state['confidence'] = result.get('confidence', 0.8)

        logger.info(f"Analysis complete: {state['workflow_type']} workflow with confidence {state['confidence']}")
        return state

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        state['error_message'] = str(e)
        state['workflow_type'] = 'sequential'  # Fallback
        state['confidence'] = 0.5
        return state


def create_sequential_workflow(state: WorkflowState) -> WorkflowState:
    """Create sequential task workflow"""
    try:
        logger.info(f"Creating sequential workflow for job {state['job_id']}")

        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4", temperature=0.7)

        workflow_prompt = f"""Create a sequential workflow for this request.
Break it down into 3-5 specific steps that should be executed in order.

Request: {state['prompt']}
Required capabilities: {state['capabilities_required']}

Respond in JSON format:
{{
    "tasks": [
        {{
            "description": "Specific task description",
            "required_capability": "capability_name",
            "depends_on": null
        }}
    ]
}}
"""

        response = llm.invoke([HumanMessage(content=workflow_prompt)])
        result = json.loads(response.content)

        state['tasks'] = result.get('tasks', [])
        logger.info(f"Created sequential workflow with {len(state['tasks'])} tasks")
        return state

    except Exception as e:
        logger.error(f"Sequential workflow creation failed: {e}")
        state['error_message'] = str(e)
        return state


def create_parallel_workflow(state: WorkflowState) -> WorkflowState:
    """Create parallel task workflow"""
    try:
        logger.info(f"Creating parallel workflow for job {state['job_id']}")

        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4", temperature=0.7)

        workflow_prompt = f"""Create a parallel workflow for this request.
Break it down into 2-4 independent tasks that can be executed simultaneously.

Request: {state['prompt']}
Required capabilities: {state['capabilities_required']}

Respond in JSON format:
{{
    "tasks": [
        {{
            "description": "Independent task description",
            "required_capability": "capability_name",
            "parallel_group": "A"
        }}
    ]
}}
"""

        response = llm.invoke([HumanMessage(content=workflow_prompt)])
        result = json.loads(response.content)

        state['tasks'] = result.get('tasks', [])
        logger.info(f"Created parallel workflow with {len(state['tasks'])} tasks")
        return state

    except Exception as e:
        logger.error(f"Parallel workflow creation failed: {e}")
        state['error_message'] = str(e)
        return state


def create_conditional_workflow(state: WorkflowState) -> WorkflowState:
    """Create conditional workflow with branches"""
    try:
        logger.info(f"Creating conditional workflow for job {state['job_id']}")

        llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4", temperature=0.7)

        workflow_prompt = f"""Create a conditional workflow for this request.
Define branches based on different conditions or outcomes.

Request: {state['prompt']}
Required capabilities: {state['capabilities_required']}

Respond in JSON format:
{{
    "tasks": [
        {{
            "description": "Initial task",
            "required_capability": "capability_name",
            "condition": "true",
            "branch": "main"
        }}
    ],
    "branches": {{
        "main": ["task1", "task2"],
        "alternative": ["task3"]
    }}
}}
"""

        response = llm.invoke([HumanMessage(content=workflow_prompt)])
        result = json.loads(response.content)

        state['tasks'] = result.get('tasks', [])
        logger.info(f"Created conditional workflow with {len(state['tasks'])} tasks")
        return state

    except Exception as e:
        logger.error(f"Conditional workflow creation failed: {e}")
        state['error_message'] = str(e)
        return state


def validate_workflow(state: WorkflowState) -> WorkflowState:
    """Validate workflow completeness and feasibility"""
    try:
        logger.info(f"Validating workflow for job {state['job_id']}")

        # Basic validation
        if not state['tasks']:
            state['error_message'] = "No tasks generated"
            state['confidence'] = 0.0
            return state

        # Check if all tasks have required capabilities
        missing_caps = []
        for task in state['tasks']:
            if 'required_capability' not in task and 'agent_type' not in task:
                missing_caps.append(task.get('description', 'unknown task'))

        if missing_caps:
            logger.warning(f"Tasks missing capabilities: {missing_caps}")
            state['confidence'] *= 0.8  # Reduce confidence

        # Validate workflow structure
        if state['workflow_type'] == 'conditional' and len(state['tasks']) < 2:
            logger.warning("Conditional workflow needs at least 2 tasks")
            state['confidence'] *= 0.7

        logger.info(f"Workflow validation complete, confidence: {state['confidence']}")
        return state

    except Exception as e:
        logger.error(f"Workflow validation failed: {e}")
        state['error_message'] = str(e)
        state['confidence'] = 0.3
        return state


# Build LangGraph Workflow
def build_workflow_planning_graph():
    """Build the LangGraph workflow planning state machine"""

    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("analyze", analyze_prompt)
    workflow.add_node("sequential", create_sequential_workflow)
    workflow.add_node("parallel", create_parallel_workflow)
    workflow.add_node("conditional", create_conditional_workflow)
    workflow.add_node("validate", validate_workflow)

    # Define routing logic
    def route_workflow_type(state: WorkflowState) -> str:
        """Route to appropriate workflow creation based on analysis"""
        workflow_type = state.get('workflow_type', 'sequential')

        if workflow_type == 'parallel':
            return 'parallel'
        elif workflow_type == 'conditional':
            return 'conditional'
        else:
            return 'sequential'

    # Add edges
    workflow.set_entry_point("analyze")
    workflow.add_conditional_edges(
        "analyze",
        route_workflow_type,
        {
            'sequential': 'sequential',
            'parallel': 'parallel',
            'conditional': 'conditional'
        }
    )

    # All workflow types lead to validation
    workflow.add_edge("sequential", "validate")
    workflow.add_edge("parallel", "validate")
    workflow.add_edge("conditional", "validate")

    # End at validation
    workflow.add_edge("validate", END)

    return workflow.compile()


# Main Workflow Planning Function
async def plan_workflow_with_langgraph(
    prompt: str,
    job_id: int,
    trace_id: str,
    correlation_id: str
) -> Dict[str, Any]:
    """Plan workflow using LangGraph state machine"""

    try:
        logger.info(f"Starting LangGraph workflow planning for job {job_id}")

        # Initialize state
        initial_state: WorkflowState = {
            "prompt": prompt,
            "job_id": job_id,
            "trace_id": trace_id,
            "correlation_id": correlation_id,
            "tasks": [],
            "analysis": None,
            "capabilities_required": [],
            "workflow_type": "sequential",
            "confidence": 0.0,
            "error_message": None
        }

        # Build and run workflow graph
        workflow_graph = build_workflow_planning_graph()
        result = await workflow_graph.ainvoke(initial_state)

        logger.info(f"LangGraph workflow planning complete for job {job_id}")
        logger.info(f"Generated {len(result['tasks'])} tasks with confidence {result['confidence']}")

        return {
            "tasks": result['tasks'],
            "workflow_type": result['workflow_type'],
            "capabilities_required": result['capabilities_required'],
            "confidence": result['confidence'],
            "analysis": result['analysis'],
            "error_message": result.get('error_message')
        }

    except Exception as e:
        logger.error(f"LangGraph workflow planning failed: {e}")
        # Fallback to simple task creation
        return {
            "tasks": [
                {
                    "description": f"Process: {prompt}",
                    "required_capability": "research",
                    "agent_type": "research"
                }
            ],
            "workflow_type": "sequential",
            "capabilities_required": ["research"],
            "confidence": 0.5,
            "analysis": "Fallback to sequential workflow",
            "error_message": str(e)
        }


# Save Workflow to Database
def save_workflow_to_database(
    job_id: int,
    trace_id: str,
    workflow_result: Dict[str, Any],
    db: Session
) -> int:
    """Save workflow execution to database"""

    try:
        # Find or create workflow definition
        workflow_name = f"workflow_{workflow_result['workflow_type']}_{job_id}"

        workflow = Workflow(
            name=workflow_name,
            description=f"Auto-generated workflow for job {job_id}",
            workflow_type=workflow_result['workflow_type'],
            definition=json.dumps(workflow_result),
            capabilities=json.dumps(workflow_result['capabilities_required']),
            is_active=True,
            version="1.0.0"
        )

        db.add(workflow)
        db.commit()
        db.refresh(workflow)

        # Create workflow execution record
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            job_id=job_id,
            trace_id=trace_id,
            correlation_id=workflow_result.get('correlation_id', trace_id),
            status="pending",
            total_steps=len(workflow_result['tasks']),
            execution_context=json.dumps(workflow_result)
        )

        db.add(execution)
        db.commit()
        db.refresh(execution)

        logger.info(f"Saved workflow {workflow.id} with execution {execution.id}")
        return execution.id

    except Exception as e:
        logger.error(f"Failed to save workflow to database: {e}")
        return 0


def get_workflow_execution_status(execution_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """Get workflow execution status"""
    try:
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()

        if execution:
            return {
                "id": execution.id,
                "workflow_id": execution.workflow_id,
                "job_id": execution.job_id,
                "trace_id": execution.trace_id,
                "status": execution.status,
                "current_step": execution.current_step,
                "total_steps": execution.total_steps,
                "execution_context": json.loads(execution.execution_context) if execution.execution_context else {},
                "error_message": execution.error_message,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None
            }
        return None

    except Exception as e:
        logger.error(f"Failed to get workflow execution status: {e}")
        return None
