"""
dashboard/app.py — Stage 3: Human-in-the-loop approval web interface.

Run with: python dashboard/app.py
Then visit: http://localhost:5000
"""

from flask import Flask, render_template_string, redirect, url_for, request, jsonify, abort
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from database import db
from agents.dispatcher import dispatch_approved_change

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# ─────────────────────────────────────────────────────────────────────────────
# HTML Templates (inline for single-file simplicity)
# ─────────────────────────────────────────────────────────────────────────────

BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8fafc; color: #1e293b; }
  .nav  { background: #1e3a5f; color: white; padding: 16px 32px;
          display:flex; align-items:center; gap:16px; }
  .nav h1 { font-size: 1.2rem; font-weight: 600; }
  .container { max-width: 960px; margin: 32px auto; padding: 0 24px; }
  .card { background: white; border-radius: 10px; border: 1px solid #e2e8f0;
          padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
  .badge { display:inline-block; padding:3px 10px; border-radius:99px;
           font-size:.75rem; font-weight:600; }
  .badge-pending    { background:#fef9c3; color:#854d0e; }
  .badge-approved   { background:#dcfce7; color:#166534; }
  .badge-rejected   { background:#fee2e2; color:#991b1b; }
  .badge-sent       { background:#dbeafe; color:#1e40af; }
  .btn { display:inline-block; padding:10px 20px; border-radius:6px;
         font-weight:600; text-decoration:none; cursor:pointer;
         border:none; font-size:.9rem; }
  .btn-green  { background:#16a34a; color:white; }
  .btn-red    { background:#dc2626; color:white; }
  .btn-blue   { background:#2563eb; color:white; }
  .btn-gray   { background:#e2e8f0; color:#374151; }
  .btn:hover  { opacity:.88; }
  textarea    { width:100%; border:1px solid #cbd5e1; border-radius:6px;
                padding:12px; font-family:inherit; font-size:.9rem;
                line-height:1.6; resize:vertical; }
  label       { font-weight:600; font-size:.85rem; color:#475569;
                text-transform:uppercase; letter-spacing:.05em; }
  .meta       { font-size:.8rem; color:#94a3b8; }
  .section-header { font-size:1rem; font-weight:700; color:#334155;
                    margin-bottom:12px; padding-bottom:8px;
                    border-bottom:2px solid #e2e8f0; }
  .alert-box { background:#fff7ed; border:1px solid #fb923c; border-radius:6px;
               padding:12px 16px; margin-bottom:16px; font-size:.9rem; }
</style>
"""


DASHBOARD_TEMPLATE = """
<!DOCTYPE html><html><head>
  <title>ABGC Guideline Monitor</title>
  {style}
</head><body>
<div class="nav">
  <h1>🧬 ABGC Guideline Monitor</h1>
  <span style="margin-left:auto; font-size:.85rem; opacity:.75;">Admin Dashboard</span>
</div>
<div class="container">

  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
    <h2 style="font-size:1.4rem;">Detected Changes</h2>
    <a href="/recipients" class="btn btn-gray">👥 Manage Recipients</a>
  </div>

  {% if not changes %}
    <div class="card" style="text-align:center; color:#94a3b8; padding:48px;">
      <p style="font-size:2rem;">✅</p>
      <p style="margin-top:8px;">No changes detected yet. The monitor will alert you when ABGC updates their guidelines.</p>
    </div>
  {% endif %}

  {% for c in changes %}
  <div class="card">
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
      <div>
        <span class="badge badge-{{ c['status'] }}">{{ c['status'].upper() }}</span>
        <strong style="margin-left:10px;">Change #{{ c['id'] }}</strong>
        <span class="meta" style="margin-left:8px;">Detected {{ c['detected_at'][:16].replace('T',' ') }} UTC</span>
      </div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <a href="/review/{{ c['id'] }}" class="btn btn-blue">🔍 Review</a>
        {% if c['status'] == 'pending' %}
          <a href="/approve/{{ c['id'] }}" class="btn btn-green">✅ Approve</a>
          <a href="/reject/{{ c['id'] }}"  class="btn btn-red">❌ Reject</a>
        {% endif %}
      </div>
    </div>
    <p class="meta" style="margin-top:8px;">Source: <a href="{{ c['url'] }}" target="_blank">{{ c['url'] }}</a></p>
    <div style="margin-top:14px; padding:14px; background:#f8fafc; border-radius:6px; font-size:.9rem; line-height:1.6;">
      {{ c['ai_summary'][:400] }}{% if c['ai_summary']|length > 400 %}…{% endif %}
    </div>
  </div>
  {% endfor %}
</div>
</body></html>
""".replace("{style}", BASE_STYLE)


REVIEW_TEMPLATE = """
<!DOCTYPE html><html><head>
  <title>Review Change #{{ change['id'] }}</title>
  {style}
</head><body>
<div class="nav">
  <a href="/" style="color:white; text-decoration:none;">← Back</a>
  <h1 style="margin-left:12px;">Review Change #{{ change['id'] }}</h1>
  <span class="badge badge-{{ change['status'] }}" style="margin-left:auto;">{{ change['status'].upper() }}</span>
</div>
<div class="container">

  {% if change['status'] == 'pending' %}
  <div class="alert-box">
    ⚠️ <strong>No messages have been sent yet.</strong> Review and edit the drafts below, then click Approve to send.
  </div>
  {% endif %}

  <div class="card">
    <p class="section-header">Source & Detection</p>
    <p><strong>URL:</strong> <a href="{{ change['url'] }}" target="_blank">{{ change['url'] }}</a></p>
    <p class="meta">Detected: {{ change['detected_at'] }} UTC</p>
    {% if change['approved_at'] %}
    <p class="meta">Actioned: {{ change['approved_at'] }} UTC by {{ change['approved_by'] }}</p>
    {% endif %}
  </div>

  <div class="card">
    <p class="section-header">🤖 AI Summary</p>
    <pre style="white-space:pre-wrap; font-size:.9rem; line-height:1.6;">{{ change['ai_summary'] }}</pre>
  </div>

  {% if change['status'] == 'pending' %}
  <form method="POST" action="/review/{{ change['id'] }}/save">
    <div class="card">
      <p class="section-header">📄 Patient Draft <span style="font-weight:400; color:#94a3b8;">(editable)</span></p>
      <textarea name="patient_draft" rows="10">{{ change['patient_draft'] }}</textarea>
    </div>
    <div class="card">
      <p class="section-header">📄 Clinician Draft <span style="font-weight:400; color:#94a3b8;">(editable)</span></p>
      <textarea name="clinician_draft" rows="10">{{ change['clinician_draft'] }}</textarea>
    </div>
    <div style="display:flex; gap:12px; margin-bottom:32px;">
      <button type="submit" name="action" value="approve" class="btn btn-green">✅ Save & Approve — Send to All Recipients</button>
      <button type="submit" name="action" value="reject"  class="btn btn-red">❌ Reject & Dismiss</button>
    </div>
  </form>

  {% else %}
  <div class="card">
    <p class="section-header">📄 Patient Message Sent</p>
    <pre style="white-space:pre-wrap; font-size:.9rem; line-height:1.6;">{{ change['patient_draft'] }}</pre>
  </div>
  <div class="card">
    <p class="section-header">📄 Clinician Message Sent</p>
    <pre style="white-space:pre-wrap; font-size:.9rem; line-height:1.6;">{{ change['clinician_draft'] }}</pre>
  </div>
  {% endif %}

</div>
</body></html>
""".replace("{style}", BASE_STYLE)


RECIPIENTS_TEMPLATE = """
<!DOCTYPE html><html><head>
  <title>Manage Recipients</title>
  {style}
</head><body>
<div class="nav">
  <a href="/" style="color:white; text-decoration:none;">← Back</a>
  <h1 style="margin-left:12px;">Manage Recipients</h1>
</div>
<div class="container">

  <div class="card">
    <p class="section-header">Add New Recipient</p>
    <form method="POST" action="/recipients/add" style="display:grid; gap:14px; max-width:500px;">
      <div>
        <label>Name</label><br>
        <input name="name" required style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;margin-top:4px;">
      </div>
      <div>
        <label>Email</label><br>
        <input name="email" type="email" required style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;margin-top:4px;">
      </div>
      <div>
        <label>Type</label><br>
        <select name="type" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;margin-top:4px;">
          <option value="patient">Patient</option>
          <option value="clinician">Clinician</option>
        </select>
      </div>
      <div>
        <label>Relevant Conditions (comma-separated, optional)</label><br>
        <input name="conditions" placeholder="e.g. BRCA, Lynch syndrome" style="width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px;margin-top:4px;">
      </div>
      <button type="submit" class="btn btn-green" style="width:fit-content;">+ Add Recipient</button>
    </form>
  </div>

  <div class="card">
    <p class="section-header">All Recipients ({{ recipients|length }})</p>
    {% if not recipients %}
      <p style="color:#94a3b8;">No recipients yet. Add some above.</p>
    {% else %}
    <table style="width:100%; border-collapse:collapse; font-size:.9rem;">
      <thead>
        <tr style="border-bottom:2px solid #e2e8f0;">
          <th style="text-align:left; padding:8px;">Name</th>
          <th style="text-align:left; padding:8px;">Email</th>
          <th style="text-align:left; padding:8px;">Type</th>
          <th style="text-align:left; padding:8px;">Conditions</th>
        </tr>
      </thead>
      <tbody>
        {% for r in recipients %}
        <tr style="border-bottom:1px solid #f1f5f9;">
          <td style="padding:8px;">{{ r['name'] }}</td>
          <td style="padding:8px;">{{ r['email'] }}</td>
          <td style="padding:8px;"><span class="badge badge-{{ 'approved' if r['type']=='clinician' else 'pending' }}">{{ r['type'] }}</span></td>
          <td style="padding:8px; color:#64748b;">{{ r['relevant_conditions'] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% endif %}
  </div>
</div>
</body></html>
""".replace("{style}", BASE_STYLE)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    db.init_db()
    changes = db.get_pending_changes()
    # Also fetch all for display
    import sqlite3
    from database.db import get_conn
    with get_conn() as conn:
        all_changes = conn.execute(
            "SELECT * FROM guideline_changes ORDER BY detected_at DESC"
        ).fetchall()
    return render_template_string(DASHBOARD_TEMPLATE, changes=all_changes)


@app.route("/review/<int:change_id>")
def review(change_id):
    change = db.get_change(change_id)
    if not change:
        abort(404)
    return render_template_string(REVIEW_TEMPLATE, change=change)


@app.route("/review/<int:change_id>/save", methods=["POST"])
def save_review(change_id):
    action          = request.form.get("action", "approve")
    patient_draft   = request.form.get("patient_draft", "")
    clinician_draft = request.form.get("clinician_draft", "")

    # Update drafts with any edits
    from database.db import get_conn
    with get_conn() as conn:
        conn.execute(
            "UPDATE guideline_changes SET patient_draft=?, clinician_draft=? WHERE id=?",
            (patient_draft, clinician_draft, change_id)
        )

    if action == "approve":
        db.approve_change(change_id, approved_by="admin")
        # Dispatch messages
        dispatch_approved_change(change_id)
    else:
        db.reject_change(change_id, approved_by="admin")

    return redirect(url_for("index"))


@app.route("/approve/<int:change_id>")
def approve(change_id):
    """Quick-approve from email link (no edit)."""
    change = db.get_change(change_id)
    if not change:
        abort(404)
    if change["status"] == "pending":
        db.approve_change(change_id)
        dispatch_approved_change(change_id)
    return redirect(url_for("index"))


@app.route("/reject/<int:change_id>")
def reject(change_id):
    """Quick-reject from email link."""
    change = db.get_change(change_id)
    if not change:
        abort(404)
    if change["status"] == "pending":
        db.reject_change(change_id)
    return redirect(url_for("index"))


@app.route("/recipients")
def recipients():
    recs = db.get_active_recipients()
    return render_template_string(RECIPIENTS_TEMPLATE, recipients=recs)


@app.route("/recipients/add", methods=["POST"])
def add_recipient():
    name       = request.form.get("name", "").strip()
    email      = request.form.get("email", "").strip()
    rtype      = request.form.get("type", "patient")
    conditions_raw = request.form.get("conditions", "")
    conditions = [c.strip() for c in conditions_raw.split(",") if c.strip()]
    if name and email:
        db.add_recipient(name, email, rtype, conditions)
    return redirect(url_for("recipients"))


# ─── API endpoints (for programmatic access) ──────────────────────────────────

@app.route("/api/changes")
def api_changes():
    from database.db import get_conn
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM guideline_changes ORDER BY detected_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/approve/<int:change_id>", methods=["POST"])
def api_approve(change_id):
    change = db.get_change(change_id)
    if not change:
        return jsonify({"error": "Not found"}), 404
    db.approve_change(change_id)
    result = dispatch_approved_change(change_id)
    return jsonify(result)


if __name__ == "__main__":
    db.init_db()
    print(f"\n🚀 Dashboard running at http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, debug=True)
