# Internal-Developer-Platform

# Internal Developer Platform (IDP) - Provisioning Service

A self-service infrastructure provisioning system designed for R&D engineers. This platform minimizes DevOps intervention by allowing developers to trigger environment creation on-demand, ensuring scalability, reliability, and automated lifecycle management.

## Architecture

The system follows a **Producer-Consumer** pattern, decoupling the API layer from the heavy infrastructure provisioning tasks. This ensures high availability and resilience under load.

## Technical Stack

* **API Layer:** FastAPI (Async) for high-concurrency request handling.
* **Task Queue:** Celery with Redis for asynchronous background task processing and fault tolerance.
* **Database:** PostgreSQL (using SQLAlchemy 2.0 Async) for state management and transaction consistency.
* **Security & Reliability:**
* API Key authentication.
* Rate Limiting (`slowapi`) to protect system resources.
* Idempotency enforcement via partial unique database indexes.



## Key Features

* **Self-Service:** Automated environment provisioning via a CLI tool.
* **TTL Management:** Automated lifecycle tracking for temporary environments to optimize cloud costs.
* **Conflict Prevention:** Prevents race conditions and duplicate environment creation.
* **Resilient Design:** Asynchronous task execution ensures that infrastructure tasks persist even if the API server restarts.

## Quick Start

### 1. Installation

Install the necessary dependencies:

```bash
pip install fastapi uvicorn celery redis sqlalchemy asyncpg slowapi

```

### 2. Infrastructure Setup

Ensure Redis is running (default port 6379):

```bash
docker run -p 6379:6379 redis

```

### 3. Run the Worker

Start the Celery worker to process provisioning tasks:

```bash
celery -A tasks worker --loglevel=info --pool=solo

```

### 4. Run the API

Start the FastAPI server:

```bash
uvicorn main:app --reload --port 8001

```

## CLI Usage

Trigger a new environment provisioning request:

```bash
python cli.py --env staging --service payment-api --ttl 4h

```

## Production Considerations

* **Security:** Replace hardcoded API keys with environment variables (Secrets Management).
* **Deployment:** Use Docker Compose for consistent development environments and Kubernetes for scalable production deployments.
* **Observability:** Integrate with monitoring tools (e.g., Prometheus, ELK stack) to track task success rates and system performance.
