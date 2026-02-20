"""
main.py — Entry points for the ABGC Monitoring Agent.

Usage:
  python main.py monitor     # Run one monitoring check right now
  python main.py dashboard   # Start the approval web dashboard
  python main.py schedule    # Run the scheduler (checks every N hours)
  python main.py seed        # Add sample recipients for testing
"""

import sys
import time
from database import db


def run_monitor_once():
    from agents.monitor import run_monitor
    run_monitor()


def run_dashboard():
    from dashboard.app import app
    import config
    db.init_db()
    print(f"\n🚀 Dashboard: http://localhost:{config.DASHBOARD_PORT}\n")
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, debug=False)


def run_scheduler():
    import config
    interval_seconds = config.CHECK_INTERVAL_HOURS * 3600
    print(f"⏰ Scheduler started — checking every {config.CHECK_INTERVAL_HOURS}h")
    while True:
        run_monitor_once()
        print(f"💤 Sleeping {config.CHECK_INTERVAL_HOURS}h until next check...\n")
        time.sleep(interval_seconds)


def seed_sample_recipients():
    db.init_db()
    samples = [
        ("Jane Smith",    "jane.smith@example.com",    "patient",    ["BRCA1", "BRCA2"]),
        ("Robert Jones",  "rob.jones@example.com",     "patient",    ["Lynch syndrome"]),
        ("Dr. Sarah Lee", "dr.lee@clinic.example.com", "clinician",  []),
        ("Dr. Mark Tan",  "dr.tan@clinic.example.com", "clinician",  ["Lynch syndrome", "BRCA"]),
    ]
    for name, email, rtype, conditions in samples:
        db.add_recipient(name, email, rtype, conditions)
        print(f"  + Added: {name} ({rtype})")
    print("\n✅ Sample recipients added.")


COMMANDS = {
    "monitor":   run_monitor_once,
    "dashboard": run_dashboard,
    "schedule":  run_scheduler,
    "seed":      seed_sample_recipients,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(__doc__)
