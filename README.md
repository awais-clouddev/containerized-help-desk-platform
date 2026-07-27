# Containerized Help Desk Platform

A production-style, multi-container Help Desk platform built to demonstrate Docker, Docker Compose, container networking, reverse proxy routing, service health checks, persistent database storage, Redis caching, backup automation, and container operations.

This project is designed as a Cloud & DevOps portfolio project. The application itself is intentionally simple, while the main focus is on containerization, platform engineering, reliability, and operational practices.

---

## Project Overview

The platform provides a simple internal IT support ticket system where users can:

- Create support tickets
- View all tickets
- Search tickets
- Filter tickets by status and priority
- View dashboard statistics
- Store ticket data in PostgreSQL
- Use Redis for cached ticket responses

The full platform runs through Docker Compose using multiple containers.

---

## Architecture

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