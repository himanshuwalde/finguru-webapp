"""
AI CA Chatbot page — "CA Guru", the grounded financial assistant.
Answers are generated ONLY from the user's computed engine outputs (tax,
net worth, portfolio, FIRE, spending), never from open-ended memory. If Gemini
is unavailable, a deterministic offline answer is shown from the same data.
Every exchange is logged to `ai_conversations`.
"""
from __future__ import annotations

import json

import streamlit as st

import ai.ca_chatbot as ca_chatbot
from ai.intent_router import TOOL_DESCRIPTIONS
from utils.ui_components import render_gradient_header, render_alert_banner


def render_page(supabase):
    render_gradient_header(
        "🧑‍💼", "AI CA Advisor (Grounded)",
        "Ask about your real numbers — tax, net worth, investments, FIRE. "
        "The assistant answers only from your computed data, never makes it up.",
        gradient_colors=["#0EA5E9", "#8B5CF6"],
    )
    st.write("---")

    intro = st.columns([2, 1])
    with intro[0]:
        st.markdown(
            "**How it works:** every figure is calculated by FinGuru's deterministic "
            "engines. Gemini explains those figures and suggests actions — it never "
            "computes tax or ROI itself. If no AI key is set, you still get a "
            "numbers-first answer.")
    with intro[1]:
        with st.expander("What can it answer?"):
            for name, desc in TOOL_DESCRIPTIONS.items():
                st.markdown(f"- **{name}** — {desc}")

    if "ca_messages" not in st.session_state:
        st.session_state.ca_messages = []
    if "ca_grounding" not in st.session_state:
        st.session_state.ca_grounding = {}

    # ------------------------------------------------------------ chat body
    for msg in st.session_state.ca_messages:
        with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

    if prompt := st.chat_input("e.g. How can I save tax this year?"):
        st.chat_message("user", avatar="👤").markdown(prompt)
        st.session_state.ca_messages.append({"role": "user", "content": prompt})

        user_id = st.session_state.user_id
        with st.chat_message("assistant", avatar="🧑‍💼"):
            placeholder = st.empty()
            with st.spinner("Reading your computed numbers…"):
                reply, intent, grounding = ca_chatbot.respond(
                    supabase, user_id, prompt, st.session_state.ca_messages[:-1])

            placeholder.markdown(reply)
            st.session_state.ca_messages.append({"role": "assistant", "content": reply})
            st.session_state.ca_grounding[intent] = grounding

            # intent badge + audit trail
            st.caption(f"intent → `{intent}`")
        if not ca_chatbot.log_conversation(supabase, user_id, prompt,
                                           intent, grounding, reply):
            st.caption("(chat history not persisted — `ai_conversations` table missing)")

    st.write("---")
    if st.session_state.ca_messages:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑 Clear conversation", use_container_width=True):
                st.session_state.ca_messages = []
                st.rerun()
        with c2:
            with st.expander("See the grounding data this session used"):
                st.json(json.dumps({k: v for k, v in
                                    st.session_state.ca_grounding.items()},
                                   default=float)[:6000])