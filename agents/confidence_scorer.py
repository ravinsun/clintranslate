"""
Agent 4: Confidence Scorer + Router
Routes each translation based on cosine similarity score:
  ≥ 0.80  → AUTO_APPROVED
  0.55–0.79 → REVIEW_REQUIRED
  < 0.55  → REJECTED (with explanation)

Also factors in validation_status from Agent 3.
"""

from typing import TypedDict, Dict, Any, List


# Thresholds
HIGH_CONFIDENCE = 0.80
LOW_CONFIDENCE = 0.55


def compute_routing(cosine_score: float, validation_status: str, sas_loc: int) -> tuple[str, str]:
    """
    Returns (routing_decision, reasoning).
    """
    # Override: if syntax failed after retries → always REVIEW_REQUIRED
    if validation_status == "failed":
        return "REVIEW_REQUIRED", "Syntax validation failed after 2 correction attempts — human review mandatory"

    if cosine_score >= HIGH_CONFIDENCE:
        decision = "AUTO_APPROVED"
        reason = f"High cosine similarity ({cosine_score}) — strong knowledge base match, minor review recommended"
    elif cosine_score >= LOW_CONFIDENCE:
        decision = "REVIEW_REQUIRED"
        reason = f"Medium cosine similarity ({cosine_score}) — translation likely correct but requires reviewer confirmation"
    else:
        decision = "REJECTED"
        reason = f"Low cosine similarity ({cosine_score}) — insufficient knowledge base coverage; manual translation recommended"

    # Additional flag: large programs (>200 LOC) always get review flag
    if sas_loc > 200 and decision == "AUTO_APPROVED":
        decision = "REVIEW_REQUIRED"
        reason += f" | Program size ({sas_loc} LOC) exceeds auto-approval threshold"

    return decision, reason


class ScorerState(TypedDict):
    translations: Dict[str, Dict[str, Any]]
    routing_summary: Dict[str, str]   # filename -> decision
    scorer_notes: List[str]


def run_confidence_scorer(state: ScorerState) -> ScorerState:
    """
    LangGraph node: Scores each translation and assigns routing decision.
    """
    routing_summary = {}
    notes = []

    for filename, data in state["translations"].items():
        if data["status"] == "error":
            data["routing_decision"] = "REJECTED"
            data["routing_reason"] = "Translation agent error — file could not be processed"
            routing_summary[filename] = "REJECTED"
            notes.append(f"❌ {filename} → REJECTED (translation error)")
            continue

        score = data.get("cosine_score", 0.0)
        val_status = data.get("validation_status", "unknown")
        sas_loc = data.get("sas_loc", 0)

        decision, reason = compute_routing(score, val_status, sas_loc)

        data["routing_decision"] = decision
        data["routing_reason"] = reason
        routing_summary[filename] = decision

        icon = {"AUTO_APPROVED": "🟢", "REVIEW_REQUIRED": "🟡", "REJECTED": "🔴"}.get(decision, "⚪")
        notes.append(f"{icon} {filename} → {decision} | {reason}")

    state["routing_summary"] = routing_summary
    state["scorer_notes"] = notes
    return state
