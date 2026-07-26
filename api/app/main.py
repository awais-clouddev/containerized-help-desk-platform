import json
import os

import psycopg2
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Containerized Help Desk Platform")


class TicketCreate(BaseModel):
    employee_name: str
    issue: str
    priority: str


def get_database_connection():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "postgres"),
        database=os.getenv("DATABASE_NAME", "helpdesk"),
        user=os.getenv("DATABASE_USER", "helpdesk"),
        password=os.getenv("DATABASE_PASSWORD", "password"),
    )


def get_redis_connection():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=6379,
        decode_responses=True,
    )


@app.get("/")
def root():
    return {
        "message": "Containerized Help Desk Platform API is running"
    }


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
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.post("/tickets")
def create_ticket(ticket: TicketCreate):
    connection = get_database_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO tickets (employee_name, issue, priority)
        VALUES (%s, %s, %s)
        RETURNING id, employee_name, issue, priority, status, created_at;
        """,
        (
            ticket.employee_name,
            ticket.issue,
            ticket.priority,
        ),
    )

    created_ticket = cursor.fetchone()
    connection.commit()

    cursor.close()
    connection.close()

    redis_connection = get_redis_connection()
    redis_connection.delete("tickets:all")

    return {
        "id": created_ticket[0],
        "employee_name": created_ticket[1],
        "issue": created_ticket[2],
        "priority": created_ticket[3],
        "status": created_ticket[4],
        "created_at": str(created_ticket[5]),
    }


@app.get("/tickets")
def get_tickets():
    redis_connection = get_redis_connection()
    cached_tickets = redis_connection.get("tickets:all")

    if cached_tickets:
        return {
            "source": "redis-cache",
            "tickets": json.loads(cached_tickets),
        }

    connection = get_database_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            employee_name,
            issue,
            priority,
            status,
            created_at
        FROM tickets
        ORDER BY created_at DESC;
        """
    )

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

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

    redis_connection.setex(
        "tickets:all",
        60,
        json.dumps(tickets),
    )

    return {
        "source": "postgresql",
        "tickets": tickets,
    }