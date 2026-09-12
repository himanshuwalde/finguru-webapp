"""
Prompts — the grounding contract for the CA chatbot.
The system prompt instructs Gemini to answer ONLY from the provided figures,
to cite the numbers it uses, and to admit when data is missing. The user's
real computed data is injected via the `grounding` block.
"""
from __future__ import annotations

from typing import List, Dict

SYSTEM_PROMPT = """You are **CA Guru**, FinGuru's chartered-accountant assistant. \
You explain *computed* numbers — you never compute them yourself.

STRICT GROUNDING RULES (non-negotiable):
1. Answer ONLY from the "GROUNDING DATA" JSON below. Every specific figure you \
quote must appear in it.
2. If the grounding says "status": "no_data" for something, say the data isn't \
recorded yet and tell the user where to enter it (Tax Planner / Portfolio / \
Net Worth / FIRE Planner). Never invent numbers.
3. If you cannot answer from the grounding, say so plainly — do not speculate, \
do not give generic tax advice as if it were computed for this user.
4. Keep responses concise (under ~180 words), structured with short bullet \
points or lines. End with ONE actionable next step when relevant.
5. If an exact figure you need is missing, work only from what IS present and \
say which assumption you made (e.g. "assumed 4% safe withdrawal rate").
"""


def build_prompt(user_message: str,
                 grounding_json: str,
                 history: List[Dict]) -> str:
    """Assemble the full prompt: system rules + grounding + conversation."""
    turns = []
    for m in history:
        turns.append(f"{m['role'].upper()}: {m['content']}")
    history_str = "\n".join(turns[-6:]) if turns else "No prior turns."

    return f"""{SYSTEM_PROMPT}

========== GROUNDING DATA (user's real computed figures) ==========
{grounding_json}
====================================================================

CONVERSATION SO FAR:
{history_str}

USER QUESTION: {user_message}

Answer now, following the grounding rules."""


# ------------------------------------------------------------------ fallback

def deterministic_answer(intent: str, results: Dict[str, Dict]) -> str:
    """
    Offline fallback when the AI service is unavailable: build a concise,
    truthful answer straight from the engine outputs (no Gemini, no invention).
    Called by ca_chatbot when generation fails — so the chat never goes blank.
    """
    lines: List[str] = []
    net = results.get("net_worth", {})
    if net.get("status") == "ok":
        lines.append(f"Net worth: {_inr(net['net_worth'])} "
                     f"(assets {_inr(net['total_assets'])} "
                     f"− liabilities {_inr(net['total_liabilities'])}).")
    port = results.get("portfolio_summary", {})
    if port.get("status") == "ok":
        lines.append(f"Investments: {_inr(port['total_current'])} "
                     f"(+{port['return_pct']:.1f}%, XIRR {port['xirr_pct']:.1f}%).")
    spend = results.get("spending_summary", {})
    if spend.get("status") == "ok":
        lines.append(f"Average monthly spend: {_inr(spend['avg_monthly_expense'])}.")
    tax = results.get("tax_calculator", {})
    if tax.get("status") == "ok":
        lines.append(f"Recommended tax regime: {tax['recommended_regime'].upper()} "
                     f"(saving ₹{tax['potential_saving']:,.0f}).")
    opp = results.get("tax_saving_opportunities", {})
    if opp.get("status") == "ok" and opp.get("opportunities"):
        lines.append("Tax-saving gaps: " + "; ".join(opp["opportunities"]))
    fire = results.get("fire_status", {})
    if fire.get("status") == "ok":
        lines.append(f"FIRE probability: {fire['probability_pct']:.0f}% "
                     f"(median corpus {_inr(fire['median_corpus'])} vs required "
                     f"{_inr(fire['required_corpus'])}).")

    if not lines:
        return ("I couldn't find enough recorded data to answer yet. Enter your "
                "income in Tax Planner, add investments, and save a FIRE plan "
                "first — then ask me again. (AI summary unavailable offline.)")
    return ("⚠️ AI explanation is temporarily offline — here's what the numbers "
            "say directly:\n• " + "\n• ".join(lines))


def _inr(v) -> str:
    return f"₹{float(v):,.0f}"