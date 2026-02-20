"""
agents/summarizer.py — Stage 2: Use Claude to summarize changes and draft outreach messages.
"""

import anthropic
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def _call_claude(system: str, user: str, max_tokens: int = 1024) -> str:
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return response.content[0].text.strip()


def generate_summaries_and_drafts(
    url: str,
    diff_text: str,
    new_text: str,
    is_first_snapshot: bool = False,
) -> tuple[str, str, str]:
    """
    Returns: (ai_summary, patient_draft, clinician_draft)
    """

    context = (
        "This is the first time we are capturing this page — "
        "summarize the key guideline content present."
        if is_first_snapshot
        else f"The following diff shows what changed on the ABGC page:\n\n{diff_text[:8000]}"
    )

    # ── AI Summary (for admin review) ────────────────────────────────────────
    ai_summary = _call_claude(
        system=(
            "You are a clinical genetics expert. Analyze changes to American Board of "
            "Genetic Counseling (ABGC) guidelines and produce a clear, accurate summary "
            "for a genetic counseling practice administrator. Be concise but complete. "
            "Note: what changed, why it likely changed, and what clinical impact it may have."
        ),
        user=(
            f"URL: {url}\n\n{context}\n\n"
            f"Current full page content (for context):\n{new_text[:6000]}\n\n"
            "Please provide:\n"
            "1. What changed (specific, factual)\n"
            "2. Clinical significance of the change\n"
            "3. Any action items for the practice\n"
            "4. Confidence level in your interpretation (High/Medium/Low)"
        ),
        max_tokens=1200
    )

    # ── Patient draft ─────────────────────────────────────────────────────────
    patient_draft = _call_claude(
        system=(
            "You are a compassionate genetic counselor writing to patients. "
            "Use plain language (8th grade reading level). Avoid jargon. "
            "Be warm, reassuring, and actionable. Do not cause unnecessary alarm. "
            "Never give specific medical advice — encourage patients to discuss with their provider."
        ),
        user=(
            f"An update was made to ABGC guidelines. Here is a summary of what changed:\n\n"
            f"{ai_summary}\n\n"
            "Write a personalized email to a patient explaining this update. "
            "Include: what this means for them in plain terms, that their care team will "
            "reach out if any action is needed, and an invitation to contact the office with questions. "
            "Use [PATIENT_NAME] as a placeholder. Keep it under 200 words."
        ),
        max_tokens=600
    )

    # ── Clinician draft ───────────────────────────────────────────────────────
    clinician_draft = _call_claude(
        system=(
            "You are a senior genetic counselor writing to clinical colleagues. "
            "Use precise clinical language. Be direct and informative. "
            "Focus on practice implications and any required changes to workflow or counseling."
        ),
        user=(
            f"An update was made to ABGC guidelines. Here is a summary of what changed:\n\n"
            f"{ai_summary}\n\n"
            "Write a professional update email for clinicians and genetic counselors. "
            "Include: the specific guideline change, clinical and workflow implications, "
            "any recommended actions, and a note that full details are available at the ABGC website. "
            "Use [CLINICIAN_NAME] as a placeholder. Keep it under 250 words."
        ),
        max_tokens=700
    )

    return ai_summary, patient_draft, clinician_draft


def personalize_message(template: str, recipient_name: str, recipient_type: str, conditions: list[str]) -> str:
    """
    Personalize a draft message for a specific recipient.
    Replaces placeholders and optionally tailors content to their conditions.
    """
    # Simple placeholder substitution first
    message = template.replace("[PATIENT_NAME]", recipient_name)
    message = message.replace("[CLINICIAN_NAME]", recipient_name)

    # If the recipient has specific conditions, add a tailored note
    if conditions:
        conditions_str = ", ".join(conditions)
        addition = _call_claude(
            system="You are a genetic counselor. Write 1-2 sentences only.",
            user=(
                f"Add a brief, personalized sentence to this {recipient_type} message "
                f"noting that this update may be particularly relevant to someone with "
                f"the following conditions/testing history: {conditions_str}. "
                f"Keep it general and non-alarming. Return only the sentence(s), nothing else."
            ),
            max_tokens=150
        )
        message = message.rstrip() + f"\n\n{addition}"

    return message
