"""
ABGC Monitoring Agent — Configuration
Edit these values before running the system.
"""

import os

# ─── ABGC URLs to monitor ────────────────────────────────────────────────────
MONITOR_URLS = [
    "https://www.abgc.net/practice-resources/practice-guidelines",
    "https://www.abgc.net/news",
]

# ─── Anthropic (Claude) ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "your-anthropic-api-key")
CLAUDE_MODEL = "claude-sonnet-4-6"

# ─── Mailgun ──────────────────────────────────────────────────────────────────
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "your-mailgun-api-key")
MAILGUN_DOMAIN  = os.getenv("MAILGUN_DOMAIN",  "your-mailgun-domain")  # e.g. mg.yourclinic.com or sandbox....mailgun.org
FROM_EMAIL = "your-system@yourdomain.com"
FROM_NAME = "Genetic Counseling Update System"

# ─── Your alert email (where YOU get notified of changes) ────────────────────
ADMIN_EMAIL = "you@yourdomain.com"
ADMIN_NAME = "Admin"

# ─── Approval dashboard ──────────────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-to-a-random-secret")
APPROVAL_BASE_URL = "http://localhost:5000"  # Update to your public URL in production

# ─── Database ────────────────────────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "abgc_agent.db")

# ─── Scheduler ───────────────────────────────────────────────────────────────
# How often to check ABGC (in hours)
CHECK_INTERVAL_HOURS = 24

# ─── Monitoring ──────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_HEADERS = {
    "User-Agent": (
        "ABGC-Guideline-Monitor/1.0 "
        "(Genetic Counseling Practice Update System; "
        "contact: your@email.com)"
    )
}
