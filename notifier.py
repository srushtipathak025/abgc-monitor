"""
agents/notifier.py — Email delivery via Mailgun.

Used for:
  - Admin alerts (Stage 2)
  - Approved patient / clinician outreach (Stage 4)
"""

import httpx
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config


def _send_email(to_email: str, to_name: str, subject: str, body_html: str) -> bool:
    """Send a single email via Mailgun. Returns True on success."""
    try:
        response = httpx.post(
            f"https://api.mailgun.net/v3/{config.MAILGUN_DOMAIN}/messages",
            auth=("api", config.MAILGUN_API_KEY),
            data={
                "from":    f"{config.FROM_NAME} <{config.FROM_EMAIL}>",
                "to":      f"{to_name} <{to_email}>",
                "subject": subject,
                "html":    body_html,
            },
            timeout=30,
        )
        if response.status_code == 200:
            return True
        else:
            print(f"    ❌ Mailgun error ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"    ❌ Mailgun error sending to {to_email}: {e}")
        return False


# ─── Admin alert (Stage 2) ────────────────────────────────────────────────────

def send_admin_alert(
    change_id: int,
    url: str,
    ai_summary: str,
    patient_draft: str,
    clinician_draft: str,
) -> bool:
    """
    Email the admin with the detected change, AI summary,
    draft messages, and approve/reject action links.
    """
    approve_url = f"{config.APPROVAL_BASE_URL}/approve/{change_id}"
    reject_url  = f"{config.APPROVAL_BASE_URL}/reject/{change_id}"
    review_url  = f"{config.APPROVAL_BASE_URL}/review/{change_id}"

    subject = f"⚠️ ABGC Guideline Change Detected — Action Required (Change #{change_id})"

    body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 700px; margin: auto; padding: 24px;">

      <h2 style="color: #b91c1c;">🔔 ABGC Guideline Change Detected</h2>
      <p><strong>Change ID:</strong> #{change_id}<br>
         <strong>Source URL:</strong> <a href="{url}">{url}</a></p>

      <hr style="border-color: #e5e7eb; margin: 20px 0;">

      <h3 style="color: #1e40af;">📋 AI Summary</h3>
      <div style="background:#f0f9ff; border-left:4px solid #3b82f6; padding:16px; border-radius:4px;">
        <pre style="white-space:pre-wrap; font-family:Arial; font-size:14px;">{ai_summary}</pre>
      </div>

      <hr style="border-color: #e5e7eb; margin: 20px 0;">

      <h3 style="color: #059669;">📄 Draft — Patient Message</h3>
      <div style="background:#f0fdf4; border-left:4px solid #10b981; padding:16px; border-radius:4px;">
        <pre style="white-space:pre-wrap; font-family:Arial; font-size:14px;">{patient_draft}</pre>
      </div>

      <h3 style="color: #7c3aed;">📄 Draft — Clinician Message</h3>
      <div style="background:#faf5ff; border-left:4px solid #8b5cf6; padding:16px; border-radius:4px;">
        <pre style="white-space:pre-wrap; font-family:Arial; font-size:14px;">{clinician_draft}</pre>
      </div>

      <hr style="border-color: #e5e7eb; margin: 20px 0;">

      <h3>🛡️ Your Action Required</h3>
      <p>Please review the drafts above. When ready, use the buttons below or visit the
         <a href="{review_url}">full review dashboard</a> to edit messages before approving.</p>

      <table><tr>
        <td style="padding-right:12px;">
          <a href="{approve_url}" style="background:#16a34a; color:white; padding:12px 24px;
             text-decoration:none; border-radius:6px; font-weight:bold;">
            ✅ Approve & Send
          </a>
        </td>
        <td>
          <a href="{reject_url}" style="background:#dc2626; color:white; padding:12px 24px;
             text-decoration:none; border-radius:6px; font-weight:bold;">
            ❌ Reject / Dismiss
          </a>
        </td>
      </tr></table>

      <p style="color:#6b7280; font-size:12px; margin-top:32px;">
        This is an automated alert from the ABGC Guideline Monitoring System.<br>
        No messages have been sent to patients or clinicians yet.
      </p>
    </body></html>
    """

    return _send_email(config.ADMIN_EMAIL, config.ADMIN_NAME, subject, body)


# ─── Outreach email (Stage 4) ─────────────────────────────────────────────────

def send_outreach_email(
    to_email: str,
    to_name: str,
    recipient_type: str,  # "patient" | "clinician"
    message_body: str,
    change_id: int,
) -> bool:
    """Send a personalized update to a patient or clinician."""

    if recipient_type == "patient":
        subject = "An Update from Your Genetic Counseling Team"
        header_color = "#059669"
        header_label = "Patient Update"
    else:
        subject = "ABGC Practice Guideline Update — Action May Be Required"
        header_color = "#1e40af"
        header_label = "Clinical Practice Update"

    body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 24px;">

      <div style="background:{header_color}; color:white; padding:16px 24px; border-radius:6px 6px 0 0;">
        <h2 style="margin:0;">{header_label}</h2>
      </div>

      <div style="border:1px solid #e5e7eb; border-top:none; padding:24px; border-radius:0 0 6px 6px;">
        <pre style="white-space:pre-wrap; font-family:Arial; font-size:15px; line-height:1.6;">
{message_body}
        </pre>
      </div>

      <p style="color:#9ca3af; font-size:11px; margin-top:16px; text-align:center;">
        Reference: Change #{change_id} | {config.FROM_NAME}<br>
        If you have questions, please contact our office.
      </p>
    </body></html>
    """

    return _send_email(to_email, to_name, subject, body)
