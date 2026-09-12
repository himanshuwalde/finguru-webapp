# Himanshu Walde
import streamlit.components.v1 as components
import pages.profile as profile
import pages.add_transaction as add_transaction
import pages.dashboard as dashboard
import pages.insurance as insurance
import pages.transactions as transactions
import pages.anomalies as anomalies
import pages.financial_twin as financial_twin
import pages.safe_to_spend as safe_to_spend
import pages.family_wealth as family_wealth
import pages.ghost_auditor as ghost_auditor
# import pages.web3_vault as web3_vault
import pages.account_aggregator as account_aggregator
import pages.trust_engine as trust_engine
import pages.legacy_agent as legacy_agent
import pages.financial_guardrail as financial_guardrail
import pages.tax_planner as tax_planner
import pages.portfolio as portfolio
import pages.net_worth as net_worth
import pages.fire_planner as fire_planner
import pages.ai_advisor as ai_advisor
import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="AI Financial Guru", page_icon="💰", layout="wide")

# ==========================================
# ✨ Supabase Email Recovery Catcher
# ==========================================
components.html("""
<script>
    if (window.parent.location.hash.includes("type=recovery") && !window.parent.location.search.includes("recovery=true")) {
        window.parent.location.replace(window.parent.location.origin + window.parent.location.pathname + "?recovery=true" + window.parent.location.hash);
    }
</script>
""", height=0)

# ==========================================
# ✨ SIDEBAR THEME FIX
# Strategy: Inject a <style> tag directly into the PARENT document
# from a components.html iframe. This bypasses the iframe sandbox
# for stylesheets and correctly applies to Streamlit's sidebar DOM.
# We detect the theme by reading the actual computed background color
# of the app container — not the OS preference — so it always matches
# whatever theme Streamlit is currently using.
# ==========================================
components.html("""
<script>
(function() {
    function applyTheme() {
        try {
            const doc = window.parent.document;

            // -- 1. Detect current Streamlit theme --
            const appBg = doc.querySelector('[data-testid="stAppViewContainer"]');
            if (!appBg) return;
            const bgColor = window.parent.getComputedStyle(appBg).backgroundColor;
            const rgb = bgColor.match(/\d+/g);
            if (!rgb) return;
            const brightness = (parseInt(rgb[0]) * 299 + parseInt(rgb[1]) * 587 + parseInt(rgb[2]) * 114) / 1000;
            const isDark = brightness < 128;

            // -- 2. Define exact colors for each theme --
            // These match Streamlit's own default theme values exactly
            const sidebarBg   = isDark ? '#0e1117' : '#f0f2f6';
            const textColor   = isDark ? '#fafafa' : '#31333f';
            const subText     = isDark ? 'rgba(250,250,250,0.6)' : 'rgba(49,51,63,0.6)';
            const borderColor = isDark ? 'rgba(250,250,250,0.1)' : 'rgba(49,51,63,0.1)';
            const hoverBg     = isDark ? 'rgba(250,250,250,0.05)' : 'rgba(49,51,63,0.05)';

            // -- 3. Remove any previously injected style to avoid duplicates --
            const existing = doc.getElementById('finguru-sidebar-fix');
            if (existing) existing.remove();

            // -- 4. Build and inject a <style> tag into the PARENT document <head> --
            const style = doc.createElement('style');
            style.id = 'finguru-sidebar-fix';
            style.textContent = `
                /* === FINGURU SIDEBAR FIX === */

                /* Target all structural wrappers of the sidebar */
                [data-testid="stSidebar"],
                [data-testid="stSidebar"] > div,
                [data-testid="stSidebar"] > div > div,
                [data-testid="stSidebar"] > div > div > div,
                section[data-testid="stSidebar"],
                section[data-testid="stSidebar"] > div {
                    background-color: ${sidebarBg} !important;
                    backdrop-filter: none !important;
                    -webkit-backdrop-filter: none !important;
                }

                /* Sidebar text colors */
                [data-testid="stSidebar"] p,
                [data-testid="stSidebar"] span,
                [data-testid="stSidebar"] label,
                [data-testid="stSidebar"] div {
                    color: ${textColor};
                }

                /* Radio button labels */
                [data-testid="stSidebar"] [role="radiogroup"] label {
                    color: ${textColor} !important;
                    border-radius: 8px;
                    padding: 8px 12px;
                }
                [data-testid="stSidebar"] [role="radiogroup"] label:hover {
                    background-color: ${hoverBg} !important;
                }

                /* HR dividers */
                [data-testid="stSidebar"] hr {
                    border-color: ${borderColor} !important;
                }

                /* Log Out button */
                [data-testid="stSidebar"] button {
                    color: ${textColor} !important;
                    border-color: ${borderColor} !important;
                }

                /* Mobile-only: full height coverage */
                @media (max-width: 767px) {
                    [data-testid="stSidebar"],
                    [data-testid="stSidebar"] > div,
                    section[data-testid="stSidebar"] {
                        min-height: 100vh !important;
                        min-height: 100dvh !important;
                    }
                }
            `;
            doc.head.appendChild(style);

        } catch(e) {
            console.warn('FinGuru sidebar fix error:', e);
        }
    }

    // Run immediately, then keep polling to handle:
    // - Streamlit rerenders
    // - Mobile sidebar slide-open animation
    // - Theme toggle by user
    applyTheme();
    setInterval(applyTheme, 500);
})();
</script>
""", height=0)

# ==========================================
# ✨ MAIN CSS
# ==========================================
st.markdown("""
<style>
    .gradient-text {
        background: -webkit-linear-gradient(45deg, #2563EB, #9333EA);
        background: linear-gradient(45deg, #2563EB, #9333EA);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 4.5rem;
        font-weight: 900;
        text-align: center;
        padding-bottom: 0.5rem;
        margin-bottom: 0;
        display: inline-block;
    }
    .sub-text {
        font-size: 1.3rem;
        color: var(--text-color);
        opacity: 0.7;
        text-align: center;
        margin-top: 0;
        margin-bottom: 3rem;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    div[data-testid="stAlert"] {
        border-radius: 16px;
        padding: 1.5rem;
        border: none;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }
    div[data-testid="stAlert"]:hover {
        transform: translateY(-8px);
        box-shadow: 0 12px 25px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border-radius: 16px;
        padding: 1.5rem 1rem;
        text-align: center;
        border: 1px solid rgba(150, 150, 150, 0.1);
        transition: transform 0.2s ease;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stMetric"]:hover {
        transform: scale(1.02);
    }
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {
        justify-content: center;
    }

    /* Desktop sidebar base */
    @media (min-width: 768px) {
        [data-testid="stSidebar"] {
            background-color: var(--secondary-background-color) !important;
            border-right: 1px solid rgba(150, 150, 150, 0.2) !important;
            min-width: 280px !important;
        }
    }

    /* Radio button menu styling */
    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 10px 15px;
        border-radius: 8px;
        margin-bottom: 5px;
        transition: all 0.2s ease;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: var(--background-color);
    }
    [data-testid="stSidebar"] hr {
        margin-top: 1rem;
        margin-bottom: 1rem;
        border-top-color: rgba(150, 150, 150, 0.2);
    }

    /* Feature Card */
    .feature-card {
        background-color: var(--background-color);
        border: 1px solid rgba(150, 150, 150, 0.2);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        height: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .feature-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.08);
        border-color: var(--primary-color);
    }
    .feature-title {
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--text-color);
        margin-bottom: 0.5rem;
    }
    .feature-desc {
        color: var(--text-color);
        opacity: 0.8;
        font-size: 0.9rem;
        line-height: 1.5;
    }

    /* ======== Landing / marketing page ======== */
    .landing-hero { text-align: center; padding: 3.2rem 1rem 1.2rem; }
    .landing-eyebrow {
        display: inline-block; text-transform: uppercase; letter-spacing: 2px;
        font-size: 0.74rem; font-weight: 700; color: var(--text-color);
        background: linear-gradient(135deg, rgba(37,99,235,.14), rgba(147,51,234,.14));
        border: 1px solid rgba(120,120,170,.28);
        padding: 6px 16px; border-radius: 999px; margin-bottom: 1.3rem;
    }
    .landing-hero h1 {
        font-size: 4.2rem; font-weight: 900; line-height: 1.1; margin-bottom: 1.2rem;
        letter-spacing: -0.8px;
    }
    .landing-hero h1 .gradient {
        background: linear-gradient(45deg, #2563EB, #9333EA);
        -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    }
    .landing-sub {
        font-size: 1.05rem; color: var(--text-color); opacity: .75;
        max-width: 820px; margin: 0 auto 1.8rem auto; line-height: 1.7;
        text-align: center;
    }
    .hero-pills { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; margin-bottom: 1.5rem; }
    .hero-pill {
        font-size: .78rem; font-weight: 600; letter-spacing: .2px; padding: 5px 13px;
        border-radius: 999px; color: var(--text-color);
        background: var(--secondary-background-color); border: 1px solid rgba(150,150,150,.25);
    }

    .section-head { text-align: center; margin: 0.5rem 0 2.2rem; }
    .section-eyebrow {
        display: inline-block; text-transform: uppercase; letter-spacing: 2.5px;
        font-size: .72rem; font-weight: 800; color: var(--primary-color); margin-bottom: .6rem;
    }
    .section-head h2 { font-size: 1.9rem; font-weight: 800; color: var(--text-color); margin: .2rem 0 .5rem; letter-spacing: -0.3px; }
    .section-head p { max-width: 640px; margin: 0 auto; color: var(--text-color); opacity: .7; line-height: 1.6; font-size: 1rem; }

    .module-card {
        background: var(--secondary-background-color);
        border: 1px solid rgba(150,150,150,.18); border-radius: 18px;
        padding: 1.4rem 1.4rem 1.2rem; height: 100%;
        transition: all .25s ease;
    }
    .module-card:hover {
        transform: translateY(-4px); border-color: var(--primary-color);
        box-shadow: 0 14px 28px rgba(0,0,0,.08);
    }
    .module-icon {
        width: 46px; height: 46px; border-radius: 13px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.45rem; margin-bottom: .95rem;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,.18);
    }
    .module-title { font-weight: 700; font-size: 1.05rem; color: var(--text-color); margin-bottom: .35rem; }
    .module-desc { color: var(--text-color); opacity: .75; font-size: .9rem; line-height: 1.55; }
    .module-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: .85rem; }
    .module-tag {
        font-size: .7rem; font-weight: 600; letter-spacing: .2px; padding: 3px 10px;
        border-radius: 999px; border: 1px solid rgba(150,150,150,.25); color: var(--text-color); opacity: .85;
    }

    .feature-card-sm {
        background: var(--background-color);
        border: 1px solid rgba(150,150,150,.18); border-radius: 14px;
        padding: 1.05rem 1.15rem; height: 100%; transition: all .25s ease;
    }
    .feature-card-sm:hover { transform: translateY(-3px); border-color: var(--primary-color); }
    .feature-title-sm { font-weight: 700; font-size: .93rem; color: var(--text-color); margin-bottom: .3rem; }
    .feature-desc-sm { color: var(--text-color); opacity: .75; font-size: .82rem; line-height: 1.5; }

    .step { text-align: center; }
    .step-num {
        width: 58px; height: 58px; margin: 0 auto .85rem; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-weight: 900; font-size: 1.45rem; color: #FFFFFF;
        background: linear-gradient(135deg, #2563EB, #9333EA);
        box-shadow: 0 10px 20px rgba(37,99,235,.28);
    }
    .step h4 { color: var(--text-color); margin: .2rem 0 .45rem; font-size: 1.05rem; }
    .step p { color: var(--text-color); opacity: .7; font-size: .9rem; line-height: 1.55; padding: 0 1rem; }

    .stack-strip {
        text-align: center; color: var(--text-color); opacity: .6;
        font-size: .78rem; letter-spacing: .5px; line-height: 2;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_connection()

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_email' not in st.session_state: st.session_state.user_email = ""
if 'user_id' not in st.session_state: st.session_state.user_id = ""
if 'show_auth_page' not in st.session_state: st.session_state.show_auth_page = False 
if 'editing_account' not in st.session_state: st.session_state.editing_account = None 
if 'force_page' not in st.session_state: st.session_state.force_page = None
if 'ai_consent' not in st.session_state: st.session_state.ai_consent = False
if 'auth_mode' not in st.session_state: st.session_state.auth_mode = 'login' 

if "recovery" in st.query_params:
    st.session_state.show_auth_page = True
    st.session_state.auth_mode = 'update_pwd'

def go_to_auth():
    st.session_state.show_auth_page = True

def go_back_home():
    st.session_state.show_auth_page = False

if st.session_state.logged_in:
    # ==========================================
    # ✨ THE JPMC AUTO-SYNC BACKGROUND LISTENER 
    # ==========================================
    account_aggregator.run_background_sync(supabase, st.session_state.user_id)

    # ==========================================
    # ✨ UPGRADED SIDEBAR UI
    # ==========================================
    
    st.sidebar.markdown("""
        <h2 style='color: var(--text-color); font-weight: 800; margin-top: 0; padding-top: 0; margin-bottom: 1rem;'>FinGuru <span style='color: var(--primary-color);'>AI</span></h2>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
        <div style="background: linear-gradient(135deg, #2563EB 0%, #9333EA 100%); padding: 15px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="font-size: 0.8rem; opacity: 0.85; margin-bottom: 3px; font-weight: 500;">Logged in as</div>
            <div style="font-weight: 700; font-size: 0.95rem; word-break: break-all; line-height: 1.2;">{st.session_state.user_email}</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown(f"""
        <div style="background-color: var(--background-color); padding: 12px; border-radius: 10px; border: 1px dashed rgba(150,150,150,0.5); margin-bottom: 20px;">
            <div style="font-size: 0.75rem; color: var(--text-color); opacity: 0.8; margin-bottom: 6px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🔌 Ext. Pairing Code</div>
            <div style="font-family: monospace; font-size: 0.8rem; color: var(--text-color); background: var(--secondary-background-color); padding: 8px; border-radius: 6px; border: 1px solid rgba(150,150,150,0.2); word-break: break-all;">
                {st.session_state.user_id}
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("<hr style='margin-top: 0;'>", unsafe_allow_html=True)
    st.sidebar.markdown("<div style='font-size: 0.8rem; color: var(--text-color); opacity: 0.6; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;'>Main Menu</div>", unsafe_allow_html=True)
    
    menu_options = [
        "⚙️ Profile & Settings",
        "📊 Dashboard (Expense Tracking)",
        "🧾 Tax Planner (Old vs New Regime)",
        "📈 Investment Portfolio",
        "🏦 Net Worth Tracker",
        "🔥 FIRE Planner (Retirement)",
        "🤖 AI CA Advisor (Grounded)",
        "📝 Transactions", 
        "🛡️ AI Insurance Advisor", 
        "🔍 Anomaly Finder",
        "👻 Ghost Spend Auditor", 
        "🤖 Financial Twin Simulation",
        "🚦 Safe-to-Spend Engine",
        "👨‍👩‍👧 Family Wealth Dashboard",
        "🔗 Bank Sync (Live AA)",
        "🏦 Trust Engine (Loan Predictor)",
        "🌳 Legacy Agent (Asset Discovery)",
        "🛑 Financial Guardrail"
    ]
    
    def clear_force_page():
        st.session_state.force_page = None

    choice = st.sidebar.radio("Navigation", menu_options, key="sidebar_choice", on_change=clear_force_page, label_visibility="collapsed")
    
    # Auto-Close Sidebar on Mobile Click
    components.html("""
    <script>
        window.parent.document.addEventListener('click', function(event) {
            if (window.parent.innerWidth < 768) {
                let isSidebarClick = event.target.closest('[data-testid="stSidebar"] div[role="radiogroup"] label');
                if (isSidebarClick) {
                    setTimeout(() => {
                        let closeBtn = window.parent.document.querySelector('[data-testid="stSidebar"] button');
                        if (closeBtn) {
                            closeBtn.click();
                        } else {
                            window.parent.document.dispatchEvent(new KeyboardEvent('keydown', {'key': 'Escape'}));
                        }
                    }, 150);
                }
            }
        });
    </script>
    """, height=0)

    st.sidebar.markdown("<hr>", unsafe_allow_html=True)
    
    if st.sidebar.button("🚪 Log Out", use_container_width=True):
        supabase.auth.sign_out()
        for key in ['logged_in', 'user_email', 'user_id', 'show_auth_page', 'editing_account', 'force_page', 'ai_consent', 'aa_consent_token', 'has_synced_this_session']:
            st.session_state[key] = False if key in ['logged_in', 'show_auth_page', 'ai_consent', 'aa_consent_token', 'has_synced_this_session'] else ("" if key in ['user_email', 'user_id'] else None)
        st.rerun()

    # ==========================================
    # ✨ THE PRIVACY GATEKEEPER
    # ==========================================
    ai_powered_tools = ["🛡️ AI Insurance Advisor", "👻 Ghost Spend Auditor", "🤖 Financial Twin Simulation", "🤖 AI CA Advisor (Grounded)"]

    if choice in ai_powered_tools and not st.session_state.ai_consent:
        st.title("🛡️ AI Privacy & Consent")
        with st.container(border=True):
            st.info("👋 **Your Privacy Matters**")
            st.markdown("""
            To provide personalized insights, our AI (Gemini) analyzes your:
            * **Transaction Categories** (e.g., Groceries, Health)
            * **Spending Amounts**
            * **Account Balances**
            
            **Important:** Your real-world identity (Email/Name) is never sent to the AI. We only send the numbers and categories. By opting in, you agree to this processing under the **DPDP Act 2023**.
            """)
            if st.button("✅ I Agree & Opt-in", type="primary", use_container_width=True):
                st.session_state.ai_consent = True
                st.rerun()
            def decline_consent():
                st.session_state.sidebar_choice = "📊 Dashboard (Expense Tracking)"
            st.button("❌ No thanks, take me back", on_click=decline_consent)
        st.stop() 

    # --- ROUTING ---
    if st.session_state.force_page == "add_transaction":
        add_transaction.render_page(supabase)
    else:
        if choice == "⚙️ Profile & Settings":
            profile.render_page(supabase)
        elif choice == "📊 Dashboard (Expense Tracking)":
            dashboard.render_page(supabase)
        elif choice == "🧾 Tax Planner (Old vs New Regime)":
            tax_planner.render_page(supabase)
        elif choice == "📈 Investment Portfolio":
            portfolio.render_page(supabase)
        elif choice == "🏦 Net Worth Tracker":
            net_worth.render_page(supabase)
        elif choice == "🔥 FIRE Planner (Retirement)":
            fire_planner.render_page(supabase)
        elif choice == "🤖 AI CA Advisor (Grounded)":
            ai_advisor.render_page(supabase)
        elif choice == "📝 Transactions":
            transactions.render_page(supabase)
        elif choice == "🛡️ AI Insurance Advisor":
            insurance.render_page(supabase)
        elif choice == "🔍 Anomaly Finder":
            anomalies.render_page(supabase)
        elif choice == "👻 Ghost Spend Auditor":
            ghost_auditor.render_page(supabase)
        elif choice == "🤖 Financial Twin Simulation":
            financial_twin.render_page(supabase)
        elif choice == "🚦 Safe-to-Spend Engine":
            safe_to_spend.render_page(supabase)
        elif choice == "👨‍👩‍👧 Family Wealth Dashboard":
            family_wealth.render_page(supabase)
        elif choice == "🔗 Bank Sync (Live AA)":
            account_aggregator.render_page(supabase) 
        elif choice == "🏦 Trust Engine (Loan Predictor)":
            trust_engine.render_page(supabase)
        elif choice == "🌳 Legacy Agent (Asset Discovery)":
            legacy_agent.render_page(supabase)
        elif choice == "🛑 Financial Guardrail":
            financial_guardrail.render_page(supabase)


elif st.session_state.show_auth_page:
    st.markdown("""
    <style>
        [data-testid="stHeader"] { visibility: hidden; }
        
        [data-testid="stVerticalBlockBlockWrapper"] {
            background-color: var(--secondary-background-color) !important;
            border: 1px solid rgba(150, 150, 150, 0.2) !important;
            border-radius: 20px !important;
            padding: 2rem 2.5rem !important;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.05) !important;
            margin-top: 1rem;
        }
        div[data-testid="stTextInput"] label { display: none; }
        div[data-testid="stTextInput"] input {
            background-color: var(--background-color) !important; 
            border: 1px solid rgba(150, 150, 150, 0.2) !important;
            color: var(--text-color) !important; 
            border-radius: 12px !important;
            padding: 0.75rem 1rem !important;
        }
        
        /* Primary button — always a vivid gradient so it's visible in both themes */
        div[data-testid="stButton"] button[kind="primary"] {
            border-radius: 12px !important;
            font-weight: 800 !important;
            font-size: 1.1rem !important;
            border: none !important;
            padding: 0.75rem !important;
            transition: all 0.3s ease;
            background: linear-gradient(135deg, #2563EB, #9333EA) !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 15px rgba(37, 99, 235, 0.3) !important;
        }
        div[data-testid="stButton"] button[kind="primary"] p {
            color: #FFFFFF !important;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.4) !important;
            filter: brightness(1.1);
        }
        div[data-testid="stButton"] button[kind="secondary"] {
            background-color: transparent !important;
            color: var(--text-color) !important;
            opacity: 0.8 !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }
        div[data-testid="stButton"] button[kind="secondary"]:hover { opacity: 1 !important; }
        .forgot-pwd-btn button p { font-weight: 800 !important; }
    </style>
    """, unsafe_allow_html=True)

    st.button("← Back to Home", on_click=go_back_home)
    st.write("")

    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        with st.container(border=True):
            if st.session_state.auth_mode == 'login':
                st.markdown("<h1 style='text-align: center; color: var(--text-color); margin-bottom: 0.2rem; margin-top: 0; font-size: 2.2rem; font-weight: 800;'>Welcome Back</h1>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 2rem; font-size: 1.1rem;'>Please log in to your account</p>", unsafe_allow_html=True)
                login_email = st.text_input("Email", placeholder="👤   Email Address", key="login_email")
                login_password = st.text_input("Password", placeholder="🔒   Password", type="password", key="login_password")
                cc1, cc_space, cc2 = st.columns([1.5, 0.5, 1.5])
                with cc1:
                    st.checkbox("Remember me")
                with cc2:
                    st.markdown('<div class="forgot-pwd-btn">', unsafe_allow_html=True)
                    st.button("**Forgot Password?**", on_click=lambda: st.session_state.update(auth_mode='reset'), use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                st.write("") 
                if st.button("Log In", use_container_width=True, type="primary"):
                    try:
                        response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                        st.session_state.logged_in = True
                        st.session_state.user_email = response.user.email
                        st.session_state.user_id = response.user.id
                        st.session_state.show_auth_page = False 
                        st.rerun()
                    except Exception as e:
                        st.error("Login failed. Please check your email and password.")
                st.write("---")
                st.button("Don't have an account? **Sign Up**", use_container_width=True, on_click=lambda: st.session_state.update(auth_mode='signup'))

            elif st.session_state.auth_mode == 'signup':
                st.markdown("<h1 style='text-align: center; color: var(--text-color); margin-bottom: 0.2rem; margin-top: 0; font-size: 2.2rem; font-weight: 800;'>Create Account</h1>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 2rem; font-size: 1.1rem;'>Join FinGuru today</p>", unsafe_allow_html=True)
                signup_email = st.text_input("Email", placeholder="👤   Email Address", key="signup_email")
                signup_password = st.text_input("Password", placeholder="🔒   Password (min 6 chars)", type="password", key="signup_password")
                st.write("")
                if st.button("Sign Up", use_container_width=True, type="primary"):
                    try:
                        response = supabase.auth.sign_up({"email": signup_email, "password": signup_password})
                        st.success("Account created successfully! You can now log in.")
                        st.session_state.auth_mode = 'login'
                        st.rerun()
                    except Exception as e:
                        st.error(f"Sign up failed: {e}")
                st.write("---")
                st.button("Already have an account? **Log In**", use_container_width=True, on_click=lambda: st.session_state.update(auth_mode='login'))

            elif st.session_state.auth_mode == 'reset':
                st.markdown("<h1 style='text-align: center; color: var(--text-color); margin-bottom: 0.2rem; margin-top: 0; font-size: 2.2rem; font-weight: 800;'>Reset Password</h1>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 2rem; font-size: 1.1rem;'>Enter your email to receive a secure link.</p>", unsafe_allow_html=True)
                reset_email = st.text_input("Email", placeholder="👤   Email Address", key="reset_email_input")
                st.write("")
                if st.button("Send Reset Link", use_container_width=True, type="primary"):
                    if not reset_email:
                        st.warning("Please enter your email address first.")
                    else:
                        try:
                            supabase.auth.reset_password_for_email(reset_email)
                            st.success("✅ Secure link sent! Please check your inbox.")
                        except Exception as e:
                            st.error(f"Failed to send link: {e}")
                st.write("---")
                st.button("← Back to Log In", use_container_width=True, on_click=lambda: st.session_state.update(auth_mode='login'))

            elif st.session_state.auth_mode == 'update_pwd':
                st.markdown("<h1 style='text-align: center; color: var(--text-color); margin-bottom: 0.2rem; margin-top: 0; font-size: 2.2rem; font-weight: 800;'>New Password</h1>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 2rem; font-size: 1.1rem;'>Enter your new secure password below.</p>", unsafe_allow_html=True)
                new_password = st.text_input("New Password", placeholder="🔒   New Password", type="password", key="new_pwd_input")
                st.write("")
                if st.button("Save New Password", use_container_width=True, type="primary"):
                    if not new_password:
                        st.warning("Please enter a new password.")
                    else:
                        try:
                            supabase.auth.update_user({"password": new_password})
                            st.success("✅ Password updated! You can now log in.")
                            st.query_params.clear()
                            st.session_state.auth_mode = 'login'
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to update password. Did you click the link in your email? Error: {e}")
                st.write("---")
                st.button("← Back to Log In", use_container_width=True, on_click=lambda: st.session_state.update(auth_mode='login'))

else:
    # ==========================================
    # ✨ PRODUCTION LANDING PAGE (pre-login)
    # ==========================================
    st.markdown("""
    <div class="landing-hero">
        <div class="landing-eyebrow">AI-Powered Financial Management</div>
        <h1><span class="gradient">Manage your money with FinGuru</span></h1>
        <p class="landing-sub">
            A production-grade financial platform combining five deterministic computational engines
            with a grounded AI co-pilot. Every number is calculated, every insight is grounded in your data,
            and the AI assistant always answers from your actual financial figures — never invented data.
        </p>
        <div class="hero-pills">
            <span class="hero-pill">🧮 Rule-based tax computation</span>
            <span class="hero-pill">🎲 Monte Carlo retirement planning</span>
            <span class="hero-pill">📡 Grounded generative AI</span>
            <span class="hero-pill">🔐 Row-level security + AES-256</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c2:
        st.button("🚀 Start Free", on_click=go_to_auth, use_container_width=True, type="primary")

    st.write("")
    st.markdown(
        "<p style='text-align: center; color: var(--text-color); opacity: 0.8; font-size: 0.9rem; margin-bottom: 2rem;'>"
        "🔒 AES-256 Encryption &nbsp;&nbsp;|&nbsp;&nbsp; 🏛️ RBI Account Aggregator Ready &nbsp;&nbsp;|&nbsp;&nbsp; 📜 DPDP Act 2023 Compliant"
        "</p>", unsafe_allow_html=True)

    st.write("---")

    # ====== ALL MODULES: Computational Engines + AI + Protective Layers ======
    st.markdown("""
    <div class="section-head">
        <div class="section-eyebrow">Complete Feature Suite</div>
        <h2>Compute, advise, protect — all in one system</h2>
        <p>FinGuru combines five deterministic engines that compute your finances (tax, portfolio, net worth, retirement, health score) with ML-powered detection and an AI co-pilot grounded in your real numbers.</p>
    </div>
    """, unsafe_allow_html=True)

    # Row 1: The Five Core Engines
    st.markdown("""
    <div style="margin-bottom: 2.5rem;">
        <div style="text-align: left; font-weight: 700; font-size: 1rem; color: var(--text-color); margin-bottom: 1.2rem; opacity: 0.85;">
            🔧 Core Computational Engines
        </div>
    </div>
    """, unsafe_allow_html=True)

    core_modules = [
        ("🧾", "linear-gradient(135deg,#3B82F6,#6366F1)", "Income Tax Engine",
         "Computes Old Regime vs New Regime side by side using audited tax rules — slabs, deductions (80C, 80D, HRA), Section 87A rebate, 4% cess. Returns both regimes and your optimal choice with rupee savings highlighted.",
         ["Rule Engine", "Old vs New", "87A + Cess"]),
        ("📈", "linear-gradient(135deg,#10B981,#14B8A6)", "Portfolio Tracker",
         "Multi-asset tracking (stocks, mutual funds, fixed deposits, gold, property). Calculates absolute return %, XIRR, asset allocation by class, diversification score and portfolio health metrics — all deterministic.",
         ["XIRR Calculation", "Asset Allocation", "Health Score"]),
        ("🏦", "linear-gradient(135deg,#8B5CF6,#6D28D9)", "Net Worth Engine",
         "Aggregates liquid assets (bank accounts, wallets), investments (all types), and liabilities (loans, credit). Computes monthly snapshots for growth tracking and wealth trend analysis.",
         ["Assets − Liabilities", "Monthly Snapshots", "Trend Analysis"]),
        ("🔥", "linear-gradient(135deg,#F97316,#EF4444)", "FIRE Retirement Planner",
         "3,000-trial Monte Carlo simulation accounting for market volatility (14% default σ), inflation, and monthly contributions. Returns required corpus, median terminal value, 5th–95th percentiles, and probability of early retirement.",
         ["Monte Carlo", "P(FIRE)", "SWR Analysis"]),
        ("📊", "linear-gradient(135deg,#0EA5E9,#2DD4BF)", "Financial Health Score",
         "Single 0–100 composite score across six weighted dimensions: savings rate (25%), spending discipline (20%), debt load (15%), investment allocation (15%), tax efficiency (10%), FIRE readiness (15%). With actionable flags per dimension.",
         ["6 Pillars", "Weighted Composite", "Actionable Insights"]),
        ("🤖", "linear-gradient(135deg,#EC4899,#A855F7)", "AI CA Advisor",
         "Chat interface grounded exclusively in your computed tax, portfolio, net-worth and FIRE figures. Routes intents (tax, portfolio, FIRE, spending), calls deterministic tools, serializes results, and queries Gemini with a strict grounding prompt. Includes offline deterministic fallback.",
         ["Grounded Gemini", "Intent Router", "Offline Fallback"]),
    ]

    for i in range(0, len(core_modules), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(core_modules):
                emoji, grad, title, desc, tags = core_modules[i + j]
                tag_html = "".join(f'<span class="module-tag">{t}</span>' for t in tags)
                with cols[j]:
                    st.markdown(f"""
                    <div class="module-card">
                        <div class="module-icon" style="background:{grad};">{emoji}</div>
                        <div class="module-title">{title}</div>
                        <div class="module-desc">{desc}</div>
                        <div class="module-tags">{tag_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.write("")

    # Row 2: AI-Powered Detection & ML Layers
    st.markdown("""
    <div style="margin-bottom: 2rem; margin-top: 2rem;">
        <div style="text-align: left; font-weight: 700; font-size: 1rem; color: var(--text-color); margin-bottom: 1.2rem; opacity: 0.85;">
            🤖 ML Detection & Protective Layers
        </div>
    </div>
    """, unsafe_allow_html=True)

    detection_modules = [
        ("🛡️", "linear-gradient(135deg,#DC2626,#991B1B)", "Anomaly Detection",
         "Statistical machine learning flags unusual spending patterns, suspicious transaction amounts, and behavioral outliers in real time using isolation forests and rolling z-scores.",
         ["Isolation Forest", "Z-Score Analysis", "Real-time Alerts"]),
        ("🔍", "linear-gradient(135deg,#7C3AED,#5B21B6)", "Ghost Spend Auditor",
         "NLP-powered decoder for messy UPI strings and payment references. Uncovers micro-transactions and subscription charges silently draining surplus cash that users miss.",
         ["NLP Parsing", "Micro-transactions", "Spend Recovery"]),
        ("🚦", "linear-gradient(135deg,#059669,#047857)", "Safe-to-Spend Engine",
         "Linear regression forecasts upcoming bills from historical data. Returns a daily safe-to-spend amount that accounts for known expenses without triggering overdrafts or budget violations.",
         ["Linear Regression", "Bill Forecasting", "Liquidity Model"]),
        ("🤖", "linear-gradient(135deg,#06B6D4,#0891B2)", "Financial Twin Simulation",
         "Runs probability-based scenarios of your financial future using your real data. Chat with an AI simulation of your retired self for forward-looking insights and what-if analysis.",
         ["Scenario Planning", "AI Chat", "Future Simulation"]),
        ("🏦", "linear-gradient(135deg,#EC4899,#BE185D)", "Trust Engine (Loan Predictor)",
         "XGBoost classifier predicts loan eligibility using alternative behavioral signals (spending patterns, savings consistency, bill payment history) — a 'shadow credit score' without requiring CIBIL.",
         ["XGBoost", "Behavioral Signals", "Loan Scoring"]),
        ("🌳", "linear-gradient(135deg,#8B5CF6,#7C3AED)", "Legacy Agent (Asset Discovery)",
         "Maps all financial assets to successors and sends dormancy alerts if an account goes inactive — prevents 'financial ghosting' and ensures intergenerational wealth transfer clarity.",
         ["Asset Mapping", "Dormancy Alerts", "Legacy Planning"]),
    ]

    for i in range(0, len(detection_modules), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(detection_modules):
                emoji, grad, title, desc, tags = detection_modules[i + j]
                tag_html = "".join(f'<span class="module-tag">{t}</span>' for t in tags)
                with cols[j]:
                    st.markdown(f"""
                    <div class="module-card">
                        <div class="module-icon" style="background:{grad};">{emoji}</div>
                        <div class="module-title">{title}</div>
                        <div class="module-desc">{desc}</div>
                        <div class="module-tags">{tag_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.write("")

    # Row 3: Transaction & Account Management
    st.markdown("""
    <div style="margin-bottom: 2rem; margin-top: 2rem;">
        <div style="text-align: left; font-weight: 700; font-size: 1rem; color: var(--text-color); margin-bottom: 1.2rem; opacity: 0.85;">
            💳 Transaction Tracking & Account Integration
        </div>
    </div>
    """, unsafe_allow_html=True)

    account_modules = [
        ("📝", "linear-gradient(135deg,#F59E0B,#D97706)", "Transaction Management",
         "Log income and expenses manually or upload receipt images. Gemini extracts merchant, amount, date and category from photos; encrypted descriptions; bulk tagging and recurring transaction support.",
         ["Receipt OCR", "Auto-Categorize", "Encrypted Data"]),
        ("🔗", "linear-gradient(135deg,#14B8A6,#0D9488)", "Bank Sync (RBI Account Aggregator)",
         "Securely link your bank accounts via the RBI-regulated Account Aggregator network. Read-only, automated data ingestion from 200+ NPCI-certified banks without sharing credentials.",
         ["RBI-Regulated", "Multi-bank", "No Credentials"]),
        ("👨‍👩‍👧", "linear-gradient(135deg,#6366F1,#4F46E5)", "Family Wealth Dashboard",
         "Aggregate intergenerational finances (parents, spouse, children) with explicit two-way consent. See consolidated view without exposing individual transaction details for privacy.",
         ["Multi-party Consent", "Aggregation", "Privacy Boundary"]),
        ("🛡️", "linear-gradient(135deg,#F97316,#EA580C)", "Insurance Advisor",
         "Calculates optimal life and health cover based on your lifestyle (dependents, income, existing coverage). Maps recommendations to real-world policies from major insurers with premium quotes.",
         ["Coverage Calculator", "Policy Matching", "Premium Quotes"]),
        ("💰", "linear-gradient(135deg,#06B6D4,#0891B2)", "Safe Spending Guardrail",
         "Acts as a strict gatekeeper intercepting impulsive e-commerce checkouts. Requires AI authorization before spending is approved — prevents buyer's remorse and keeps you on your budget.",
         ["Impulse Blocker", "AI Authorization", "Budget Protection"]),
    ]

    for i in range(0, len(account_modules), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(account_modules):
                emoji, grad, title, desc, tags = account_modules[i + j]
                tag_html = "".join(f'<span class="module-tag">{t}</span>' for t in tags)
                with cols[j]:
                    st.markdown(f"""
                    <div class="module-card">
                        <div class="module-icon" style="background:{grad};">{emoji}</div>
                        <div class="module-title">{title}</div>
                        <div class="module-desc">{desc}</div>
                        <div class="module-tags">{tag_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.write("---")

    # ====== How It Works ======
    st.markdown("""
    <div class="section-head">
        <div class="section-eyebrow">Getting Started</div>
        <h2>Three steps to full financial visibility</h2>
    </div>
    """, unsafe_allow_html=True)
    hw1, hw2, hw3 = st.columns(3)
    with hw1:
        st.markdown("""<div class="step"><div class="step-num">1</div><h4>Create Account</h4><p>Sign up securely on Supabase Auth with email. Two-factor authentication optional.</p></div>""", unsafe_allow_html=True)
    with hw2:
        st.markdown("""<div class="step"><div class="step-num">2</div><h4>Connect & Track</h4><p>Link your banks via RBI Account Aggregator, log transactions, upload receipts for auto-extraction.</p></div>""", unsafe_allow_html=True)
    with hw3:
        st.markdown("""<div class="step"><div class="step-num">3</div><h4>Optimize & Plan</h4><p>Run tax/FIRE simulations, chat with the AI co-pilot, get alerts on anomalies and opportunities.</p></div>""", unsafe_allow_html=True)

    st.write("---")

    # ====== Privacy & Security ======
    with st.container(border=True):
        st.markdown("<h3 style='text-align: center;'>🛡️ Privacy & Security</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Your financial data is yours. FinGuru operates under the <b>DPDP Act 2023</b> with enterprise-grade protections.</p>", unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        p1.markdown("✔️ **Encryption at rest & transit:** AES-256 symmetric encryption for sensitive fields (transaction descriptions); TLS 1.3 for all network traffic.")
        p2.markdown("✔️ **Row-level security:** Supabase RLS enforces that every query is scoped to `auth.uid()` — cross-user data access is cryptographically impossible even with DB access.")
        st.write("")
        p3, p4 = st.columns(2)
        p3.markdown("✔️ **Anonymized AI:** Your real name, email and account numbers are **never** sent to Gemini. Only computed amounts and categories are included in AI prompts.")
        p4.markdown("✔️ **Right to be forgotten:** Delete all your data with one click — all records, transactions and profiles are permanently removed from Supabase.")

    st.write("---")

    # ====== Tech Stack ======
    st.markdown("""
    <div class="stack-strip">
        BUILT WITH &nbsp;·&nbsp; STREAMLIT 1.55.0 &nbsp;·&nbsp; SUPABASE (POSTGRES + ROW-LEVEL SECURITY) &nbsp;·&nbsp; GOOGLE GEMINI 2.0 FLASH &nbsp;·&nbsp; NUMPY + SCIPY &nbsp;·&nbsp; PLOTLY &nbsp;·&nbsp; SCIKIT-LEARN &nbsp;·&nbsp; XGBOOST &nbsp;·&nbsp; CRYPTOGRAPHY (FERNET)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center;'>Ready to take control?</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 2rem;'>Join thousands of users optimizing their finances with real computation and grounded AI.</p>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([1.5, 1, 1.5])
    with fc2:
        st.button("Create Your Free Account", type="primary", use_container_width=True, on_click=go_to_auth, key="footer_btn")
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.6; font-size: 0.8rem; margin-top: 3rem;'>© 2026 FinGuru. All rights reserved. | Privacy Policy | Terms of Service</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.4; font-size: 0.7rem;'>Disclaimer: FinGuru is an educational financial planning tool. Always consult a certified financial advisor before making investment or tax decisions.</p>", unsafe_allow_html=True)
