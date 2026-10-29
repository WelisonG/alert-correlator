# Alert Correlator

**Rule-Based Incident Correlation API | Python · FastAPI · SQLite**

Alert Correlator is an independent backend project designed to identify potentially related IT incidents and monitoring alerts.

Inspired by real-world Network Operations Center (NOC) workflows, it explores how incident correlation can help operations teams identify related tickets, reduce duplicated investigation efforts, and improve incident visibility.

The system uses deterministic scoring rules, text similarity, and temporal validation to suggest correlations while preserving the original tickets.

> **Project scope:** This is an independent portfolio prototype. It does not currently integrate directly with Zabbix, ServiceNow, or other monitoring and ITSM platforms.

## The Problem

In IT operations environments, a single infrastructure failure can generate multiple alerts and incident tickets.

For example, a server outage may trigger monitoring alerts while users independently report application failures.

Without correlation, different analysts may investigate the same underlying issue separately.

Alert Correlator demonstrates a backend approach to identifying potentially related incidents using information already available in their ticket records.

## Key Features

- **Weighted incident correlation:** Evaluates shared assets, services, symptoms, descriptions, and event timestamps.
- **Explainable results:** Returns a similarity score and the reasons contributing to that score.
- **Temporal validation:** Prevents suggested correlations when valid incident activity periods are demonstrably non-overlapping.
- **Incident lifecycle support:** Stores ticket status, resolution timestamps, and closure timestamps.
- **Status history:** Records incident status changes in SQLite.
- **Persistent storage:** Uses SQLite for tickets and correlation records.
- **REST API:** Provides endpoints for creating and retrieving tickets and viewing stored correlations.
- **Automated testing:** Includes unit and API tests using Python's `unittest` and `pytest`.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and correlation logic |
| FastAPI | REST API |
| Pydantic | API request and response models |
| SQLite | Persistent ticket and correlation storage |
| `difflib.SequenceMatcher` | Description similarity |
| pytest / unittest | Automated testing |

## How Correlation Works

The correlation engine compares two tickets using the following weighted criteria:

| Criterion | Score |
|---|---:|
| Same infrastructure asset | +30 |
| Same service | +30 |
| At least one shared symptom | +20 |
| Description similarity greater than 70% | +10 |
| Event timestamps less than 10 minutes apart | +10 |
| **Maximum score** | **100** |

A score of **60 or higher** qualifies a pair of tickets for a suggested correlation.

However, the engine also checks incident activity periods. When sufficient timezone-aware timestamps demonstrate that the incidents occurred in non-overlapping periods, the correlation is rejected even if the similarity score meets the threshold.

If the temporal information is insufficient, the engine does not apply this exclusion.

The algorithm is **rule-based**, not machine learning or generative AI.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/tickets` | Create a ticket and evaluate correlations with existing tickets |
| GET | `/tickets` | List stored tickets |
| GET | `/tickets/{ticket_id}` | Retrieve a ticket by ID |
| GET | `/correlations` | List stored correlation suggestions |

### Example: Create a Ticket

**POST `/tickets`**

```json
{
  "id": "INC001",
  "ativo": "SERVER-01",
  "servico": "Database",
  "sintomas": ["timeout", "connection_error"],
  "descricao": "Database connection failures detected",
  "timestamp": "2026-10-29T10:00:00+00:00",
  "status": "aberto"
}
```

When a new ticket is stored, the application compares it against existing tickets and saves correlation suggestions that satisfy the scoring and temporal rules.

### Example: Correlation Result

A stored correlation may include:

```json
{
  "ticket1_id": "INC001",
  "ticket2_id": "INC002",
  "score": 80,
  "correlacionado": true,
  "reasons": [
    {
      "tipo": "ativo",
      "peso": 30,
      "explicacao": "Mesmo ativo: SERVER-01"
    },
    {
      "tipo": "serviço",
      "peso": 30,
      "explicacao": "Mesmo serviço: Database"
    },
    {
      "tipo": "sintoma",
      "peso": 20,
      "explicacao": "Sintomas em comum: timeout"
    }
  ]
}
```

The response explains why the incidents were considered related.

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/WelisonG/alert-correlator.git
cd alert-correlator
```

### 2. Create a Virtual Environment

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

On Linux or macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Start the API

```bash
uvicorn main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

Interactive API documentation:

`http://127.0.0.1:8000/docs`

### 5. Run the Tests

Install pytest if it is not already available:

```bash
python -m pip install pytest
```

Then run:

```bash
python -m pytest -q
```

At the time of this documentation update, **49 automated tests were passing**.

## Current Limitations

This project is a backend prototype and has several limitations:

- No direct integration with monitoring or ITSM platforms.
- No web dashboard or user authentication.
- Correlation rules use fixed weights and thresholds.
- Tickets are preserved rather than automatically merged.
- Lifecycle validation and API exposure of status transitions can be expanded.
- Correlation records are generated when tickets are created; automatic re-evaluation following lifecycle changes is not implemented.

## Future Improvements

Potential next steps include:

- Exposing incident status transitions through API endpoints.
- Strengthening request validation and lifecycle consistency.
- Supporting configurable correlation weights and thresholds.
- Re-evaluating correlations when ticket status changes.
- Adding integrations with monitoring and ITSM tools.
- Developing an operational dashboard for reviewing correlation suggestions.

## Professional Context

This project demonstrates practical concepts relevant to:

- Network Operations Center (NOC)
- IT Operations and Monitoring
- Incident Management
- Backend API Development
- Relational Data Storage
- Automated Testing

It was developed as an independent portfolio project to explore how software can support incident investigation and operational efficiency.

## Author

**Welison Pereira de Paula Gomes**

[LinkedIn](https://www.linkedin.com/in/welison-pereira-gomes/) · [GitHub](https://github.com/WelisonG)