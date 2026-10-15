"""Explicit integration drill; preserves the application's source database."""
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def command(args, check=True):
    r = subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, timeout=120
    )
    if check and r.returncode:
        raise RuntimeError(r.stderr or r.stdout)
    return r


def postgres(script, *args):
    return command([
        "docker", "compose", "exec", "-T", "postgres",
        "sh", "-c", script, "sh", *args
    ])


def read_tickets(database=""):
    return postgres(
        'exec psql -X -v ON_ERROR_STOP=1 -At -U "$POSTGRES_USER" '
        '-d "${1:-$POSTGRES_DB}" -c '
        "'SELECT row_to_json(t) FROM public.tickets t ORDER BY id;'",
        database
    ).stdout


def main():
    suffix = uuid.uuid4().hex[:12]
    restored = "restore_drill_" + suffix
    failed = "restore_failed_" + suffix
    created = []

    before = read_tickets()
    backup_output = command(["bash", "scripts/backup_database.sh"]).stdout
    marker = "Database backup created: "
    backup = next(
        line[len(marker):] for line in backup_output.splitlines()
        if line.startswith(marker)
    )

    try:
        for database in (restored, failed):
            postgres(
                'exec createdb -T template0 -U "$POSTGRES_USER" "$1"',
                database
            )
            created.append(database)

        command([
            "bash", "scripts/restore_database.sh", backup,
            "--database", restored
        ])
        assert read_tickets(restored) == before, "Restored ticket data differs"
        print("PASS: real backup restored with matching ticket data")

        again = command([
            "bash", "scripts/restore_database.sh", backup,
            "--database", restored
        ], check=False)
        assert again.returncode != 0
        assert "must be empty" in again.stderr
        assert read_tickets(restored) == before
        print("PASS: nonempty target rejected without changing its data")

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "invalid.sql"
            bad.write_text(
                "CREATE TABLE public.restore_probe(id integer);\n"
                "SELECT 1/0;\n"
            )
            result = command([
                "bash", "scripts/restore_database.sh", str(bad),
                "--database", failed
            ], check=False)
            assert result.returncode != 0, "Invalid SQL unexpectedly succeeded"
            probe = postgres(
                'exec psql -X -v ON_ERROR_STOP=1 -At '
                '-U "$POSTGRES_USER" -d "$1" '
                '-c "SELECT to_regclass(\'public.restore_probe\');"',
                failed
            ).stdout.strip()
            assert not probe, "Failed restore left a table behind"
        print("PASS: failed restore rolled back its database changes")

        assert read_tickets() == before, "Source ticket data changed during drill"
        print("PASS: source ticket data unchanged")
    finally:
        for database in reversed(created):
            postgres('exec dropdb -U "$POSTGRES_USER" "$1"', database)
        print("Disposable drill databases removed")


if __name__ == "__main__":
    main()
