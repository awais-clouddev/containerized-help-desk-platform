# Architecture Overview

## System Flow

Browser traffic enters the platform through the Nginx reverse proxy. Nginx routes frontend requests to the frontend container and API requests to the FastAPI backend container.

The API communicates privately with PostgreSQL for persistent ticket storage and Redis for cached ticket responses.

```text
Browser
   |
   v
Nginx Reverse Proxy
   |
   +------------------> Frontend Container
   |
   +------------------> FastAPI Backend Container
                              |
                              +------> PostgreSQL Database
                              |
                              +------> Redis Cache
```

## Service Responsibilities

| Service | Responsibility |
|---|---|
| Nginx | Single public entry point and reverse proxy |
| Frontend | User interface for ticket creation, search, and dashboard |
| API | Business logic, health checks, ticket APIs, database/cache access |
| PostgreSQL | Persistent ticket storage |
| Redis | Temporary cache for faster ticket responses |

## Network Design

| Network | Connected Services | Purpose |
|---|---|---|
| frontend_network | Nginx, Frontend, API | Public-facing application routing |
| backend_network | API, PostgreSQL, Redis | Private internal backend communication |

PostgreSQL and Redis are intentionally not exposed to the host machine. Only internal containers can access them through the backend network.

## Reliability Design

The platform includes:

- Docker health checks
- Restart policies
- Persistent database volume
- Backup and restore automation
- Platform health validation script
- Container log viewing script

## Security Design

The platform includes:

- Non-root API container user
- Private backend services
- Environment-variable based configuration
- `.env` ignored from Git
- Optimized Docker build context
