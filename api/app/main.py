import json
import os

import psycopg2
import redis
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Containerized Help Desk Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
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
    except Exception as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.post("/tickets", status_code=201)
def create_ticket(ticket: TicketCreate):
    connection = get_database_connection()
    cursor = connection.cursor()

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
    cursor.close()
    connection.close()

    get_redis_connection().delete("tickets:all")

    return {
        "id": created_ticket[0],
        "employee_name": created_ticket[1],
        "issue": created_ticket[2],
        "priority": created_ticket[3],
        "status": created_ticket[4],
        "created_at": str(created_ticket[5]),
    }


@app.get("/tickets")
def get_tickets(search: str = Query(default="")):
    redis_connection = get_redis_connection()
    cache_key = f"tickets:search:{search.lower()}"

    cached_tickets = redis_connection.get(cache_key)

    if cached_tickets:
        return {
            "source": "redis-cache",
            "tickets": json.loads(cached_tickets),
        }

    connection = get_database_connection()
    cursor = connection.cursor()

    if search:
        search_pattern = f"%{search}%"

        cursor.execute(
            """
            SELECT id, employee_name, issue, priority, status, created_at
            FROM tickets
            WHERE employee_name ILIKE %s
               OR issue ILIKE %s
               OR CAST(id AS TEXT) ILIKE %s
            ORDER BY created_at DESC;
            """,
            (search_pattern, search_pattern, search_pattern),
        )
    else:
        cursor.execute(
            """
            SELECT id, employee_name, issue, priority, status, created_at
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
        cache_key,
        60,
        json.dumps(tickets),
    )

    return {
        "source": "postgresql",
        "tickets": tickets,
    }

@app.patch("/tickets/{ticket_id}/status")
def update_ticket_status(ticket_id: int, update: TicketStatusUpdate):
    connection = get_database_connection()
    cursor = connection.cursor()

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
        cursor.close()
        connection.close()
        raise HTTPException(status_code=404, detail="Ticket not found")

    connection.commit()
    cursor.close()
    connection.close()

    get_redis_connection().delete("tickets:all")

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
    connection = get_database_connection()
    cursor = connection.cursor()

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

    cursor.close()
    connection.close()

    return {
        "total": total,
        "open": open_count,
        "in_progress": progress_count,
        "resolved": resolved_count,
        "critical": critical_count,
    }
