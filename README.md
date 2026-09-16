# Agentic AI Based Bus Ticket Booking Application

An educational **Agentic AI Bus Ticket Booking Application** built from
scratch to learn and implement modern AI agent development concepts step
by step.

This project is intentionally being developed as a **learning project**,
not as a production-ready ticket booking platform.

The goal is to understand how an AI agent is designed, how an LLM
interacts with application logic and tools, how context and state are
managed, and how an agent can eventually interact with a real database
to search buses, check seats, and manage bookings.

------------------------------------------------------------------------

## Project Goal

The objective of this project is to build a bus ticket booking AI agent
while learning the major concepts involved in modern agent development.

Instead of learning each concept independently and then building an
unrelated project, every concept is introduced theoretically,
implemented practically, tested, and eventually integrated into the same
bus booking application.

The planned agent will eventually be able to:

-   Understand natural-language bus booking requests
-   Ask users for missing information
-   Search available buses
-   Retrieve bus details
-   Check seat availability
-   Hold seats
-   Release held seats
-   Create bookings
-   Retrieve booking information
-   Cancel bookings
-   Maintain conversation context
-   Validate structured information
-   Use external tools through MCP
-   Coordinate multiple agent steps using LangGraph

The application will use manually created sample bus data for learning
and experimentation.

------------------------------------------------------------------------

# Architecture

The planned architecture is:

``` text
                    User
                      │
                      ▼
             Next.js + TypeScript
                      │
                    HTTP
                      │
                      ▼
               FastAPI Backend
                      │
                      ▼
                LangGraph Agent
                      │
                      ▼
                Google Gemini
                      │
                     MCP
                      │
                      ▼
                 MCP Server
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Bus Tools   Seat Tools   Booking Tools
          │           │           │
          └───────────┼───────────┘
                      ▼
             Supabase PostgreSQL
```

### Core architectural principle

The project follows this separation:

``` text
LLM
│
└── Reasoning and decision making

Tools / Backend
│
└── Deterministic execution and business logic

Database
│
└── Source of truth
```

The LLM should **not** be responsible for inventing bus schedules,
prices, seat availability, or booking information.

Gemini will eventually decide what action should be taken, while
application tools and the database will perform and verify the actual
operations.

------------------------------------------------------------------------

# Technology Stack

## Frontend

-   Next.js
-   TypeScript

The frontend will eventually provide the user interface for interacting
with the bus booking agent.

------------------------------------------------------------------------

## Backend

-   Python
-   FastAPI

FastAPI will eventually expose the application backend and coordinate
communication between the frontend, agent layer, tools, and other
backend components.

------------------------------------------------------------------------

## LLM

-   Google Gemini API
-   `google-genai` Python SDK

Current development model:

``` text
gemini-3.5-flash
```

The project uses Google's Gemini Python SDK rather than an LLM
abstraction layer for the initial learning stages so that the underlying
concepts can be understood directly.

------------------------------------------------------------------------

## Agent Framework

-   LangGraph, LangSmith

LangGraph will be introduced later for agent state, nodes, edges,
conditional routing, loops, tool execution, checkpoints, and human
interruption.

It is intentionally not being used during the initial LLM foundation
stage.

------------------------------------------------------------------------

## Tool Protocol

-   MCP (Model Context Protocol)

MCP will eventually be used to expose bus, seat, and booking
capabilities as tools that the agent can use.

------------------------------------------------------------------------

## Database

-   Supabase
-   PostgreSQL

Supabase PostgreSQL will eventually contain:

-   Operators
-   Buses
-   Routes
-   Schedules
-   Seats
-   Users
-   Bookings
-   Booking seats
-   Optional payment information
-   Conversation/state information

The database has **not been introduced yet** because it belongs to the
later MCP and tool-calling stage of the learning roadmap.

------------------------------------------------------------------------

## Validation

-   Pydantic

Pydantic is used to validate structured data returned from the LLM
before application code consumes it.

------------------------------------------------------------------------

# Learning Roadmap

The project follows a 14-stage learning roadmap.

``` text
Phase 01 → LLM Foundations
Phase 02 → Context Engineering
Phase 03 → MCP + Tool Calling
Phase 04 → Agent Loops + Orchestration
Phase 05 → Memory + State
Phase 06 → Guardrails + Security
Phase 07 → Human-in-the-Loop
Phase 08 → Multi-Agent Systems
Phase 09 → Observability
Phase 10 → Evaluation
Phase 11 → Reliability
Phase 12 → Cost + Performance
Phase 13 → LangChain + LangGraph
Phase 14 → Production Deployment
```

The project is being developed sequentially so that each layer is
understood before more complex agent behavior is introduced.

------------------------------------------------------------------------

# Current Status

## Phase 01: LLM Foundations

**Status: COMPLETE**

Phase 01 focuses on understanding how an LLM works from an
application-development perspective before introducing tools, agents,
databases, or orchestration frameworks.

### Completed concepts

#### 1. LLM Integration

Connected the Python application to Google's Gemini API using the
`google-genai` SDK.

The project can send user input to Gemini and receive a model response.

------------------------------------------------------------------------

#### 2. Tokens

Learned what tokens are and how LLMs process input and output as tokens.

The project also observes token usage returned by Gemini.

Tracked usage includes:

``` text
Input tokens
Output tokens
Thought tokens
Tool-use tokens
Cached tokens
Total tokens
```

------------------------------------------------------------------------

#### 3. Token Counting

Implemented Gemini's token-counting capability using:

``` python
client.models.count_tokens()
```

The application counts the current user input before sending the
generation request.

------------------------------------------------------------------------

#### 4. Multi-turn Conversation

Implemented multi-turn conversations using Gemini's interaction
continuation mechanism.

The application stores the previous interaction ID and uses it when
sending subsequent messages.

Conceptually:

``` text
Interaction 1
      ↓
interaction.id
      ↓
Interaction 2
      ↓
interaction.id
      ↓
Interaction 3
```

------------------------------------------------------------------------

#### 5. Context Window

Implemented model-limit inspection using the Gemini API.

The application retrieves the selected model's:

``` text
Input token limit
Output token limit
```

This provides practical visibility into the model's context and output
capacity.

------------------------------------------------------------------------

#### 6. System Instructions

Implemented system-level instructions for the bus booking assistant.

Current instructions establish that the assistant should:

-   Help with bus travel and ticket booking questions
-   Be clear and concise
-   Ask for missing information
-   Avoid inventing bus information
-   Avoid inventing seat availability
-   Avoid inventing prices
-   Clearly state when information is unknown

This establishes an important principle for the future agent:

> The LLM should not invent application data.

------------------------------------------------------------------------

#### 7. User Messages

Implemented dynamic user input through the CLI.

The user can type their own questions and requests rather than having
predefined questions hard-coded into the application.

------------------------------------------------------------------------

#### 8. Conversation History

Created a dedicated `ConversationHistory` abstraction.

The component manages the Gemini interaction ID required to continue a
conversation across turns.

Conceptually:

``` text
User Message
     ↓
ConversationHistory
     ↓
Gemini Interaction
     ↓
Interaction ID
     ↓
ConversationHistory
     ↓
Next User Message
```

This keeps conversation-history responsibility separate from the main
integrated test.

------------------------------------------------------------------------

#### 9. Structured Output

Implemented structured output using a Pydantic model.

Current learning schema:

``` python
class BusSearchRequest(BaseModel):
    origin: str
    destination: str
    travel_date: str
    passengers: int
```

The intended flow is:

``` text
Natural Language
       ↓
Gemini
       ↓
Structured Output
       ↓
Pydantic Validation
       ↓
Python Object
```

This demonstrates how LLM output can become machine-readable application
data.

------------------------------------------------------------------------

# Current Phase 01 Project Structure

``` text
src/
└── bus_booking_ai_agent/
    │
    ├── __init__.py
    │
    ├── config/
    │   ├── __init__.py
    │   └── gemini.py
    │
    └── phase_01_llm_fundamentals/
        ├── __init__.py
        ├── context_window.py
        ├── conversation_history.py
        ├── llm_integration.py
        ├── multi_turn.py
        ├── structured_output.py
        ├── system_instructions.py
        ├── test.py
        ├── token_counting.py
        ├── tokens.py
        └── user_messages.py

main.py
pyproject.toml
README.md
uv.lock
```

------------------------------------------------------------------------

# Integrated Phase 01 Test

The project contains a single integrated Phase 01 test:

``` text
phase_01_llm_fundamentals/test.py
```

The integrated test combines the concepts learned during Phase 01 rather
than requiring each concept to be executed independently.

Run it with:

``` bash
uv run python -m bus_booking_ai_agent.phase_01_llm_fundamentals.test
```

The integrated test currently demonstrates:

``` text
User Input
    ↓
Token Counting
    ↓
System Instructions
    ↓
Conversation History
    ↓
Gemini
    ↓
Response
    ↓
Token Usage
```

Structured output can also be tested through the integrated test using
the structured-input flow.

------------------------------------------------------------------------

# Phase 02: Context Engineering

**Status: IN PROGRESS**

Phase 02 focuses on designing and managing the information supplied to
the LLM for each request.

### Completed Topics

#### 1. Context Sources

Implemented a `ContextSources` abstraction for the currently available
context:

``` text
System Instruction
User Message
Previous Interaction ID
```

#### 2. Context Selection

Implemented deterministic context selection. System instructions and the
current user message are always selected, while the previous interaction
ID is included only when available.

#### 3. Context Formatting

Implemented context formatting into readable sections while keeping
formatting separate from context ordering.

#### 4. Context Ordering

Implemented explicit ordering of context sources before formatting.

#### 5. Context Injection

Implemented injection of engineered context into Gemini while preserving
multi-turn conversation continuity through `previous_interaction_id`.

#### 6. Dynamic Context

Implemented dynamic updating of the current user message and previous
interaction state for each conversation turn.

#### 7. Context Compression

Implemented deterministic context compression. System instructions and
previous interaction IDs remain in application state but are excluded
from the formatted text input because they are handled separately by
Gemini.

#### 8. Context Management

Implemented `ContextManager` to coordinate:

``` text
Context Selection
      ↓
Context Compression
      ↓
Context Ordering
      ↓
Context Formatting
```

This keeps the individual context components separate while providing a
single context-management pipeline.

### Current Phase 02 Pipeline

``` text
User Message
     ↓
Dynamic Context
     ↓
Context Manager
     ↓
Context Selection
     ↓
Context Compression
     ↓
Context Ordering
     ↓
Context Formatting
     ↓
Context Injection
     ↓
Google Gemini
```

### Next Phase 02 Topics

``` text
09. Context Prioritization
10. Context Engineering for Agents
11. Context vs Memory
12. Context vs Tools
13. Context Failure Modes
14. Integrated Context Pipeline
```

The phase will be considered complete after Topic 14, followed by a
Phase 02 review and interview/study PDF.

------------------------------------------------------------------------

# What Is Not Implemented Yet

The project is intentionally **not connected to real bus data yet**.

Currently there is:

-   No Supabase database
-   No PostgreSQL schema
-   No real bus records
-   No MCP server
-   No MCP tools
-   No seat availability tool
-   No booking tool
-   No payment system
-   No LangGraph agent workflow
-   No authentication
-   No frontend
-   No production deployment

This is intentional.

The learning process introduces each layer only when its corresponding
phase is reached.

------------------------------------------------------------------------

# Future Bus Data

Sample bus data will be manually created for learning.

The planned data model includes:

``` text
Operators
    ↓
Buses
    ↓
Routes
    ↓
Schedules
    ↓
Seats
    ↓
Bookings
```

Example future tools:

``` text
search_buses
check_seat_availability
get_bus_details
hold_seat
release_seat
create_booking
get_booking
cancel_booking
```

These tools will eventually interact with Supabase PostgreSQL rather
than relying on the LLM to generate or invent application data.

------------------------------------------------------------------------

# Development Approach

This project follows a learning-first implementation process.

For each major concept:

``` text
1. Learn the theory
       ↓
2. Understand why it exists
       ↓
3. Relate it to the bus-agent problem
       ↓
4. Implement a small experiment
       ↓
5. Test the implementation
       ↓
6. Integrate it into the project
       ↓
7. Break and debug it
       ↓
8. Move to the next concept
```

The goal is not simply to produce an application.

The goal is to understand **why each component exists and how the
components work together**.

------------------------------------------------------------------------

# Project Philosophy

This project follows several principles.

### 1. LLM is not the source of truth

Gemini handles reasoning and interpretation.

Actual application data must eventually come from deterministic tools
and the database.

------------------------------------------------------------------------

### 2. No hard-coded user questions

The application should accept user input dynamically.

Learning experiments may have example inputs in documentation, but the
actual CLI interaction should allow the user to type arbitrary requests.

------------------------------------------------------------------------

### 3. Learn the underlying concepts before hiding them behind frameworks

The initial implementation uses the Gemini SDK directly.

Frameworks such as LangChain and LangGraph will be introduced later
after the underlying LLM, context, tool, and agent concepts are
understood.

------------------------------------------------------------------------

### 4. Build one project throughout the roadmap

Each phase adds another layer to the same bus booking application.

The project should gradually evolve from:

``` text
Simple Gemini interaction
```

into:

``` text
LLM
 ↓
Context
 ↓
Tools
 ↓
Agent
 ↓
Memory
 ↓
Guardrails
 ↓
Human approval
 ↓
Multi-agent system
 ↓
Observable + evaluated system
 ↓
Reliable application
 ↓
Production deployment
```

------------------------------------------------------------------------

# Current Development Stage

``` text
┌──────────────────────────────────────────────┐
│       AGENTIC BUS BOOKING APPLICATION        │
├──────────────────────────────────────────────┤
│                                              │
│ Phase 01  LLM Foundations        ✅ COMPLETE │
│ Phase 02  Context Engineering    🔄 IN PROGRESS │
│ Phase 03  MCP + Tool Calling     ⏳          │
│ Phase 04  Agent Orchestration    ⏳          │
│ Phase 05  Memory + State         ⏳          │
│ Phase 06  Guardrails + Security  ⏳          │
│ Phase 07  Human-in-the-Loop      ⏳          │
│ Phase 08  Multi-Agent            ⏳          │
│ Phase 09  Observability          ⏳          │
│ Phase 10  Evaluation             ⏳          │
│ Phase 11  Reliability            ⏳          │
│ Phase 12  Cost + Performance     ⏳          │
│ Phase 13  LangChain + LangGraph  ⏳          │
│ Phase 14  Deployment             ⏳          │
│                                              │
└──────────────────────────────────────────────┘
```

## Current Milestone

**Phase 01: LLM Foundations completed.**

**Phase 02: Context Engineering is currently in progress.**

### Phase 02 Progress

The following topics have been completed:

``` text
01. Context Sources          ✅
02. Context Selection        ✅
03. Context Formatting       ✅
04. Context Ordering         ✅
05. Context Injection        ✅
06. Dynamic Context          ✅
07. Context Compression      ✅
08. Context Management       ✅
```

### Next Topic

``` text
09. Context Prioritization
```

Phase 02 contains 14 topics in total, so 6 topics remain after Topic 08.

# Project Status

This repository is an ongoing learning project.

The implementation will evolve significantly as new agent-development
concepts are introduced.

The current code should therefore be considered **educational and
experimental**, not production-ready software.

------------------------------------------------------------------------

## License

This project is intended primarily as a personal learning and
experimentation project.
