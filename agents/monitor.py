"""
agents/monitor.py — Stage 1 & 2: Scrape ABGC pages, detect changes, alert admin.

Run this on a schedule (cron / GitHub Actions / cloud scheduler).
"""

import hashlib
import difflib
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from database import db
from agents.summarizer import generate_summaries_and_drafts
from agents.notifier import send_admin_alert


def fetch_page_text(url: str) -> str:
    """Fetch a URL and return clean visible text (no HTML tags)."""
    resp = httpx.get(url, headers=config.REQUEST_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove navigation, footer, scripts, styles
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Get clean text
    text = soup.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def compute_diff(old_text: str, new_text: str) -> str:
    """Return a unified diff string between old and new text."""
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile="previous", tofile="current",
        lineterm=""
    ))
    return "".join(diff) if diff else ""


def check_url(url: str) -> bool:
    """
    Check a single URL for changes.
    Returns True if a change was detected and processed.
    """
    print(f"\n🔍 Checking: {url}")

    try:
        new_text = fetch_page_text(url)
    except Exception as e:
        print(f"  ❌ Failed to fetch page: {e}")
        return False

    new_hash = compute_hash(new_text)
    latest = db.get_latest_snapshot(url)

    if latest and latest["content_hash"] == new_hash:
        print(f"  ✅ No change detected.")
        return False

    print(f"  ⚠️  Change detected!")

    # Save new snapshot
    new_snap_id = db.save_snapshot(url, new_hash, new_text)
    old_snap_id = latest["id"] if latest else None
    old_text = latest["raw_text"] if latest else ""

    # Compute diff
    diff_text = compute_diff(old_text, new_text)

    # Stage 2: AI summarization + draft messages
    print("  🤖 Generating AI summary and draft messages...")
    ai_summary, patient_draft, clinician_draft = generate_summaries_and_drafts(
        url=url,
        diff_text=diff_text,
        new_text=new_text,
        is_first_snapshot=(old_text == "")
    )

    # Save change record
    change_id = db.save_change(
        url=url,
        old_snapshot_id=old_snap_id,
        new_snapshot_id=new_snap_id,
        diff_text=diff_text,
        ai_summary=ai_summary,
        patient_draft=patient_draft,
        clinician_draft=clinician_draft,
    )

    # Alert admin
    print("  📧 Sending admin alert...")
    send_admin_alert(change_id, url, ai_summary, patient_draft, clinician_draft)

    print(f"  ✅ Change #{change_id} saved and alert sent.")
    return True


def run_monitor():
    """Check all configured URLs."""
    print(f"\n{'='*60}")
    print(f"ABGC Monitor — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    db.init_db()
    changes_found = 0

    for url in config.MONITOR_URLS:
        if check_url(url):
            changes_found += 1

    print(f"\n{'='*60}")
    print(f"Done. {changes_found} change(s) detected across {len(config.MONITOR_URLS)} URL(s).")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_monitor()
