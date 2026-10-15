import hashlib
import json
import os
import logging
from contextlib import contextmanager

import psycopg2
import redis
from redis.exceptions import RedisError
from redis.retry import Retry
from redis.backoff import NoBackoff
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

app = FastAPI(title="Containerized Help Desk Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8090", "http://localhost:8081"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TicketCreate(BaseModel):
    employee_name: str = Field(min_length=2, max_length=100)
    issue: str = Field(min_length=5, max_length=500)
    priority: str = Field(pattern="^(Low|Medium|High|Critical)$")


class TicketStatusUpdate(BaseModel):
    status: str = Field(
        pattern="^(Open|Assigned|In Progress|Waiting|Resolved|Closed)$"
    )



class TicketRead(TicketCreate):
    id: int = Field(gt=0)
    status: str = Field(
        pattern="^(Open|Assigned|In Progress|Waiting|Resolved|Closed)$"
    )
    created_at: str


TICKET_CACHE_ADAPTER = TypeAdapter(list[TicketRead])



logger = logging.getLogger(__name__)


def positive_setting(name, default):
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@contextmanager
def database_session():
    connection = get_database_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        yield connection, cursor
    except Exception:
        try:
            connection.rollback()
        except Exception:
            logger.exception("Database rollback failed")
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()


def get_database_connection():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "postgres"),
        database=os.getenv("DATABASE_NAME", "helpdesk"),
        user=os.getenv("DATABASE_USER", "helpdesk"),
        password=os.getenv("DATABASE_PASSWORD", "password"),
        connect_timeout=positive_setting("DB_CONNECT_TIMEOUT", 5),
        options=(
            f"-c statement_timeout={positive_setting('DB_STATEMENT_TIMEOUT_MS', 5000)} "
            f"-c lock_timeout={positive_setting('DB_LOCK_TIMEOUT_MS', 3000)}"
        ),
    )


def get_redis_connection():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=6379,
        decode_responses=True,
        socket_connect_timeout=positive_setting("CACHE_CONNECT_TIMEOUT", 2),
        socket_timeout=positive_setting("CACHE_SOCKET_TIMEOUT", 2),
        retry=Retry(NoBackoff(), 0),
    )


def clear_ticket_cache():
    redis_connection = get_redis_connection()

    try:
        for key in redis_connection.scan_iter("tickets:*"):
            redis_connection.delete(key)
    except RedisError:
        pass  # Redis is optional; PostgreSQL remains authoritative.


@app.get("/")
def root():
    return {"message": "Containerized Help Desk Platform API is running"}


@app.get("/health")
def health():
    try:
        database_connection = get_database_connection()
        database_connection.close()

        redis_connection = get_redis_connection()
        redis_connection.ping()

        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
        }
    except Exception:
        logger.exception("Dependency health check failed")
        raise HTTPException(status_code=503, detail="Dependencies unavailable") from None


@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketCreate):
    with database_session() as (connection, cursor):

        cursor.execute(
            """
            INSERT INTO tickets (employee_name, issue, priority)
            VALUES (%s, %s, %s)
            RETURNING id, employee_name, issue, priority, status, created_at;
            """,
            (ticket.employee_name, ticket.issue, ticket.priority),
        )

        created_ticket = cursor.fetchone()
        connection.commit()

    clear_ticket_cache()

    return {
        "id": created_ticket[0],
        "employee_name": created_ticket[1],
        "issue": created_ticket[2],
        "priority": created_ticket[3],
        "status": created_ticket[4],
        "created_at": str(created_ticket[5]),
    }


@app.get("/tickets")
def get_tickets(
    search: str = Query(default=""),
    status: str = Query(default=""),
    priority: str = Query(default=""),
):
    redis_connection = get_redis_connection()


    normalized_filters = [search.lower(), status.lower(), priority.lower()]
    cache_key = "tickets:" + hashlib.sha256(
        json.dumps(normalized_filters, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    try:
        cached_tickets = redis_connection.get(cache_key)
        if cached_tickets is not None:
            validated = TICKET_CACHE_ADAPTER.validate_json(cached_tickets)
            return {
                "source": "redis-cache",
                "tickets": [ticket.model_dump() for ticket in validated],
            }
    except (RedisError, ValidationError):
        pass  # Invalid/unavailable cache falls back to PostgreSQL.

    with database_session() as (connection, cursor):

        conditions = []
        parameters = []

        if search:
            search_pattern = f"%{search}%"
            conditions.append(
                """
                (
                    employee_name ILIKE %s
                    OR issue ILIKE %s
                    OR CAST(id AS TEXT) ILIKE %s
                )
                """
            )
            parameters.extend(
                [search_pattern, search_pattern, search_pattern]
            )

        if status:
            conditions.append("LOWER(status) = %s")
            parameters.append(status.lower())

        if priority:
            conditions.append("LOWER(priority) = %s")
            parameters.append(priority.lower())

        query = """
            SELECT id, employee_name, issue, priority, status, created_at
            FROM tickets
        """

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC;"

        cursor.execute(query, parameters)
        rows = cursor.fetchall()


    tickets = [
        {
            "id": row[0],
            "employee_name": row[1],
            "issue": row[2],
            "priority": row[3],
            "status": row[4],
            "created_at": str(row[5]),
        }
        for row in rows
    ]

    try:
        redis_connection.setex(
            cache_key,
            60,
            json.dumps(tickets),
        )
    except RedisError:
        pass

    return {
        "source": "postgresql",
        "tickets": tickets,
    }


@app.patch("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: int, update: TicketStatusUpdate):
    with database_session() as (connection, cursor):

        cursor.execute(
            """
            UPDATE tickets
            SET status = %s
            WHERE id = %s
            RETURNING id, employee_name, issue, priority, status, created_at;
            """,
            (update.status, ticket_id),
        )

        updated_ticket = cursor.fetchone()

        if updated_ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        connection.commit()

    clear_ticket_cache()

    return {
        "id": updated_ticket[0],
        "employee_name": updated_ticket[1],
        "issue": updated_ticket[2],
        "priority": updated_ticket[3],
        "status": updated_ticket[4],
        "created_at": str(updated_ticket[5]),
    }


@app.get("/dashboard")
def dashboard_summary():
    with database_session() as (connection, cursor):

        cursor.execute("SELECT COUNT(*) FROM tickets;")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='Open';")
        open_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='In Progress';")
        progress_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status='Resolved';")
        resolved_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE priority='Critical';")
        critical_count = cursor.fetchone()[0]


    return {
        "total": total,
        "open": open_count,
        "in_progress": progress_count,
        "resolved": resolved_count,
        "critical": critical_count,
    }
