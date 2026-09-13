"""
Per-user settings loader — pulls the AI persona + preferred currency from the
`profiles` table into session_state exactly once per logged-in session, so every
page (and every LLM prompt) can read `st.session_state.preferred_currency`,
`ai_tone`, `financial_phase` and `risk_tolerance` without a per-render DB call.

`profile.py` invalidates the load (resets `_user_settings_loaded`) whenever the
user saves a settings change, so the new values apply on the very next rerun.
Missing columns are tolerated (falls back to the defaults), matching the app's
other defensive reads against an un-migrated Supabase.
"""
from __future__ import annotations

import streamlit as st


def ensure_user_settings(supabase, user_id: str) -> None:
    """Load persona + currency into session_state once per login. No-op if done."""
    if st.session_state.get("_user_settings_loaded"):
        return
    row = None
    try:
        res = (supabase.table("profiles")
               .select("ai_tone, financial_phase, risk_tolerance, preferred_currency")
               .eq("id", user_id).execute())
        row = res.data[0] if (res and res.data) else None
    except Exception:
        row = None  # un-migrated profiles table → keep defaults

    st.session_state.preferred_currency = (row or {}).get("preferred_currency") or "INR"
    st.session_state.ai_tone = (row or {}).get("ai_tone") or "Strict Accountant"
    st.session_state.financial_phase = (row or {}).get("financial_phase") or "Building Wealth"
    st.session_state.risk_tolerance = (row or {}).get("risk_tolerance") or "Moderate"
    st.session_state._user_settings_loaded = True


def invalidate_user_settings() -> None:
    """Force a fresh load on the next rerun (called after settings saves)."""
    st.session_state._user_settings_loaded = False