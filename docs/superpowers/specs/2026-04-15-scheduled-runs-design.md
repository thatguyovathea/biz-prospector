# Scheduled Pipeline Runs with Email Summary — Design Spec

## Goal

Automate recurring pipeline runs via system cron and deliver weekly email briefings of outreach targets, so the user can plan each week's outreach from their inbox without manually running the CLI.

## Why This Matters

The pipeline currently requires manual invocation for every vertical/metro combination. For a user running 4–8 verticals across multiple metros, that's tedious and easy to forget. Scheduled runs turn the pipeline into a "set and forget" lead generation system that delivers fresh targets weekly.

## Approach

**System cron + CLI commands.** Each scheduled job is a crontab entry that calls `python -m src.pipeline run` with the right flags. No long-running daemon, no new dependencies. Cron handles timing; the CLI handles execution. A thin management layer (install/list/remove) generates crontab entries from YAML config.

**Summary email after each run.** Uses Python's built-in `smtplib` and `email` packages to send an HTML digest with the run's top leads, key stats, and the full HTML report attached.

## Config Changes (`config/settings.example.yaml`)

New `schedule` section:

```yaml
schedule:
  # Prospecting jobs — each becomes a crontab entry
  jobs:
    - name: "hvac-portland"
      vertical: hvac
      metro: portland-or
      cron: "0 6 * * 1"          # Every Monday at 6am
      count: 100
      push_instantly: false

    - name: "dental-seattle"
      vertical: dental
      metro: seattle-wa
      cron: "0 6 * * 3"          # Every Wednesday at 6am
      count: 100

  # Re-enrichment of stale leads
  re_enrich:
    enabled: false
    cron: "0 2 * * 0"            # Every Sunday at 2am
    max_age_days: 30              # Re-enrich leads scored more than 30 days ago

  # Email notification after scheduled runs
  summary_email:
    enabled: false
    to: ""                        # Recipient address
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: ""                 # Or set env var BIZ_SMTP_USER
    smtp_password: ""             # Or set env var BIZ_SMTP_PASSWORD
    subject_prefix: "[biz-prospector]"
```

All schedule features are disabled/empty by default. The user copies `settings.example.yaml` to `settings.yaml`, fills in their jobs and SMTP credentials, then runs `schedule install`.

## New CLI Commands

### `python -m src.pipeline schedule install`

Reads `schedule.jobs` and `schedule.re_enrich` from settings. For each job, generates a crontab entry:

```
# biz-prospector:hvac-portland
0 6 * * 1 cd /path/to/biz-prospector && /path/to/python -m src.pipeline run --vertical hvac --metro portland-or --count 100 --notify >> data/logs/hvac-portland.log 2>&1
```

Key details:
- Each entry is prefixed with a comment marker `# biz-prospector:<job-name>` for identification
- Uses absolute paths to the Python interpreter and project directory (resolved at install time via `sys.executable` and `Path.cwd()`)
- Appends `--notify` flag so the summary email is sent
- Logs stdout/stderr to `data/logs/<job-name>.log`
- Reads current crontab, removes any existing biz-prospector entries, writes new ones
- If `re_enrich.enabled` is true, adds a crontab entry for `python -m src.pipeline re-enrich --notify`

### `python -m src.pipeline schedule list`

Reads current crontab, filters to lines with `# biz-prospector:` marker, displays them in a formatted table:

```
Job              Schedule          Next Run
hvac-portland    Mon 6:00 AM       Apr 21, 2026
dental-seattle   Wed 6:00 AM       Apr 16, 2026
re-enrich        Sun 2:00 AM       Apr 20, 2026
```

### `python -m src.pipeline schedule remove`

Reads current crontab, removes all lines with `# biz-prospector:` marker, writes back. Confirms before removing.

### `python -m src.pipeline re-enrich`

New pipeline command that refreshes stale leads:

1. Scans `data/scored/` for JSON files
2. Loads all leads, filters to those where `enriched_at` is older than `max_age_days` (from config)
3. Runs them through the async enrichment processor (same as Stage 2)
4. Re-scores them (same as Stage 3)
5. Saves updated results back to `data/scored/` (overwrites the source file)
6. If `--notify` flag is set and `summary_email` is configured, sends a summary

This does NOT re-scrape or generate new outreach. It refreshes enrichment data (website audit, reviews, job postings, employee titles) and recalculates scores, so previously scored leads get accurate current data.

Options:
- `--max-age DAYS` — override `max_age_days` from config
- `--notify` — send summary email after completion

### `--notify` flag on existing `run` command

Add `--notify` flag to the existing `run` command. When set and `summary_email` is configured, sends a run summary email after pipeline completion. Scheduled runs always include this flag; manual runs don't unless explicitly passed.

## Email Summary Module

### New Module: `src/notifications/email_summary.py`

Single-responsibility module for composing and sending run summary emails.

### `send_run_summary(leads, run_info, settings)`

**Parameters:**
- `leads` — list of scored/outreach leads from the run
- `run_info` — dict with `vertical`, `metro`, `timestamp`, `scraped_count`, `qualified_count`, `threshold`, `is_re_enrich` (bool)
- `settings` — full settings dict (for SMTP config)

**Email structure:**

Subject: `[biz-prospector] HVAC Portland — 12 new targets (Week of Apr 14)`

Body (HTML):

```
Run Summary
───────────
Vertical: HVAC | Metro: Portland, OR
Scraped: 87 | Enriched: 87 | Qualified: 12 (threshold: 55)
Run time: 2026-04-14 06:00

Top 10 Leads
─────────────────────────────────────────────────────
Score  Business              Contact         Signals
78.5   Acme HVAC             Bob (Owner)     No CRM, 3 manual roles
72.1   Portland Air Co       Jane (CEO)      No scheduling, 2 complaints
...

Quick Stats
───────────
Average score: 68.4 | Highest: 78.5
With contact email: 10/12 (83%)
Net new: 9 | Previously seen: 3

Full report attached.
```

**Attachment:** The HTML report file that `save_report()` already generates, attached as `<job-name>-report.html`.

### SMTP Handling

```python
def _get_smtp_config(settings: dict) -> dict:
    """Get SMTP config from settings, with env var fallback."""
    email_cfg = settings.get("schedule", {}).get("summary_email", {})
    return {
        "host": email_cfg.get("smtp_host", "smtp.gmail.com"),
        "port": email_cfg.get("smtp_port", 587),
        "user": email_cfg.get("smtp_user") or os.environ.get("BIZ_SMTP_USER", ""),
        "password": email_cfg.get("smtp_password") or os.environ.get("BIZ_SMTP_PASSWORD", ""),
        "to": email_cfg.get("to", ""),
        "subject_prefix": email_cfg.get("subject_prefix", "[biz-prospector]"),
    }
```

Credentials can be in `settings.yaml` or environment variables (env vars take precedence if settings values are empty). This avoids putting passwords in config files when the user prefers env vars.

Uses `smtplib.SMTP` with STARTTLS. No new dependencies.

### Error Handling

- If SMTP config is incomplete (no `to`, no credentials), skip silently with a console warning
- If SMTP connection fails, log the error and continue — a failed email should never crash the pipeline
- If the HTML report file doesn't exist, send the email without attachment

## Scheduler Module

### New Module: `src/scheduler.py`

Handles crontab read/write/parse operations.

### Key Functions

```python
def install_jobs(settings: dict) -> list[str]:
    """Generate and install crontab entries from settings. Returns list of installed job names."""

def list_jobs() -> list[dict]:
    """Read crontab and return biz-prospector jobs with name, schedule, command."""

def remove_jobs() -> int:
    """Remove all biz-prospector entries from crontab. Returns count removed."""

def _read_crontab() -> str:
    """Read current user crontab."""

def _write_crontab(content: str):
    """Write content to user crontab."""

def _build_cron_entry(job: dict, python_path: str, project_dir: str) -> str:
    """Build a single crontab entry string from a job config dict."""
```

Crontab is managed via `subprocess.run(["crontab", "-l"])` and `subprocess.run(["crontab", "-"], input=...)`. Standard Unix approach.

### Job Validation

Before installing, validate each job:
- `name` is present and unique across all jobs
- `vertical` and `metro` are non-empty strings
- `cron` is a valid 5-field cron expression (validate format, not semantic correctness)
- `count` is a positive integer (default 100)

If any job fails validation, report the error and don't install any jobs.

## Re-Enrich Command

### Pipeline Integration

```python
@cli.command(name="re-enrich")
@click.option("--max-age", default=None, type=int, help="Override max_age_days from config")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def re_enrich(max_age: int | None, notify: bool):
    """Re-enrich and re-score stale leads."""
```

**Flow:**
1. Load settings, get `max_age_days` (from `--max-age` flag or `schedule.re_enrich.max_age_days` or default 30)
2. Scan `data/scored/*.json`, load all leads
3. Filter to leads where `enriched_at` is older than `max_age_days`
4. If no stale leads, print message and exit
5. Run `run_async_enrichment(stale_leads)` (Stage 2)
6. Run `score_leads(stale_leads)` (Stage 3)
7. Save back to their source files in `data/scored/`
8. If `--notify`, send summary email

**Grouping:** Stale leads are grouped by their source file so results are saved back to the correct file. Each file's leads are enriched and scored together, preserving the vertical context for scoring weights.

## Log Directory

Scheduled runs log to `data/logs/<job-name>.log`. The `data/` directory is already gitignored. The log directory is created by `schedule install` if it doesn't exist.

Logs are appended, not rotated. For a weekly run, logs grow slowly. The user can clear them manually or we add a `--max-log-size` option later if needed (YAGNI for now).

## Testing

### `tests/test_scheduler.py`

- `install_jobs()` generates correct crontab entries with absolute paths
- `install_jobs()` replaces existing biz-prospector entries (idempotent)
- `install_jobs()` validates job config (rejects missing name, bad cron)
- `list_jobs()` parses crontab entries correctly
- `remove_jobs()` removes only biz-prospector entries
- `_build_cron_entry()` produces correct format with comment marker
- All crontab operations are mocked via `subprocess.run` patching

### `tests/notifications/test_email_summary.py`

- `send_run_summary()` composes correct HTML with lead data
- `send_run_summary()` attaches HTML report file
- `send_run_summary()` skips gracefully when SMTP config incomplete
- `send_run_summary()` handles SMTP connection failure without crashing
- `_get_smtp_config()` falls back to env vars when settings are empty
- SMTP operations mocked via `unittest.mock.patch("smtplib.SMTP")`

### `tests/test_pipeline.py` (additions)

- `re-enrich` command loads stale leads and re-enriches them
- `re-enrich` command skips fresh leads
- `schedule install` calls `install_jobs`
- `schedule list` calls `list_jobs`
- `schedule remove` calls `remove_jobs`
- `run --notify` triggers `send_run_summary`

## Files Changed

| File | Action | Purpose |
|------|--------|---------|
| `src/scheduler.py` | Create | Crontab management (install/list/remove) |
| `src/notifications/__init__.py` | Create | Package init |
| `src/notifications/email_summary.py` | Create | HTML summary email composition and sending |
| `src/pipeline.py` | Modify | Add schedule subcommands, re-enrich command, --notify flag |
| `config/settings.example.yaml` | Modify | Add schedule section |
| `tests/test_scheduler.py` | Create | Scheduler unit tests |
| `tests/notifications/__init__.py` | Create | Package init |
| `tests/notifications/test_email_summary.py` | Create | Email summary unit tests |
| `tests/test_pipeline.py` | Modify | Integration tests for new commands |
| `FEATURES.md` | Modify | Document scheduled runs and email summary |
| `CHANGELOG.md` | Modify | Add entries |
