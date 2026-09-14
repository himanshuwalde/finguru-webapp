"""
Insurance Advisor — personalised policy recommendations.

Collects a quick 5-field profile (age, dependents, smoking, income, existing
cover) and recommends the best-fitting real Indian term-life and health
insurance policies from a curated market database.  Policies are scored and
ranked by fit, not shown in a static order.  Every policy card shows a Google
search link to buy or compare.  An optional Gemini-powered note explains the
overall strategy.
"""
import streamlit as st
import pandas as pd

from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe
from utils.ai_persona import persona_and_currency_note
from utils.currency import fmt_money

genai_client = get_gemini_client()

# ══════════════════════════════════════════════════════════════════════════════
# MARKET DATABASE — real Indian policies (curated 2025-26)
# ══════════════════════════════════════════════════════════════════════════════
# premium formula: (base_rate × cover_lakhs) × age_factor × smoker_factor
# base_rate, age_factor are per-policy knobs tuned to approximate real quotes.

TERM_POLICIES = [
    {
        "name": "Click 2 Protect Super",
        "provider": "HDFC Life",
        "base_rate": 6.2, "age_factor": 0.085, "min_age": 18, "max_age": 65,
        "tags": ["return_of_premium", "women_discount", "ci_waiver"],
        "feature_head": "Return of premium option",
        "explain": "Gives back all premiums if you survive the term — acts like "
                   "a forced savings plus pure protection. CI waiver on diagnosis.",
    },
    {
        "name": "Smart Secure Plus",
        "provider": "Max Life",
        "base_rate": 5.9, "age_factor": 0.088, "min_age": 18, "max_age": 65,
        "tags": ["ti_cover", "accelerated_death", "accident_cover"],
        "feature_head": "Terminal Illness cover included",
        "explain": "Pays out early on terminal illness diagnosis; accident add-on "
                   "available. Consistently one of the lowest-cost online term plans.",
    },
    {
        "name": "iProtect Smart",
        "provider": "ICICI Prudential",
        "base_rate": 6.4, "age_factor": 0.09, "min_age": 18, "max_age": 65,
        "tags": ["ci_cover", "women_discount", "waiver"],
        "feature_head": "Covers 34 Critical Illnesses",
        "explain": "Lump-sum payout on any of 34 CI conditions; women get lower "
                   "rates. Waiver of premium on CI diagnosis keeps the policy alive.",
    },
    {
        "name": "Life Protect",
        "provider": "Bandhan Life",
        "base_rate": 5.5, "age_factor": 0.082, "min_age": 18, "max_age": 65,
        "tags": ["best_value", "simple"],
        "feature_head": "Lowest-cost pure term cover",
        "explain": "No-frills, lowest-premium pure term plan — ideal if you want "
                   "maximum cover per rupee. No return-of-premium but cheapest option.",
    },
    {
        "name": "eTouch Online Term",
        "provider": "Bajaj Allianz",
        "base_rate": 5.7, "age_factor": 0.086, "min_age": 18, "max_age": 60,
        "tags": ["accident_cover", "waiver", "women_discount"],
        "feature_head": "Accident cover + premium waiver included",
        "explain": "Built-in accidental death benefit and premium waiver on "
                   "disability — no add-on needed. Good for active / commuting users.",
    },
    {
        "name": "eShield Next",
        "provider": "SBI Life",
        "base_rate": 5.8, "age_factor": 0.084, "min_age": 18, "max_age": 65,
        "tags": ["decreasing_cover", "best_value"],
        "feature_head": "Decreasing cover matches reducing liabilities",
        "explain": "Cover automatically shrinks as home loan / liabilities reduce — "
                   "you never overpay. Premium stays level throughout the term.",
    },
    {
        "name": "e-Term Plan",
        "provider": "Kotak Life",
        "base_rate": 5.6, "age_factor": 0.085, "min_age": 18, "max_age": 65,
        "tags": ["women_discount", "simple"],
        "feature_head": "Simple online-only term plan",
        "explain": "Clean digital purchase, no medical for covers under ₹75L if "
                   "young and healthy. Women get preferential rates.",
    },
    {
        "name": "SRI Life",
        "provider": "Tata AIA",
        "base_rate": 6.8, "age_factor": 0.087, "min_age": 18, "max_age": 65,
        "tags": ["ci_cover", "income_benefit", "return_of_premium"],
        "feature_head": "Critical Illness + monthly income benefit",
        "explain": "On CI diagnosis, pays monthly income for 5 years on top of "
                   "lump-sum cover — replaces lost salary during treatment.",
    },
]

HEALTH_POLICIES = [
    {
        "name": "Optima Secure",
        "provider": "HDFC ERGO",
        "base_rate": 850, "min_age": 5, "max_age": 65,
        "tags": ["4x_cover", "no_sublimits", "metro_bonus"],
        "feature_head": "4× cover from Day 1, no room-rent sub-limits",
        "explain": "Instant cover multiplier means your ₹10L policy becomes ₹40L "
                   "from day one — no waiting. No room-rent caps keep costs predictable.",
    },
    {
        "name": "ReAssure 2.0",
        "provider": "Niva Bupa",
        "base_rate": 780, "min_age": 5, "max_age": 65,
        "tags": ["age_lock", "carry_forward", "no_sublimits"],
        "feature_head": "Age-lock + unused cover carries forward",
        "explain": "Premium is locked at your current age for 3 renewals; unused "
                   "sum insured carries forward — rewards healthy years.",
    },
    {
        "name": "Family Health Optima",
        "provider": "Star Health",
        "base_rate": 800, "min_age": 5, "max_age": 65,
        "tags": ["auto_restoration", "newborn_cover", "family"],
        "feature_head": "Auto-restoration of sum insured",
        "explain": "Cover auto-restores if exhausted during a year; newborn baby "
                   "cover from day 1 — ideal for young families planning children.",
    },
    {
        "name": "ProHealth Personal",
        "provider": "ManipalCigna",
        "base_rate": 820, "min_age": 5, "max_age": 65,
        "tags": ["wellness_rewards", "no_sublimits", "chronic_management"],
        "feature_head": "Wellness rewards + chronic management programme",
        "explain": "Earn premium discounts via wellness activities; chronic disease "
                   "management included — best for health-conscious users.",
    },
    {
        "name": "Freedom - Diabetes Care",
        "provider": "Care Health",
        "base_rate": 1100, "min_age": 5, "max_age": 65,
        "tags": ["diabetes_cover", "pre_existing", "no_sublimits"],
        "feature_head": "Full cover for diabetes and pre-existing conditions",
        "explain": "One of the few plans covering diabetes from day one with no "
                   "waiting period — critical if you have existing health conditions.",
    },
    {
        "name": "Activ Fit",
        "provider": "Aditya Birla Health",
        "base_rate": 790, "min_age": 5, "max_age": 65,
        "tags": ["wellness_rewards", "no_sublimits", "healthy_discount"],
        "feature_head": "Health returns + gym membership benefit",
        "explain": "Rewards healthy lifestyle with premium discounts and wellness "
                   "perks; good base plan with modern digital experience.",
    },
    {
        "name": "Complete Health Insurance",
        "provider": "ICICI Lombard",
        "base_rate": 830, "min_age": 5, "max_age": 65,
        "tags": ["4x_cover", "no_sublimits", "reload"],
        "feature_head": "Reload benefit + day-1 preventive health check",
        "explain": "Cover reloads once if exhausted; includes preventive health "
                   "check from year one — useful for families with varied health needs.",
    },
    {
        "name": "Health Companion",
        "provider": "Tata AIG",
        "base_rate": 770, "min_age": 5, "max_age": 65,
        "tags": ["auto_restoration", "simple", "family"],
        "feature_head": "Simple family floater with auto-restoration",
        "explain": "Straightforward family plan, auto-restores on exhaustion; "
                   "competitive pricing for families of 3-4.",
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# PREMIUM CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def _term_premium(policy: dict, cover: float, age: int, smoker: bool) -> int:
    """Estimate monthly premium for a term policy (₹/month)."""
    cover_lakhs = max(cover, 1_00_000) / 1_00_000
    age_factor = 1.0 + policy["age_factor"] * max(0, age - 25)
    smoker_factor = 1.4 if smoker else 1.0
    return max(500, int(policy["base_rate"] * cover_lakhs * age_factor * smoker_factor))


def _health_premium(policy: dict, cover: float, dependents: int,
                    smoker: bool, metro: bool) -> int:
    """Estimate monthly premium for a health policy (₹/month)."""
    cover_factor = max(cover, 5_00_000) / 5_00_000
    family_factor = 1.0 + dependents * 0.25
    smoker_factor = 1.25 if smoker else 1.0
    metro_factor = 1.15 if metro else 1.0
    return max(500, int(policy["base_rate"] * cover_factor * family_factor
                        * smoker_factor * metro_factor))


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDED COVERAGE CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def _recommended_term(annual_income: float, dependents: int,
                      existing_cover: float) -> float:
    """Recommended term life cover in ₹."""
    multiplier = 15 + min(dependents, 5)
    raw = annual_income * multiplier - existing_cover
    return max(5_00_000, round(raw, -5))  # floor ₹5L, round to nearest ₹1L


def _recommended_health(dependents: int, metro: bool,
                        existing_cover: float) -> float:
    """Recommended health cover in ₹."""
    base = 25_00_000 if metro else 15_00_000
    dep_add = dependents * 5_00_000
    raw = base + dep_add - existing_cover
    return max(5_00_000, round(raw, -5))


# ══════════════════════════════════════════════════════════════════════════════
# POLICY MATCHING & RANKING
# ══════════════════════════════════════════════════════════════════════════════

def _term_match_score(policy: dict, age: int, smoker: bool,
                      income: float, cover: float) -> tuple:
    """
    Lower is better.  Returns (disqualified_flag, negative_suitability, -price).
    Policies that don't fit are pushed to the end; the rest rank by value.
    """
    if age < policy["min_age"] or age > policy["max_age"]:
        return (1, 0, 0)
    tags = set(policy["tags"])
    score = 0
    if smoker and "women_discount" in tags:
        score -= 1   # women_discount policies also tend to be pricier for smokers
    if income < 5_00_000 and "best_value" in tags:
        score -= 2   # cheap plans for low-income users
    if income >= 15_00_000 and cover >= 1_00_00_000:
        score -= 1   # high-coverage plans suit high earners
    if smoker and "ci_cover" in tags:
        score -= 1   # CI cover is extra valuable for smokers
    est = _term_premium(policy, cover, age, smoker)
    return (0, score, -est)


def _health_match_score(policy: dict, dependents: int, smoker: bool,
                        cover: float) -> tuple:
    tags = set(policy["tags"])
    score = 0
    if dependents >= 2 and "family" in tags:
        score -= 2
    if smoker and "diabetes_cover" in tags:
        score -= 2
    if cover >= 20_00_000 and "4x_cover" in tags:
        score -= 1
    if dependents == 0 and "simple" in tags:
        score -= 1
    if "no_sublimits" in tags:
        score -= 1
    est = _health_premium(policy, cover, dependents, smoker, True)
    return (0, score, -est)


def _best_policies(policies: list, rank_fn, top_n: int = 3) -> list:
    """Rank policies by custom scoring function, return top N."""
    scored = [(rank_fn(p), p) for p in policies]
    scored.sort(key=lambda x: x[0])
    return [p for _, p in scored[:top_n]]


# ══════════════════════════════════════════════════════════════════════════════
# PAGE RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render_page(supabase):
    st.markdown("""
        <div class="page-header">
            <h2>AI Insurance Advisor</h2>
            <p>Personalised term life & health insurance recommendations from the real Indian market.</p>
        </div>
    """, unsafe_allow_html=True)

    defaults = dict(user_age=30, user_dependents=0, user_smoker="No",
                    user_annual_income=0, user_existing_cover=0,
                    profile_saved=False, ai_advice=None)
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── 1. PROFILE FORM ──────────────────────────────────────────────────────
    if not st.session_state.profile_saved:
        with st.container(border=True):
            st.subheader("👨‍👩‍👧 Tell us about yourself")
            st.caption("5 quick inputs so we can match you to the right policies — takes ~15 seconds.")

            r1c1, r1c2, r1c3 = st.columns(3)
            age = r1c1.number_input("Your Age", min_value=18, max_value=80,
                                    value=st.session_state.user_age)
            dependents = r1c2.number_input("Dependents (spouse + kids + parents)",
                                           min_value=0, max_value=10,
                                           value=st.session_state.user_dependents)
            smoker = r1c3.selectbox("Smoker?",
                                    ["No", "Yes"],
                                    index=0 if st.session_state.user_smoker == "No" else 1)

            r2c1, r2c2 = st.columns(2)
            annual_income = r2c1.number_input(
                "Annual income (₹)", min_value=0, max_value=10_00_00_000,
                value=st.session_state.user_annual_income, step=50000,
                help="Used to size your cover. Set to 0 to auto-estimate from transactions.")
            existing_cover = r2c2.number_input(
                "Existing life/health cover (₹)", min_value=0, max_value=10_00_00_000,
                value=st.session_state.user_existing_cover, step=50000,
                help="Total cover you already have from employer or other policies. "
                     "We'll recommend the gap to avoid overlap.")

            if st.button("Get My Recommendations", type="primary", use_container_width=True):
                st.session_state.user_age = age
                st.session_state.user_dependents = dependents
                st.session_state.user_smoker = smoker
                st.session_state.user_annual_income = annual_income
                st.session_state.user_existing_cover = existing_cover
                st.session_state.profile_saved = True
                st.session_state.ai_advice = None
                st.rerun()
        return

    # ── 2. FETCH TRANSACTION DATA ─────────────────────────────────────────────
    user_id = st.session_state.user_id
    try:
        acc_res = supabase.table("accounts") \
            .select("*").eq("user_id", user_id).order("created_at").execute()
        user_accounts = acc_res.data or []

        primary_acc = next((a for a in user_accounts if a.get("is_primary")), None)
        if not primary_acc and user_accounts:
            primary_acc = user_accounts[0]

        if not primary_acc:
            st.warning("📊 Add a bank account in the Dashboard first!")
            if st.button("Reset Profile"):
                st.session_state.profile_saved = False
                st.rerun()
            return

        acc_id = primary_acc["id"]
        acc_name = primary_acc["account_name"]

        txn_res = supabase.table("transactions") \
            .select("*").eq("user_id", user_id).execute()
        txns = [t for t in (txn_res.data or []) if t.get("account_id") == acc_id]
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return

    if not txns:
        st.warning(f"No transactions in **{acc_name}** yet — log some income and expenses first.")
        if st.button("Reset Profile"):
            st.session_state.profile_saved = False
            st.rerun()
        return

    # ── 3. INFERENCE ───────────────────────────────────────────────────────────
    df = pd.DataFrame(txns)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    total_income = df[df["type"] == "Income"]["amount"].sum()

    # Use manual entry if provided; otherwise infer from transactions
    annual_income = (st.session_state.user_annual_income
                     if st.session_state.user_annual_income > 0
                     else total_income * 12)

    # ── 4. RECOMMENDED COVERS ──────────────────────────────────────────────────
    rec_term = _recommended_term(annual_income, st.session_state.user_dependents,
                                 st.session_state.user_existing_cover)
    rec_health = _recommended_health(st.session_state.user_dependents,
                                    metro=True,
                                    existing_cover=st.session_state.user_existing_cover)

    # ── 5. RANK POLICIES ───────────────────────────────────────────────────────
    def _tf(p): return _term_match_score(p, st.session_state.user_age,
                                         st.session_state.user_smoker == "Yes",
                                         annual_income, rec_term)
    def _hf(p): return _health_match_score(p, st.session_state.user_dependents,
                                           st.session_state.user_smoker == "Yes",
                                           rec_health)
    best_term  = _best_policies(TERM_POLICIES,  _tf, top_n=3)
    best_health = _best_policies(HEALTH_POLICIES, _hf, top_n=3)

    # ── 6. HEADER ──────────────────────────────────────────────────────────────
    hc1, hc2 = st.columns([4, 1])
    with hc1:
        age_str = st.session_state.user_age
        dep_str = st.session_state.user_dependents
        smoke_str = "smoker" if st.session_state.user_smoker == "Yes" else "non-smoker"
        st.subheader(f"Recommendations for a {age_str}-year-old {smoke_str} "
                     f"with {dep_str} dependent{'s' if dep_str != 1 else ''}")
        st.caption(f"Primary account analysed: **{acc_name}**")
    with hc2:
        if st.button("✏️ Edit Profile"):
            st.session_state.profile_saved = False
            st.session_state.ai_advice = None
            st.rerun()

    st.write("---")

    # ── 7. SUMMARY METRICS ────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Term Life Cover", fmt_money(rec_term))
    m2.metric("Health Cover", fmt_money(rec_health))
    m3.metric("Est. Term Premium", fmt_money(_term_premium(best_term[0], rec_term,
              st.session_state.user_age, st.session_state.user_smoker == "Yes"))
              + "/mo" if best_term else "—")
    m4.metric("Est. Health Premium", fmt_money(_health_premium(best_health[0], rec_health,
              st.session_state.user_dependents, st.session_state.user_smoker == "Yes",
              True)) + "/mo" if best_health else "—")

    st.write("---")

    # ── 8. TWO-COLUMN POLICY CARDS ────────────────────────────────────────────
    left, right = st.columns(2)

    # ---------- TERM LIFE ----------
    with left:
        with st.container(border=True):
            st.markdown("### ☂️ Term Life Insurance")
            st.caption("Replace your income and clear debts if you are not around.")

            st.markdown(f"""
            <div style="background:var(--secondary-background-color);padding:16px 20px;
                        border-radius:8px;text-align:center;margin:10px 0;
                        border:1px solid rgba(150,150,150,.15)">
              <p style="color:var(--text-color);opacity:.6;margin:0;font-size:.8rem;
                        font-weight:700;text-transform:uppercase;letter-spacing:1px">
                Recommended Cover</p>
              <h2 style="color:var(--primary-color);margin:4px 0 0;font-size:1.6rem;
                         font-weight:700">{fmt_money(rec_term)}</h2>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("How we calculated this"):
                multiplier = 15 + min(st.session_state.user_dependents, 5)
                st.caption(f"• **Income multiple:** {multiplier}× annual income "
                           f"({fmt_money(annual_income)}/yr × {multiplier})")
                if st.session_state.user_existing_cover > 0:
                    st.caption(f"• **Existing cover deducted:** "
                               f"−{fmt_money(st.session_state.user_existing_cover)}")

            st.markdown("#### ✨ Best Matches for You")

            for i, p in enumerate(best_term):
                premium = _term_premium(p, rec_term, st.session_state.user_age,
                                        st.session_state.user_smoker == "Yes")
                with st.container(border=True):
                    c1, c2 = st.columns([2.5, 1.5])
                    with c1:
                        badge = f"#{i+1} Best Fit" if i == 0 else ""
                        if badge:
                            st.markdown(
                                f"<span style='background:var(--primary-color);color:#fff;"
                                f"padding:2px 8px;border-radius:10px;font-size:.7rem;"
                                f"font-weight:700'>{badge}</span>",
                                unsafe_allow_html=True)
                        st.markdown(
                            f"<div style='font-weight:800;font-size:1.05rem;"
                            f"color:var(--text-color)'>{p['name']}</div>",
                            unsafe_allow_html=True)
                        st.caption(f"by {p['provider']}")
                        st.markdown(
                            f"<div style='background:var(--secondary-background-color);"
                            f"border:1px solid rgba(150,150,150,.2);"
                            f"color:var(--primary-color);padding:3px 10px;border-radius:12px;"
                            f"font-size:.73rem;font-weight:700;margin-top:4px;"
                            f"display:inline-block'>✓ {p['feature_head']}</div>",
                            unsafe_allow_html=True)
                    with c2:
                        st.markdown(
                            f"<div style='text-align:right;font-weight:800;font-size:1.15rem;"
                            f"color:var(--text-color);margin-bottom:6px'>"
                            f"{fmt_money(premium)}"
                            f"<span style='font-size:.78rem;font-weight:500;"
                            f"opacity:.6'>/mo</span></div>",
                            unsafe_allow_html=True)
                        search_q = f"{p['name'].replace(' ', '+')}+" \
                                   f"{p['provider'].replace(' ', '+')}+term+insurance"
                        st.link_button("View Plan →",
                                       url=f"https://www.google.com/search?q={search_q}",
                                       use_container_width=True)
                        with st.expander("Why this policy for you?", expanded=(i == 0)):
                            st.caption(p["explain"])

    # ---------- HEALTH ----------
    with right:
        with st.container(border=True):
            st.markdown("### 🏥 Health Insurance")
            st.caption("Cover hospital bills for you and your family without draining savings.")

            st.markdown(f"""
            <div style="background:var(--secondary-background-color);padding:16px 20px;
                        border-radius:8px;text-align:center;margin:10px 0;
                        border:1px solid rgba(150,150,150,.15)">
              <p style="color:var(--text-color);opacity:.6;margin:0;font-size:.8rem;
                        font-weight:700;text-transform:uppercase;letter-spacing:1px">
                Recommended Cover</p>
              <h2 style="color:var(--primary-color);margin:4px 0 0;font-size:1.6rem;
                         font-weight:700">{fmt_money(rec_health)}</h2>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("How we calculated this"):
                base = 25_00_000
                dep_add = st.session_state.user_dependents * 5_00_000
                st.caption(f"• **Base cover:** {fmt_money(base)} (metro city rate)")
                if st.session_state.user_dependents > 0:
                    st.caption(f"• **Dependent add-on:** +{fmt_money(dep_add)} "
                               f"({st.session_state.user_dependents} dependents)")
                if st.session_state.user_existing_cover > 0:
                    st.caption(f"• **Existing cover deducted:** "
                               f"−{fmt_money(st.session_state.user_existing_cover)}")

            st.markdown("#### ✨ Best Matches for You")

            for i, p in enumerate(best_health):
                premium = _health_premium(p, rec_health,
                                          st.session_state.user_dependents,
                                          st.session_state.user_smoker == "Yes",
                                          metro=True)
                with st.container(border=True):
                    c1, c2 = st.columns([2.5, 1.5])
                    with c1:
                        badge = f"#{i+1} Best Fit" if i == 0 else ""
                        if badge:
                            st.markdown(
                                f"<span style='background:var(--primary-color);color:#fff;"
                                f"padding:2px 8px;border-radius:10px;font-size:.7rem;"
                                f"font-weight:700'>{badge}</span>",
                                unsafe_allow_html=True)
                        st.markdown(
                            f"<div style='font-weight:800;font-size:1.05rem;"
                            f"color:var(--text-color)'>{p['name']}</div>",
                            unsafe_allow_html=True)
                        st.caption(f"by {p['provider']}")
                        st.markdown(
                            f"<div style='background:var(--secondary-background-color);"
                            f"border:1px solid rgba(150,150,150,.2);"
                            f"color:var(--primary-color);padding:3px 10px;border-radius:12px;"
                            f"font-size:.73rem;font-weight:700;margin-top:4px;"
                            f"display:inline-block'>✓ {p['feature_head']}</div>",
                            unsafe_allow_html=True)
                    with c2:
                        st.markdown(
                            f"<div style='text-align:right;font-weight:800;font-size:1.15rem;"
                            f"color:var(--text-color);margin-bottom:6px'>"
                            f"{fmt_money(premium)}"
                            f"<span style='font-size:.78rem;font-weight:500;"
                            f"opacity:.6'>/mo</span></div>",
                            unsafe_allow_html=True)
                        search_q = f"{p['name'].replace(' ', '+')}+" \
                                   f"{p['provider'].replace(' ', '+')}+health+insurance"
                        st.link_button("View Plan →",
                                       url=f"https://www.google.com/search?q={search_q}",
                                       use_container_width=True)
                        with st.expander("Why this policy for you?", expanded=(i == 0)):
                            st.caption(p["explain"])

    # ── 9. AI ADVISOR NOTE ────────────────────────────────────────────────────
    st.write("---")
    st.subheader("🤖 AI Advisor's Note")

    if st.session_state.ai_advice:
        st.info(st.session_state.ai_advice)
        if st.button("🔄 Clear & Regenerate"):
            st.session_state.ai_advice = None
            st.rerun()
    else:
        if st.button("Generate Personalised Advice", type="primary"):
            with st.spinner("Analysing your profile with Gemini..."):
                smoke = "smoker" if st.session_state.user_smoker == "Yes" else "non-smoker"
                term_names = ", ".join(p["name"] + " (" + p["provider"] + ")"
                                       for p in best_term)
                health_names = ", ".join(p["name"] + " (" + p["provider"] + ")"
                                         for p in best_health)
                prompt = f"""{persona_and_currency_note()}

You are a sympathetic, expert Indian financial advisor. Write a short 2-paragraph
personalised insurance note for this specific person.

Profile:
  Age: {st.session_state.user_age}, Dependents: {st.session_state.user_dependents},
  Smoking: {smoke}, Annual Income: {fmt_money(annual_income)},
  Existing Cover: {fmt_money(st.session_state.user_existing_cover)}

Recommended Term Life Cover: {fmt_money(rec_term)}
Top 3 term policies ranked for this person: {term_names}

Recommended Health Cover: {fmt_money(rec_health)}
Top 3 health policies ranked for this person: {health_names}

Paragraph 1: Explain WHY this specific person needs this specific cover amount,
referencing their income, dependents, and what would happen if they are not around.
Paragraph 2: Briefly explain why the top-ranked policies suit them best (value,
features relevant to their age/lifestyle). Be specific to THIS person — do not
write generic advice. Keep it professional and empathetic. Use plain text, no
markdown formatting like **bold**."""

                try:
                    target = get_best_model(genai_client, prefer_flash=True)
                    model = genai_client.GenerativeModel(target)
                    result = generate_content_safe(model, prompt)
                    if result:
                        st.session_state.ai_advice = result
                    else:
                        raise Exception("Empty model response")
                except Exception as e:
                    print(f"[insurance] Gemini error: {e}")
                    smoke = st.session_state.user_smoker.lower()
                    st.session_state.ai_advice = (
                        f"As a {st.session_state.user_age}-year-old {smoke} "
                        f"with {st.session_state.user_dependents} dependents and "
                        f"an annual income of {fmt_money(annual_income)}, securing a "
                        f"term life cover of {fmt_money(rec_term)} is essential. This "
                        f"ensures your family maintains their lifestyle and any "
                        f"outstanding debts are cleared if you are not around.\n\n"
                        f"A health cover of {fmt_money(rec_health)} protects your "
                        f"savings from being drained by sudden hospitalisation. "
                        f"The policies listed above were ranked specifically for "
                        f"your age, smoking status, and family size to give you "
                        f"the best value per rupee of premium.")
                st.rerun()
