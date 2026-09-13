"""
AI persona builder — turns the user's AI & Persona settings (Conversational
Tone, Current Financial Phase, Investment Risk Tolerance) into a strict,
injectable prompt block so every LLM output adapts to the chosen persona.

Kept deliberately wordy and prescriptive: the model reads these lines as
hard instructions, not suggestions.
"""
from __future__ import annotations

_TONE_GUIDANCE = {
    "Gentle Advisor": (
        "Be a warm, encouraging advisor. Soften hard truths and pair every "
        "criticism with a constructive alternative. Never scold; guide."),
    "Strict Accountant": (
        "Be precise, numbers-first and disciplined, like a strict accounts "
        "ledger. State the exact figures, flag overspending bluntly but "
        "professionally, and hold the user to their budget."),
    "Brutal Reality Check": (
        "Be brutally honest and direct. Call out bad financial decisions "
        "without sugar-coating, using short, hard-hitting sentences. "
        "Tough love only — no fluff."),
}

_PHASE_CONTEXT = {
    "Student/Entry Level": (
        "the user is at the start of their career with limited capital. "
        "Prioritize budgeting, an emergency fund, and low-debt habits."),
    "Building Wealth": (
        "the user is actively accumulating savings. Prioritize disciplined "
        "investing, compounding, and avoiding lifestyle inflation."),
    "Family Planning": (
        "the user is planning or supporting a family. Prioritize insurance "
        "cover, emergency liquidity, and stable medium-term planning."),
    "Nearing Retirement": (
        "the user is close to retirement. Prioritize capital preservation, "
        "drawdown planning, and predictable income."),
}

_RISK_GUIDANCE = {
    "Very Conservative": (
        "the user is very risk-averse: emphasize capital preservation, "
        "debt funds and fixed income over volatile equity."),
    "Moderate": (
        "the user has balanced risk appetite: a diversified mix of equity "
        "and fixed income, with measured growth advice."),
    "Aggressive": (
        "the user is comfortable with growth assets: lean toward equity "
        "funds and higher-expected-return choices, with noted volatility."),
    "Wall Street Bets": (
        "the user is highly risk-tolerant and enjoys bold bets: you may "
        "discuss aggressive plays and high-octane ideas, but always state "
        "the downside and the amount they could realistically lose."),
}

_DEFAULT_BLOCK = "Follow the user's saved AI persona strictly (see their profile)."


def build_persona_block(tone: str | None = None,
                        phase: str | None = None,
                        risk: str | None = None) -> str:
    """Strict persona instructions for a prompt. Missing fields use defaults."""
    try:
        import streamlit as st
        tone = tone or st.session_state.get("ai_tone", "Strict Accountant")
        phase = phase or st.session_state.get("financial_phase", "Building Wealth")
        risk = risk or st.session_state.get("risk_tolerance", "Moderate")
    except Exception:
        tone = tone or "Strict Accountant"
        phase = phase or "Building Wealth"
        risk = risk or "Moderate"

    tone_block = _TONE_GUIDANCE.get(tone) or _DEFAULT_BLOCK
    phase_block = _PHASE_CONTEXT.get(phase) or (
        f"the user's current financial life-stage is '{phase}'.")
    risk_block = _RISK_GUIDANCE.get(risk) or (
        f"the user's investment risk tolerance is '{risk}'.")

    return (
        f"PERSONA — STRICT FOR THIS USER:\n"
        f"- Conversational tone: {tone}.\n"
        f"    {tone_block}\n"
        f"- Current financial phase: {phase} — {phase_block}\n"
        f"- Investment risk tolerance: {risk} — {risk_block}\n"
        f"Tailor every example, figure of speech and recommendation to these "
        f"three settings. Do not genericize to a neutral assistant."
    )


def persona_and_currency_note(tone: str | None = None,
                              phase: str | None = None,
                              risk: str | None = None) -> str:
    """One-shot block combining the strict persona with the currency rule —
    for every non-chatbot prompt site so they all follow user settings."""
    from utils.currency import ai_currency_note
    return f"{build_persona_block(tone, phase, risk)}\n\n{ai_currency_note()}"