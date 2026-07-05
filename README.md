# Autonomous Database Agent (DevOps ADK)

This project is a fully autonomous Database Administrator (DBA) agent built using **LangGraph**, **React**, and **Google GenAI**. It analyzes database schemas, detects issues like write hotspotting in CockroachDB, writes SQL fixes, gets them reviewed by an internal QA Agent, and pauses for human approval before executing them on a live cluster.

## System Architecture

Here is the block diagram of the system. It is broken down into two parts: the overall full-stack architecture, and the internal LangGraph AI Agent flow.

### 1. Full-Stack Architecture

This shows how the different pieces of the system communicate with each other.

```mermaid
graph TD
    %% Define styles
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:white;
    classDef backend fill:#10b981,stroke:#047857,stroke-width:2px,color:white;
    classDef ai fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:white;
    classDef db fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:white;

    %% Nodes
    React["💻 React Frontend<br/>(UI & Human Approval)"]:::frontend
    FastAPI["⚙️ FastAPI Backend<br/>(Python Server)"]:::backend
    Gemini["🧠 Gemini 2.5 Flash<br/>(Google GenAI API)"]:::ai
    CRDB["🗄️ CockroachDB<br/>(Live Database)"]:::db

    %% Connections
    React -- "HTTP POST (Task)" --> FastAPI
    React -- "HTTP POST (Resume)" --> FastAPI
    
    FastAPI -- "Prompts & Context" --> Gemini
    Gemini -- "SQL & Reasoning" --> FastAPI
    
    FastAPI -- "Execute SQL" --> CRDB
    CRDB -- "Results" --> FastAPI
```

---

### 2. Multi-Agent ADK Flow (LangGraph)

This shows the internal state machine running inside our Python backend when a task is received.

```mermaid
stateDiagram-v2
    direction TB
    
    Start --> DBA_Agent : Task Received
    
    state DBA_Agent {
        [*] --> Think
        Think --> WriteSQL
    }
    
    DBA_Agent --> QA_Agent : SQL Proposed
    
    state QA_Agent {
        [*] --> ReviewSQL
        ReviewSQL --> Approve
        ReviewSQL --> Reject
    }
    
    QA_Agent --> DBA_Agent : Rejected (Needs Fix)
    QA_Agent --> Human_In_The_Loop : Approved
    
    state Human_In_The_Loop {
        [*] --> Pause
        Pause --> Wait_For_Click
    }
    
    Human_In_The_Loop --> Execute_SQL : User Clicks 'Approve'
    
    Execute_SQL --> End : Success!
```
