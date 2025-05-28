# AuditTrail

Secure, Scalable, and Resilient Log Management System

AuditTrail is a backend service designed for high-throughput, cryptographically verifiable audit logging. Tailored for enterprise-grade observability, it supports JWT-authenticated access, asynchronous resilient writes, powerful query filtering, and export capabilities — all within a scalable, observable architecture deployed via Docker Swarm.

## Architecture Overview

```
+----------------+            +-----------------+             +----------------+
| Client Apps    | -- JWT --> | Django REST API | -- Async --> | Celery Workers |
+----------------+            +-----------------+             +----------------+
        |                             |                              |
        |                             |                              |
        v                             v                              v
   Auth via JWT                 MongoDB (Logs Collection)           Redis
                                |                                  |
                                v                                  v
                           Prometheus Metrics                Celery Broker
```

## Core Features

### 1. Authenticated API Endpoints
- JWT Bearer token authentication ensures secure access
- Role-based permissions for future extensibility

### 2. Asynchronous Logging Pipeline
- Celery task queue for asynchronous log processing
- Redis as the Celery broker for task distribution
- MongoDB for persistent log storage with late acknowledgment to ensure data integrity

### 3. Cryptographically Signed Logs
- Log entries are signed using a LOG_SIGNING_KEY to prevent tampering
- Signature verification ensures log integrity during retrieval

### 4. Log Query API
- Filter logs by criteria like user_id, action, and timestamps
- Pagination support for efficient data retrieval
- MongoDB indexes for optimized query performance

### 5. Observability & Metrics
- Prometheus metrics for monitoring log creation and system health
- Configurable for integration with Grafana dashboards for real-time insights

### 6. Export Capabilities
- Export logs in JSON format for archival or analysis
- Configurable retention policies for log management

### 7. Testing & CI/CD
- Unit and integration tests using Django's test framework
- CI/CD pipeline via GitHub Actions for automated testing and deployment to Docker Swarm
- Dependencies on MongoDB and Redis during testing are managed via Docker Compose

## Tech Stack

- **Backend**: Django REST Framework + Celery (Redis broker)
- **Database**: MongoDB for log storage
- **Task Queue/Cache**: Redis (Celery broker)
- **Authentication**: JWT tokens
- **Monitoring**: Prometheus (Grafana integration planned)
- **Deployment**: Docker + Docker Swarm on GCP
- **CI/CD**: GitHub Actions
- **Testing**: Django's test framework (pytest integration planned)

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- GitHub repository with secrets configured:
  - `LOG_SIGNING_KEY`: Secret key for signing logs
  - `MONGO_USERNAME` and `MONGO_PASSWORD`: MongoDB credentials
  - `SSH_USER`, `SSH_HOST`, `SSH_PRIVATE_KEY`: For deployment to Docker Swarm
  - `DOCKER_HUB_USERNAME` and `DOCKER_HUB_PASSWORD`: For Docker Hub access

### Setup Instructions

1. Clone the repo and set up the environment:
   ```bash
   git clone https://github.com/santura-dev/AuditTrail.git
   cd audittrail
   ```

2. Create a `.env` file with the following variables:
   ```env
   MONGO_USERNAME=user
   MONGO_PASSWORD=password
   LOG_SIGNING_KEY=your-secret-key-here
   ```

3. Build and start the services using Docker Compose:
   ```bash
   docker-compose up --build -d
   ```

4. Access the API at http://localhost:8000

## API Endpoints

| Endpoint | Method | Authentication | Description |
|----------|--------|----------------|-------------|
| `/logs/create/` | POST | JWT Required | Create a new audit log entry |
| `/logs/list/` | GET | JWT Required | Retrieve logs with filtering |
| `/logs/export/` | GET | JWT Required | Export logs in JSON format |

## Deployment

AuditTrail is deployed to a Docker Swarm cluster on a GCP VM using GitHub Actions. The workflow includes:

- Running tests with MongoDB and Redis dependencies
- Building and pushing the Docker image to Docker Hub
- Deploying to Docker Swarm via SSH

### CI/CD Workflow

The `deploy.yml` in `.github/workflows` automates:
- Testing with `python manage.py test`
- Building the Docker image
- Deploying to Docker Swarm on the remote GCP VM

### GCP VM Requirements

Ensure the GCP VM has:
- Docker and Docker Swarm initialized
- Firewall rules allowing ports:
  - 22 (SSH)
  - 8000 (API)
  - 27017 (MongoDB)
  - 6379 (Redis)
  - 9090 (Prometheus)

## Contributing

We welcome contributions to AuditTrail! Please feel free to submit issues and pull requests. Before contributing, please read our contributing guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.

---

