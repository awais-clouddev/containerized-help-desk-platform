# Operations and Recovery

This is an independent local portfolio lab using demonstration data.

## Startup

From the repository root:

    cp .env.example .env

Only copy the example on first setup; preserve an existing .env.
Set database credentials consistently before initialising a fresh volume.

    docker compose up -d --build --wait --wait-timeout 120
    bash scripts/health_check.sh

Compose waits for dependency health. The helper allows bounded retries.
A failed build or readiness wait returns an error for investigation.

    docker compose ps -a
    docker compose logs --tail=100 api postgres redis nginx

Restart policies do not automatically restart an unhealthy running container.
Stopping the platform preserves its named database volume:

    docker compose down

Do not add --volumes when preserving application data.

## Backup

    bash scripts/backup_database.sh

The helper uses the PostgreSQL service's configured database/user.
Only completed, nonempty dumps are published under backups/.
Backup filenames are unique and new files use mode 0600.
Keep copies outside the Docker host for protection against host loss.
Off-host backup scheduling and retention are future production work.

## Restore

Restore only trusted SQL dumps. SQL dumps contain executable commands.
The target must already exist, be empty and have no concurrent writers.

Create a separate recovery database:

    docker compose exec -T postgres sh -c 'exec createdb -T template0 -U "$POSTGRES_USER" recovered_helpdesk'

Restore into it:

    bash scripts/restore_database.sh /absolute/path/backup.sql --database recovered_helpdesk

The original application database is preserved.
A SQL error rolls back the restore transaction.
Inspect recovered data and test the application before deciding on cutover.

For a deliberate cutover, stop incoming application traffic, update
DATABASE_NAME to the recovered database, and recreate the API container.
Keep the old database until recovery is accepted.

Clear ticket cache keys before reopening traffic:

    docker compose exec -T api python -c 'from app.main import get_redis_connection; r=get_redis_connection(); [r.delete(k) for k in r.scan_iter("tickets:*")]; print("Ticket cache cleared")'

If Redis is unavailable, do not assume old cached results have been removed.
Complete cache recovery/clearing before reopening traffic when fresh reads
are required. Normal cache TTL is 60 seconds.

## Health and Timeouts

Database connection timeout defaults to 5 seconds.
Statement timeout defaults to 5000 ms; lock timeout to 3000 ms.
Redis connection/socket timeouts default to 2 seconds with client retries disabled.
These limits are not a guarantee of an overall request deadline under load.

The health helper defaults to 12 attempts per endpoint, 2 seconds between
attempts, a 2-second connection timeout and a 5-second request timeout.
HEALTH_ATTEMPTS, HEALTH_RETRY_DELAY and HEALTH_BASE_URL configure the helper.

Ticket operations can use PostgreSQL during Redis failure.
The strict dependency health endpoint still returns 503.
PostgreSQL failure prevents database operations; investigate logs and storage.
Never delete a volume as a troubleshooting shortcut.

## Local Exposure

Only the gateway publishes a port: 127.0.0.1:8090.
Database/cache ports are not published. Docker networks are not access controls.
There is no authentication or authorisation; use disposable demo data only.

## Evidence

Screenshots are historical examples. Test results establish the tested local
scenarios, not production availability, browser layout or automatic failover.
