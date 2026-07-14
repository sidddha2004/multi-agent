# Multi-AI - Distributed AI Agent Platform

A powerful AI orchestration platform that coordinates multiple AI specialists to work together on complex tasks. Think of it as having a project manager that delegates different parts of your request to the best AI assistant for each job.

## What Makes Multi-AI Special?

Smart Task Planning - Automatically breaks down your requests into the right steps
Team Coordination - Routes tasks to the best AI agent for the job
Full Transparency - Watch your requests get processed in real-time
Extensible - Easily add new AI specialists to your team
Production-Ready - Built with enterprise-grade architecture

## How It Works (The Simple Version)

```
You → "Research quantum computing" → Multi-AI Team → Results!

Here's what happens behind the scenes:

1. You submit a request through a web interface
2. My smart planner figures out the best way to tackle it
3. The scheduler assigns tasks to the right AI specialists
4. Each agent works on their part (research, browsing, database queries, etc.)
5. Results come back in real-time while you watch
6. You get comprehensive, well-organized answers
```

## Current AI Specialists

Research Agent - Deep research and analysis
Browser Agent - Web scraping and online research
SQL Agent - Database queries and data analysis
Email Agent - Email parsing and communication

Coming Soon:

Creative Agent - Content generation and editing
Code Agent - Programming and debugging
Analytics Agent - Data visualization and insights

## Quick Start (5 Minutes)

Prerequisites
Docker and Docker Compose installed
An OpenAI API key (get one at openai.com)

Step 1: Get the Code
```bash
git clone https://github.com/yourusername/multi-ai.git
cd multi-ai
```

Step 2: Setup Your API Key
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY=your_key_here
```

Step 3: Start Your AI Team
```bash
docker compose up --build
```

Step 4: Access the Platform
Open your browser and go to: http://localhost:3000

That's it! You're now ready to delegate tasks to your AI team.

## What Can You Do?

Example Tasks You Can Try:

Research & Analysis:

"What are the latest developments in quantum computing?"
"Compare renewable energy storage solutions"
"Analyze current trends in AI safety research"

Web & Data Exploration:

"Scrape tech news from the past week and summarize key trends"
"Query our database for customer churn patterns"
"Extract email addresses from this customer feedback"

Complex Multi-Step Tasks:

"Research the top 5 electric cars, browse their websites for specs,
and create a comparison table"

## Under the Hood (For the Tech-Curious)

Architecture Overview
```
Your Request → Frontend → API Gateway → Smart Planner → Scheduler →
Specialized Agents → Kafka Messaging → Results → Real-time Updates → You!
```

The Tech Stack That Makes It Possible

Backend: FastAPI (blazing fast Python web framework)
Frontend: React (beautiful, responsive UI)
Messaging: Apache Kafka (reliable task distribution)
Database: PostgreSQL (robust data storage)
Caching: Redis (speedy responses)
AI: OpenAI GPT-4 (powerful language model)
Containers: Docker (easy deployment)

Key Components

Smart Planner
- Analyzes your request using AI
- Breaks down complex tasks into steps
- Chooses the right workflow (sequential, parallel, or conditional)

Scheduler
- Matches tasks to the best agents
- Manages queues and priorities
- Handles retries and error recovery

Agent Registry
- Dynamic agent registration (no hardcoding!)
- Capability-based routing
- Easy to add new agent types

Result Aggregator
- Collects results from all agents
- Provides unified responses
- Tracks performance metrics

## Testing Your AI Team

I've included some handy test scripts:

```bash
# Test the complete workflow
./test-end-to-end.ps1

# Test memory capabilities
python test-memory.py

# Test workflow planning
python test-langgraph.py
```

## Monitoring & Debugging

Watch Your AI Team Work
```bash
# See all agents working
docker compose logs -f

# Follow specific agents
docker compose logs -f research-agent
docker compose logs -f browser-agent
```

Check Agent Health
```bash
# View registered agents
curl http://localhost:8002/agents

# Check Kafka message flow
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

## Why I Built Multi-AI

The Problem: Most AI tools are limited to single tasks. Need research + browsing + data analysis? You're stuck doing it yourself.

My Solution: A coordinated AI team that works together seamlessly. Think of it as having specialists who collaborate on your project, each bringing their unique expertise.

The Result: Faster, more comprehensive results with less manual effort.

## Contributing

I love contributions! Here are some ways you can help:

Add New Agents - Create specialized AI workers
Improve Workflows - Make task planning smarter
Enhance UI - Make the interface more beautiful
Write Docs - Help others understand the system
Share Ideas - Tell me what features you'd love

## Learning Resources

Want to understand how it all works?

Check out my code comments (I write them for humans!)
Run the test scripts to see workflows in action
Browse the agent code to understand specialist logic
Study the planner to see task breakdown in action

## Troubleshooting

Common Issues:

"I can't access the frontend!"
Make sure all containers are running: docker compose ps
Check frontend logs: docker compose logs frontend

"Tasks are stuck in processing!"
Check if your OpenAI API key is valid in .env
View agent logs: docker compose logs research-agent
Verify Kafka is working: docker compose logs kafka

"I want to add a new agent!"
Check the existing agent code for templates
Register your agent in the system
Add capabilities to the agent registry
Update the planner to recognize new task types

## Tips for Best Results

1. Be Specific - Clear requests get better results
2. Break It Down - Complex tasks work well step-by-step
3. Use Context - Reference previous results for continuity
4. Monitor Progress - Watch real-time updates to understand processing
5. Experiment - Try different types of requests to see agent strengths

## License

MIT License - Feel free to use, modify, and distribute!

## Acknowledgments

Built with love by the Multi-AI team
Powered by amazing open-source technologies
Inspired by the vision of accessible AI for everyone

---

Ready to supercharge your productivity with AI?

```bash
docker compose up --build
```

Open http://localhost:3000 and meet your new AI team!

Questions? Issues? Ideas? I'm here to help!

---

Built with love by the Multi-AI community
Making AI accessible, one task at a time