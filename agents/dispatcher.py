"""
agents/dispatcher.py — Stage 4: Send personalized messages to all recipients after approval.

Called automatically when admin approves a change via the dashboard.
"""

import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import db
from agents.summarizer import personalize_message
from agents.notifier import send_outreach_email


def dispatch_approved_change(change_id: int) -> dict:
    """
    For an approved change:
    1. Fetch all active recipients
    2. Personalize the appropriate draft for each recipient
    3. Send the email
    4. Log every message to the database
    Returns a summary dict.
    """
    change = db.get_change(change_id)
    if not change:
        return {"error": f"Change #{change_id} not found."}
    if change["status"] != "approved":
        return {"error": f"Change #{change_id} is not in 'approved' state (status: {change['status']})."}

    recipients = db.get_active_recipients()
    if not recipients:
        return {"error": "No active recipients found in the database."}

    results = {"sent": 0, "failed": 0, "total": len(recipients)}
    patient_draft    = change["patient_draft"]
    clinician_draft  = change["clinician_draft"]

    print(f"\n📬 Dispatching Change #{change_id} to {len(recipients)} recipient(s)...\n")

    for recipient in recipients:
        rtype      = recipient["type"]          # "patient" or "clinician"
        name       = recipient["name"]
        email      = recipient["email"]
        conditions = json.loads(recipient["relevant_conditions"] or "[]")

        # Choose the right template
        template = patient_draft if rtype == "patient" else clinician_draft

        # Personalize using Claude
        try:
            personalized_body = personalize_message(
                template=template,
                recipient_name=name,
                recipient_type=rtype,
                conditions=conditions,
            )
        except Exception as e:
            print(f"  ⚠️  Personalization failed for {name} ({email}): {e}")
            personalized_body = template.replace("[PATIENT_NAME]", name).replace("[CLINICIAN_NAME]", name)

        # Save to DB before sending
        msg_id = db.save_outbound_message(
            change_id=change_id,
            recipient_id=recipient["id"],
            subject=(
                "An Update from Your Genetic Counseling Team"
                if rtype == "patient"
                else "ABGC Practice Guideline Update"
            ),
            body=personalized_body,
        )

        # Send
        success = send_outreach_email(
            to_email=email,
            to_name=name,
            recipient_type=rtype,
            message_body=personalized_body,
            change_id=change_id,
        )

        if success:
            db.mark_message_sent(msg_id)
            results["sent"] += 1
            print(f"  ✅ Sent to {name} ({rtype}) — {email}")
        else:
            db.mark_message_failed(msg_id, "SendGrid delivery failure")
            results["failed"] += 1
            print(f"  ❌ Failed: {name} ({rtype}) — {email}")

    # Mark the change itself as sent
    db.mark_change_sent(change_id)

    print(f"\n📊 Dispatch complete: {results['sent']} sent, {results['failed']} failed.\n")
    return results
