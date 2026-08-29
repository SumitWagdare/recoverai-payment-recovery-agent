# Architecture

RecoverAI is built with a modular, layered architecture to separate the frontend interface, business logic, safety constraints, and state persistence.

## System Diagram

```mermaid
flowchart TD
    %% Users
    Operator([Human Operator])
    
    %% UI Layer
    subgraph Frontend [Dashboard UI (app/static/)]
        JS[Vanilla JS SPA]
        CSS[Glassmorphism CSS]
    end
    
    %% API Layer
    subgraph API [Flask Server (app/server.py)]
        API_Endpoints[REST Endpoints\n/api/payments, /api/dashboard]
    end
    
    %% Business Logic
    subgraph Logic [Core System]
        RA[Recovery Agent\n(app/recovery_agent.py)]
        AI[AI Decision Engine\n(app/ai_engine.py)]
        Safety{Safety Guards\n- Max Retries\n- Cooldown\n- Approval}
        DuplicateCheck{Duplicate\nContact\nPrevention}
    end
    
    %% Storage Layer
    subgraph Storage [Data & Storage (data/)]
        DB[(Payments JSON)]
        Audit[(Audit Log JSONL)]
    end
    
    %% Interactions
    Operator -->|Approves / Rejects Actions| JS
    JS <-->|HTTP GET/POST| API_Endpoints
    API_Endpoints <--> RA
    
    RA --> Safety
    Safety -->|Passed| AI
    Safety -.->|Failed| DB
    
    AI -->|Classify & Recommend| DuplicateCheck
    DuplicateCheck -->|Passed| RA
    DuplicateCheck -.->|Blocked| Audit
    
    RA -->|Record Action| Audit
    RA -->|Update Status| DB
```

## Components Breakdown

### 1. AI Decision Engine (`app/ai_engine.py`)
Responsible purely for intelligence mapping. It takes a payment snapshot and returns:
- **Classification**: Maps raw payment gateway errors to internal logical categories (e.g., `temporary`, `permanent`).
- **Recommendation**: Uses the classification, customer segment, and retry history to select one of four bounded actions (`retry_later`, `send_payment_link`, `request_alt_method`, `escalate_to_support`), complete with explainable reasoning text.

### 2. Recovery Agent (`app/recovery_agent.py`)
The orchestrator. It wraps the AI Engine in strict safety and policy constraints.
- **Safety**: Checks cooldowns and maximum retry limits before letting the AI process a payment.
- **Duplicate Prevention**: Checks the audit log to ensure the same customer isn't bombarded with payment links within a 24-hour window.
- **Human Approval**: Intercepts actions recommended by the AI. If the action is customer-facing, or the payment is above a high-value threshold, the agent pauses execution and marks it as `awaiting_approval`.

### 3. Audit Log (`app/audit_log.py`)
The immutable record keeper.
- Uses a JSON Lines (`.jsonl`) append-only format.
- Records every decision the AI makes, every block the safety system enforces, and every manual approval/rejection made by a human operator.

### 4. REST API (`app/server.py`)
A lightweight Flask application exposing internal operations to the frontend.
- `/api/dashboard`: Aggregates statistics.
- `/api/payments/<id>/process`: Triggers the Recovery Agent.
- `/api/payments/<id>/approve`: Completes a held workflow.

### 5. Frontend Dashboard (`app/static/`)
A completely dependency-free (Vanilla JS/CSS) Single Page Application (SPA).
- Uses modern CSS properties (backdrop-filter) for a premium dark-mode glassmorphism aesthetic.
- Presents actionable modals for human operators to quickly evaluate AI reasoning and approve or reject actions.
