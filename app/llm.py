"""
LLM Insight Generation via Anthropic API.

Constructs a structured clinical prompt from analysis metrics and returns
a 3–5 sentence patient-friendly glucose pattern report.
Falls back to a realistic placeholder when ANTHROPIC_API_KEY is not set.
"""

import os

from app.schemas import AnalysisResponse, InsightResponse

_SYSTEM_PROMPT = (
    "You are a clinical CGM data interpreter helping patients understand their glucose patterns. "
    "Write in clear, empathetic language a patient can act on. Avoid jargon. "
    "Always ground observations in the specific numbers provided."
)

_MODEL = "claude-haiku-4-5-20251001"


def _build_prompt(analysis: AnalysisResponse) -> str:
    """
    Construct the LLM prompt from analysis metrics.

    Includes all meal stability classifications, CV%, peak excursions,
    TIR/TAR/TBR, and GMI so the model can ground its report in real numbers.
    """
    meal_lines = []
    for m in analysis.meal_analyses:
        meal_lines.append(
            f"  - {m.meal_name} ({m.meal_time}): peak {m.peak_glucose} mg/dL, "
            f"{m.time_to_peak_minutes:.0f} min to peak, excursion +{m.excursion_mg_dl:.0f} mg/dL, "
            f"CV {m.cv_percent:.1f}%, classification: {m.stability.replace('_', ' ')}"
        )

    hypo_note = (
        f"  - {len(analysis.hypo_events)} hypoglycemia episode(s) detected."
        if analysis.hypo_events
        else "  - No hypoglycemia episodes detected."
    )

    return f"""Here is a patient's 14-day CGM summary. Write a 3–5 sentence report following this structure exactly:
Sentence 1: Overall assessment starting with "Your glucose control over the past 14 days shows..."
Sentences 2–3: Identify the best-performing meal and worst-performing meal by name, with specific numbers.
Sentences 4–5: One concrete, actionable lifestyle suggestion for each problematic meal.

DATA:
Overall metrics:
  - Time In Range (70–180 mg/dL): {analysis.tir_percent:.1f}%
  - Time Above Range (>180 mg/dL): {analysis.tar_percent:.1f}%
  - Time Below Range (<70 mg/dL): {analysis.tbr_percent:.1f}%
  - Glucose Management Indicator (estimated A1c): {analysis.gmi:.1f}%
  - Mean glucose: {analysis.mean_glucose:.0f} mg/dL
  - Overall CV: {analysis.cv_percent:.1f}%

Meal-by-meal breakdown:
{chr(10).join(meal_lines)}

Hypoglycemia:
{hypo_note}
"""


def _placeholder_report(analysis: AnalysisResponse) -> str:
    """
    Generate a realistic demo report when no API key is configured.

    Uses actual metric values so the placeholder is meaningful.
    """
    worst = max(analysis.meal_analyses, key=lambda m: m.cv_percent)
    best = min(analysis.meal_analyses, key=lambda m: m.cv_percent)

    tir_note = (
        "good control" if analysis.tir_percent >= 70
        else "room for improvement" if analysis.tir_percent >= 50
        else "significant variability"
    )

    return (
        f"Your glucose control over the past 14 days shows {tir_note}, with "
        f"{analysis.tir_percent:.0f}% of readings in the healthy 70–180 mg/dL range "
        f"and a Glucose Management Indicator of {analysis.gmi:.1f}%. "
        f"Your best-controlled meal is {best.meal_name}, where glucose peaks at around "
        f"{best.peak_glucose:.0f} mg/dL with a low variability score of {best.cv_percent:.0f}%. "
        f"Your {worst.meal_name} shows the most variability (CV {worst.cv_percent:.0f}%), "
        f"with spikes averaging {worst.peak_glucose:.0f} mg/dL — "
        f"about {worst.excursion_mg_dl:.0f} mg/dL above your pre-meal level. "
        f"For {worst.meal_name}, try reducing portion size of fast-digesting carbohydrates "
        f"(bread, rice, sugary drinks) and adding 10–15 minutes of light walking afterward. "
        f"Tracking how different foods affect your {worst.meal_name.lower()} spike over the "
        f"next week will help you identify the biggest triggers."
    )


def generate_insight(analysis: AnalysisResponse) -> InsightResponse:
    """
    Generate a patient-facing glucose pattern report.

    Calls the Anthropic API if ANTHROPIC_API_KEY is present; otherwise
    returns a placeholder report built from the analysis data so the
    UI remains functional in demo mode.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        return InsightResponse(report=_placeholder_report(analysis))

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(analysis)

        message = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        report = message.content[0].text.strip()
        return InsightResponse(report=report)

    except Exception:
        # Any API failure falls back to placeholder — UI never breaks
        return InsightResponse(report=_placeholder_report(analysis))
