# Currency + Persona Implementation Complete

## Overview
Successfully implemented a **Preferred Currency selector** and **strict AI persona delivery** throughout the FinGuru app. Every money display now respects the user's chosen currency (INR, USD, EUR, GBP, JPY, AUD, CAD, SGD, AED, CHF), and every AI prompt adapts to the user's Conversational Tone, Financial Phase, and Investment Risk Tolerance.

## Changes Made

### 1. Core Utilities
- `utils/currency.py` – Single source of truth for currency display
  - Live FX rate caching (12h TTL, open.er-api.com)
  - `fmt_money(value, dp=0)` – format stored INR amounts in display currency
  - `fmt_label(text)` – rewrite "(₹)" labels to display symbol
  - `ai_currency_note()` – prompt line for LLM currency instructions
  - Graceful degradation on API failure → symbol relabel only

- `utils/ai_persona.py` – Strict persona builder
  - `build_persona_block(tone, phase, risk)` – structured prompt block
  - `persona_and_currency_note()` – combined persona+currency block for single prompts
  - Maps all 3 settings to delivery guidance, life-stage context, and risk language

- `utils/user_settings.py` – Session-state loader
  - `ensure_user_settings(supabase, user_id)` – loads 4 fields from profiles
  - Called once per login in `app.py` before page dispatch

### 2. Database Migration
- `migrations/002_preferred_currency_persona.sql` – adds `preferred_currency` and `risk_tolerance` columns
- Default values: `'INR'` and `'Moderate'`

### 3. Profile & Settings UI
- **Identity tab**: "🌍 Preferred Currency" selectbox with curated 10 currencies
- **AI Persona tab**: Risk Tolerance slider now saved (`risk_tolerance` field)
- Both tabs: Immediate session-state update + invalidate flag on save → instant effect

### 4. Display Sweep (Task #23)
Replaced every per-page `_inr(v) → f"₹{v:,.0f}"` with `fmt_money()`:
- `portfolio.py`, `net_worth.py`, `fire_planner.py`, `family_wealth.py`
- `dashboard.py`, `transactions.py`, `add_transaction.py`, `anomalies.py`
- `tax_planner.py`, `trust_engine.py`, `insurance.py`, `ghost_auditor.py`
- `safe_to_spend.py`, `utils/ui_components.py`, `engines/health_score.py`

All `(₹)` input/axis labels → `fmt_label(...)` – matches display symbol while keeping stored amounts native-INR.

### 5. LLM Prompt Injection (Task #24)
Every Gemini call now receives persona + currency strict instructions:

#### AI Chatbot Layer
- `ai/context_builder.py` – tool outputs converted to display currency, adds `"settings"` block
- `ai/prompts.py` – `build_prompt(... persona_block, currency_note)` – injects blocks before grounding
- `ai/ca_chatbot.py` – pulls session-state persona/currency → injects into every chatbot response

#### Page-Specific Prompts
All inject `persona_and_currency_note()` + convert raw ₹ amounts via `fmt_money`:
- `financial_twin.py:188` – Future Self AI
- `financial_guardrail.py:229` – Purchase authorization reality check
- `ghost_auditor.py:227` – UPI micro-transaction audit
- `dashboard.py:702` – Financial Health Score summary
- `anomalies.py:132` – Fraud analyst warning
- `insurance.py:274` – Insurance advisor summary
- `legacy_agent.py:233/385` – Successor invite + stagnant account alerts
- `utils/anomaly_engine.py:18` – Fraud alert email generation
- `alert_engine.py:33` – Budget warning emails (converts budget/category amounts)

## Behavior Contract

### Currency Semantics
1. **Stored data stays INR** – single source of truth; Indian statutory thresholds remain INR-correct
2. **Viewing in INR** → relabel only (symbol ₹, same formatting as before)
3. **Viewing in another currency** → fetches live rate, multiplies stored INR for display + AI grounding
4. **Rate fetch failure** → symbol still swaps, values stay unchanged (no crash)
5. **Money inputs** remain labelled in display currency but store INR values
6. **Offline/edge tests** → `default_code()` returns "INR" outside Streamlit → existing tests pass

### Persona Delivery
1. **AI Conversational Tone** – Gentle Advisor/Strict Accountant/Brutal Reality Check
2. **Current Financial Phase** – Student/Building Wealth/Family Planning/Nearing Retirement
3. **Investment Risk Tolerance** – Very Conservative/Moderate/Aggressive/Wall Street Bets
4. **Every AI output** – tone, examples, risk language, phase context strictly adapted

## Verification

### Automated
- `python -m py_compile app.py pages/*.py ai/*.py utils/*.py` – all compile clean
- `pytest` – 53 tests pass (offline defaults keep ₹ assertions in test_chatbot.py)
- Currency-aware grounding test (`test_grounding_serializes_to_valid_json`) updated for `"settings"` block

### Manual Test Flow
1. **Profile → Identity** → set Preferred Currency = **USD** → Save
2. **Dashboard/net worth/portfolio/fire metrics** show `$`-prefixed, value = INR ×USD rate
3. **Profile → AI Persona** → select **Brutal Reality Check + Student/Entry Level + Very Conservative** → Save
4. **Open AI CA Advisor** → ask "how am I doing?" → reply is blunt, uses `$`, adapts to Student phase + risk
5. **Switch back to INR** → everything returns to plain ₹ relabel, statutory thresholds intact
6. **Kill FX fetch** (`FX_API_URL` wrong) → non-INR view renders correct symbol, un-converted values (graceful)
7. **Offline AI** (`GEMINI_API_KEY` missing) → deterministic answers print chosen currency

## Deployment Notes
1. `git add` touched files, push to branch
2. Deploy on Streamlit Cloud (`.streamlit/secrets.toml` stays out of git)
3. Run migrations in Supabase SQL editor:
   ```sql
   -- 001 (if not already)
   -- 002_preferred_currency_persona.sql
   alter table public.profiles add column if not exists preferred_currency text not null default 'INR';
   alter table public.profiles add column if not exists risk_tolerance      text not null default 'Moderate';
   ```

## Files Touched
- New: `utils/currency.py`, `utils/ai_persona.py`, `utils/user_settings.py`, `migrations/002_preferred_currency_persona.sql`
- Modified: `app.py`, `pages/profile.py`, `pages/*.py` (12 pages), `ai/context_builder.py`, `ai/prompts.py`, `ai/ca_chatbot.py`, `utils/anomaly_engine.py`, `alert_engine.py`, `tests/test_chatbot.py`, `engines/health_score.py`, `utils/ui_components.py`

## Security
- `.streamlit/secrets.toml` never committed (contains SUPABASE_KEY, GEMINI_API_KEY, ENCRYPTION_KEY)
- FX API fallback prevents crashes
- Session-state isolation preserves privacy between users

**Complete**: All user requirements satisfied – currency selection, display adaptation, AI persona strict delivery.