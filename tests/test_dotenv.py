"""Tests that a .env file is actually loaded.

.env.example exists and README points at it, but nothing called load_dotenv,
so the file was read by no one. That mattered most for the budget alerts:
AlertConfig.from_env reads SMTP_HOST, SMTP_USER, SMTP_PASSWORD and
ALERT_RECIPIENT, so email alerts could not be switched on through the
documented route at all.

These tests run in a subprocess with a temporary working directory, because
load_dotenv runs at import time and os.environ cannot be un-imported between
test cases.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SMTP_VARS = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "ALERT_RECIPIENT")

# Import api.main so the .env is loaded, then report what the alert config
# ends up with.
PROBE = (
    "import api.main; "
    "from agents.alert_service import AlertConfig; "
    "c = AlertConfig.from_env(); "
    "print('HOST=' + c.smtp_host); "
    "print('USER=' + c.smtp_user); "
    "print('RECIPIENT=' + c.recipient); "
    "print('CONFIGURED=' + str(c.is_configured))"
)


def _run_probe(cwd: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    full_env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    # Ignore anything the developer happens to have exported.
    for var in SMTP_VARS:
        full_env.pop(var, None)
    if env:
        full_env.update(env)

    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=cwd,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    values = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            values[key] = value
    return values


class TestDotenvLoading:
    def test_alert_config_reads_env_file(self, tmp_path):
        """SMTP settings in .env reach AlertConfig, so alerts can be enabled."""
        (tmp_path / ".env").write_text(
            "SMTP_HOST=smtp.example.com\n"
            "SMTP_USER=someone@example.com\n"
            "SMTP_PASSWORD=secret\n"
            "ALERT_RECIPIENT=someone@example.com\n"
        )
        values = _run_probe(tmp_path)
        assert values["HOST"] == "smtp.example.com"
        assert values["USER"] == "someone@example.com"
        assert values["CONFIGURED"] == "True"

    def test_alerts_stay_off_without_env_file(self, tmp_path):
        """Without configuration the alert service reports itself unconfigured."""
        values = _run_probe(tmp_path)
        assert values["HOST"] == ""
        assert values["CONFIGURED"] == "False"

    def test_real_environment_wins_over_env_file(self, tmp_path):
        """An exported variable overrides the file, which is what Docker relies on."""
        (tmp_path / ".env").write_text("SMTP_HOST=from-the-file\n")
        values = _run_probe(tmp_path, {"SMTP_HOST": "from-the-environment"})
        assert values["HOST"] == "from-the-environment"
