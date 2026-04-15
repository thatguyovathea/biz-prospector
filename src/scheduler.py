"""Crontab scheduler management for biz-prospector.

Generates, installs, lists, and removes crontab entries
for scheduled pipeline runs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()

MARKER = "# biz-prospector:"


def _validate_job(job: dict) -> list[str]:
    """Validate a job config dict. Returns list of error strings."""
    errors = []
    if not job.get("name"):
        errors.append("Job missing 'name'")
    if job.get("_type") != "re_enrich":
        if not job.get("vertical"):
            errors.append(f"Job '{job.get('name', '?')}' missing 'vertical'")
        if not job.get("metro"):
            errors.append(f"Job '{job.get('name', '?')}' missing 'metro'")
    cron = job.get("cron", "")
    if not cron or len(cron.split()) != 5:
        errors.append(f"Job '{job.get('name', '?')}' has invalid cron expression: '{cron}'")
    return errors


def _build_cron_entry(job: dict, python_path: str, project_dir: str) -> str:
    """Build a crontab entry string from a job config dict."""
    name = job["name"]
    cron = job["cron"]

    if job.get("_type") == "re_enrich":
        max_age = job.get("max_age_days", 30)
        cmd = f"{python_path} -m src.pipeline re-enrich --max-age {max_age} --notify"
    else:
        vertical = job["vertical"]
        metro = job["metro"]
        count = job.get("count", 100)
        cmd = f"{python_path} -m src.pipeline run --vertical {vertical} --metro {metro} --count {count} --notify"
        if job.get("push_instantly"):
            cmd += " --push-instantly"

    log_path = f"data/logs/{name}.log"
    return f"{MARKER}{name}\n{cron} cd {project_dir} && {cmd} >> {log_path} 2>&1"


def _read_crontab() -> str:
    """Read current user crontab."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _write_crontab(content: str):
    """Write content to user crontab."""
    subprocess.run(
        ["crontab", "-"],
        input=content,
        text=True,
        check=True,
    )


def _strip_biz_entries(crontab: str) -> tuple[list[str], int]:
    """Remove all biz-prospector entries from crontab lines.

    Returns cleaned lines and count of removed entries.
    """
    lines = crontab.splitlines()
    cleaned = []
    skip_next = False
    removed = 0
    for line in lines:
        if line.startswith(MARKER):
            skip_next = True
            removed += 1
            continue
        if skip_next:
            skip_next = False
            continue
        cleaned.append(line)
    return cleaned, removed


def install_jobs(settings: dict) -> list[str]:
    """Generate and install crontab entries from settings.

    Returns list of installed job names.
    Raises ValueError if any job fails validation.
    """
    schedule = settings.get("schedule", {})
    jobs = list(schedule.get("jobs", []))

    # Add re-enrich job if enabled
    re_enrich = schedule.get("re_enrich", {})
    if re_enrich.get("enabled"):
        jobs.append({
            "name": "re-enrich",
            "cron": re_enrich.get("cron", "0 2 * * 0"),
            "max_age_days": re_enrich.get("max_age_days", 30),
            "_type": "re_enrich",
        })

    # Validate all jobs
    all_errors = []
    for job in jobs:
        errors = _validate_job(job)
        all_errors.extend(errors)
    if all_errors:
        raise ValueError(f"Job validation failed:\n" + "\n".join(all_errors))

    # Build entries
    python_path = sys.executable
    project_dir = str(Path.cwd())

    entries = []
    names = []
    for job in jobs:
        entries.append(_build_cron_entry(job, python_path, project_dir))
        names.append(job["name"])

    # Read existing crontab, strip old biz-prospector entries
    existing = _read_crontab()
    cleaned, _ = _strip_biz_entries(existing)

    # Build new crontab
    new_lines = cleaned + [""] + entries + [""]
    new_crontab = "\n".join(new_lines) + "\n"

    # Create log directory
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    _write_crontab(new_crontab)
    return names


def list_jobs() -> list[dict]:
    """Read crontab and return biz-prospector jobs."""
    crontab = _read_crontab()
    if not crontab:
        return []

    jobs = []
    lines = crontab.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(MARKER):
            name = line[len(MARKER):]
            # Next line is the cron entry
            if i + 1 < len(lines):
                cron_line = lines[i + 1]
                parts = cron_line.split(None, 5)
                schedule = " ".join(parts[:5]) if len(parts) >= 5 else cron_line
                jobs.append({"name": name, "schedule": schedule, "command": cron_line})
    return jobs


def remove_jobs() -> int:
    """Remove all biz-prospector entries from crontab.

    Returns count of removed entries.
    """
    existing = _read_crontab()
    if not existing:
        return 0

    cleaned, removed = _strip_biz_entries(existing)
    if removed > 0:
        _write_crontab("\n".join(cleaned) + "\n")
    return removed
