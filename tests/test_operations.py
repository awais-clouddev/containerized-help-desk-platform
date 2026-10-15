from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        self.script = self.repo / "scripts/backup_database.sh"
        self.script.write_text((ROOT / "scripts/backup_database.sh").read_text())
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=str(self.bin)+":"+os.environ["PATH"])
        self.mock("date", "echo fixed-timestamp")

    def mock(self, name, body):
        p = self.bin / name
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(0o755)

    def run_backup(self):
        return subprocess.run(
            ["bash", str(self.script)], cwd=self.root, env=self.env,
            capture_output=True, text=True, timeout=10
        )

    def test_failed_dump_leaves_no_backup_or_temporary_file(self):
        self.mock("docker", "echo partial-dump; exit 1")
        r = self.run_backup()
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(list((self.repo / "backups").iterdir()), [])

    def test_empty_dump_is_rejected(self):
        self.mock("docker", "exit 0")
        r = self.run_backup()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("backup was empty", r.stderr)
        self.assertEqual(list((self.repo / "backups").iterdir()), [])

    def test_same_timestamp_backups_are_unique_and_private(self):
        self.mock("docker", "echo '-- successful SQL dump'")
        for _ in range(2):
            r = self.run_backup()
            self.assertEqual(r.returncode, 0, r.stderr)
        files = list((self.repo / "backups").glob("*.sql"))
        self.assertEqual(len(files), 2)
        for p in files:
            self.assertEqual(p.read_text(), "-- successful SQL dump\n")
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list((self.repo / "backups").glob(".backup.*")))



class HelperTests(unittest.TestCase):
    def test_helpers_work_outside_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            scripts = repo / "scripts"
            scripts.mkdir(parents=True)
            bins = root / "bin"
            bins.mkdir()
            calls = root / "calls"
            for name in ("platform.sh", "view_logs.sh", "health_check.sh"):
                target = scripts / name
                target.write_text((ROOT / "scripts" / name).read_text())
                target.chmod(0o755)
            docker = bins / "docker"
            docker.write_text(
                '#!/bin/sh\n'
                'printf "%s|%s\\n" "$PWD" "$*" >> "$CALL_LOG"\n'
            )
            docker.chmod(0o755)
            curl = bins / "curl"
            curl.write_text("#!/bin/sh\nexit 0\n")
            curl.chmod(0o755)
            env = dict(os.environ, PATH=str(bins)+":"+os.environ["PATH"],
                       CALL_LOG=str(calls))
            for name, args in (
                ("platform.sh", ["status"]),
                ("platform.sh", ["logs", "api"]),
                ("platform.sh", ["health"]),
                ("view_logs.sh", ["postgres"]),
            ):
                r = subprocess.run(
                    ["bash", str(scripts / name), *args],
                    cwd=root, env=env, capture_output=True, text=True, timeout=10
                )
                self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            lines = calls.read_text().splitlines()
            self.assertTrue(lines)
            self.assertTrue(all(line.startswith(str(repo)+"|") for line in lines))
            before = calls.read_text()
            for name, args in (
                ("platform.sh", []),
                ("platform.sh", ["logs"]),
                ("view_logs.sh", []),
                ("view_logs.sh", ["unknown"]),
            ):
                r = subprocess.run(
                    ["bash", str(scripts / name), *args],
                    cwd=root, env=env, capture_output=True, text=True, timeout=10
                )
                self.assertNotEqual(r.returncode, 0)
                self.assertNotIn("unbound variable", r.stderr)
            self.assertEqual(calls.read_text(), before)



if __name__ == "__main__":
    unittest.main()
