"""Explicit Docker integration drill using a separate project and volumes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    project = "helpdesk-drill-" + uuid.uuid4().hex[:10]

    with tempfile.TemporaryDirectory(prefix="helpdesk-drill-") as tmp:
        root = Path(tmp)
        for folder in ("api", "frontend", "database", "nginx", "scripts", "tests"):
            shutil.copytree(
                ROOT / folder, root / folder,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )

        compose = (ROOT / "compose.yaml").read_text()
        compose = "\n".join(
            line for line in compose.splitlines()
            if "container_name:" not in line
        ) + "\n"
        assert '"127.0.0.1:8090:80"' in compose
        compose = compose.replace('"127.0.0.1:8090:80"', '"127.0.0.1::80"')
        old = 'pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}'
        assert old in compose
        compose = compose.replace(old, "test -f /tmp/drill-ready && " + old)
        compose = compose.replace("interval: 30s", "interval: 1s")
        compose = compose.replace("retries: 3", "retries: 30")
        compose = compose.replace("start_period: 20s", "start_period: 1s")
        compose = compose.replace("start_period: 10s", "start_period: 1s")
        (root / "compose.yaml").write_text(compose)

        password = uuid.uuid4().hex
        (root / ".env").write_text(
            f"COMPOSE_PROJECT_NAME={project}\n"
            "DATABASE_HOST=postgres\nDATABASE_NAME=drill\n"
            "DATABASE_USER=drill\n"
            f"DATABASE_PASSWORD={password}\n"
            "POSTGRES_DB=drill\nPOSTGRES_USER=drill\n"
            f"POSTGRES_PASSWORD={password}\nREDIS_HOST=redis\n"
        )
        env = dict(os.environ, COMPOSE_PROJECT_NAME=project)
        for key in ("COMPOSE_FILE", "COMPOSE_PROFILES",
                    "DATABASE_HOST", "DATABASE_NAME", "DATABASE_USER",
                    "DATABASE_PASSWORD", "POSTGRES_DB", "POSTGRES_USER",
                    "POSTGRES_PASSWORD", "REDIS_HOST"):
            env.pop(key, None)

        def command(args, check=True, timeout=180):
            result = subprocess.run(
                args, cwd=root, env=env, capture_output=True,
                text=True, timeout=timeout
            )
            if check and result.returncode:
                raise RuntimeError(result.stderr + "\n" + result.stdout)
            return result

        def dc(*args, **kwargs):
            return command(["docker", "compose", *args], **kwargs)

        try:
            print("Building disposable stack...", flush=True)
            dc("build", timeout=900)
            dc("up", "-d", "postgres", "redis", "frontend")

            def release_database_health():
                time.sleep(3)
                dc("exec", "-T", "postgres", "touch", "/tmp/drill-ready")

            with ThreadPoolExecutor(max_workers=1) as pool:
                release = pool.submit(release_database_health)
                dc("up", "-d", "--wait", "--wait-timeout", "180")
                release.result()
            print("PASS: clean startup with delayed database health", flush=True)

            address = dc("port", "nginx", "80").stdout.strip()
            base = "http://" + address

            def request(path, method="GET", payload=None):
                data = None if payload is None else json.dumps(payload).encode()
                req = Request(
                    base + path, data=data, method=method,
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urlopen(req, timeout=15) as response:
                        body = response.read()
                        return response.status, json.loads(body) if body else None
                except HTTPError as error:
                    body = error.read()
                    try:
                        body = json.loads(body)
                    except ValueError:
                        body = body.decode()
                    return error.code, body

            code, health = request("/api/health")
            assert code == 200 and health["status"] == "healthy"

            code, ticket = request("/api/tickets", "POST", {
                "employee_name": "Integration Drill",
                "issue": "Disposable integration ticket",
                "priority": "High"
            })
            assert code == 201, (code, ticket)
            ticket_id = ticket["id"]

            for priority in ("high", "High"):
                code, result = request("/api/tickets?priority=" + priority)
                assert code == 200
                assert ticket_id in [t["id"] for t in result["tickets"]]

            code, changed = request(
                f"/api/tickets/{ticket_id}/status",
                "PATCH", {"status": "Resolved"}
            )
            assert code == 200 and changed["status"] == "Resolved"
            code, result = request("/api/tickets?status=resolved")
            assert code == 200
            assert ticket_id in [t["id"] for t in result["tickets"]]
            print("PASS: gateway create/read/filter/update flow", flush=True)

            dc("stop", "redis")
            code, _ = request("/api/health")
            assert code == 503
            code, result = request("/api/tickets", "POST", {
                "employee_name": "Redis Failure Drill",
                "issue": "Database write while Redis is stopped",
                "priority": "Low"
            })
            assert code == 201, (code, result)
            code, result = request("/api/tickets")
            assert code == 200 and result["source"] == "postgresql"
            print("PASS: Redis-down writes and database fallback", flush=True)

            dc("up", "-d", "--wait", "--wait-timeout", "120", "redis")
            # This Redis belongs exclusively to this disposable drill.
            dc("exec", "-T", "redis", "redis-cli", "FLUSHDB")

            dc("stop", "postgres")
            started = time.monotonic()
            code, _ = request("/api/dashboard")
            assert code >= 500
            assert time.monotonic() - started < 15
            print("PASS: database failure returns an error within timeout", flush=True)
            dc("up", "-d", "--wait", "--wait-timeout", "120", "postgres")

            command([sys.executable, "tests/restore_drill.py"])
            print("PASS: real restore, nonempty-target protection and rollback", flush=True)
            print("All disposable integration checks passed.", flush=True)
        finally:
            cleanup = dc(
                "down", "--volumes", "--remove-orphans", "--rmi", "local",
                check=False
            )
            if cleanup.returncode:
                raise RuntimeError(
                    f"Cleanup failed for disposable project {project}:\n"
                    + cleanup.stderr
                )
            print("Disposable containers, volumes and build images removed.", flush=True)


if __name__ == "__main__":
    main()
