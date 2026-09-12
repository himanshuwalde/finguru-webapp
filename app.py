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
    st.markdown("""
    <div style='text-align: center; padding: 4rem 1rem 2rem 1rem;'>
        <h1 style='font-size: 4.5rem; font-weight: 900; background: linear-gradient(45deg, #2563EB, #9333EA); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; line-height: 1.2; margin-bottom: 1rem; display: inline-block;'>
            Manage your finances with<br>FinGuru
        </h1>
        <p style='font-size: 1.4rem; color: var(--text-color); opacity: 0.7; max-width: 800px; margin: 0 auto 2rem auto; line-height: 1.6;'>
            An AI-powered financial management platform that helps you track, analyze, and optimize your wealth with enterprise-grade security.
        </p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c2:
        st.button("🚀 Start Your Free Trial", on_click=go_to_auth, use_container_width=True, type="primary")

    st.write("")
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.6; font-weight: 600; letter-spacing: 1px; font-size: 0.9rem;'>TRUSTED BY THOUSANDS. SECURED BY ENTERPRISE STANDARDS.</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.8; font-size: 0.9rem; margin-bottom: 2rem;'>🔒 256-bit Encryption &nbsp;&nbsp;|&nbsp;&nbsp; 🏛️ RBI Account Aggregator Ready &nbsp;&nbsp;|&nbsp;&nbsp; 📜 DPDP Act 2023 Compliant</p>", unsafe_allow_html=True)
    st.write("---")

    st.markdown("<h2 style='text-align: center; font-size: 2.2rem; font-weight: 600; color: var(--text-color); margin-bottom: 3rem;'>Everything you need to manage your finances</h2>", unsafe_allow_html=True)

    features = [
        ("📝 Manage your transactions", "Easily log, track, and categorize your daily expenses and income. Upload receipts for AI-powered data extraction."),
        ("🛡️ Insurance Advisor", "Calculates optimal life and health cover based on your lifestyle, mapping them to real-world policies."),
        ("🔍 Anomaly Finder", "Monitors transactions using statistical machine learning to instantly flag unusual spending patterns or suspicious outliers."),
        ("👻 Ghost Spend Auditor", "Uses NLP to decode messy UPI strings, uncovering hidden micro-transactions silently draining your surplus."),
        ("🤖 Financial Twin Simulation", "Run probability-based Monte Carlo simulations and chat with an AI version of your future retired self."),
        ("🚦 Safe-to-Spend Engine", "A dynamic liquidity model that forecasts upcoming bills using linear regression to tell you exactly how much you can safely spend today."),
        ("👨‍👩‍👧 Family Wealth Dashboard", "Securely aggregate and manage intergenerational finances with explicit, two-way consent without exposing private transaction details."),
        ("🔗 Bank Sync (Live AA)", "Securely link your bank accounts using the RBI-regulated Account Aggregator network for automated, read-only data ingestion."),
        ("🏦 Trust Engine (Loan Predictor)", "Builds a 'Shadow Credit Score' using XGBoost on alternative behavioral data to accurately predict your loan eligibility."),
        ("🌳 Legacy Agent (Asset Discovery)", "Prevents 'financial ghosting' by securely mapping your assets to successors and notifying them if an account goes dormant."),
        ("🛑 Financial Guardrail", "Acts as a strict gatekeeper, intercepting impulsive e-commerce checkouts and requiring AI authorization before issuing virtual cards.")
    ]

    for i in range(0, len(features), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(features):
                title, desc = features[i + j]
                with cols[j]:
                    st.markdown(f"""
                    <div class="feature-card">
                        <div class="feature-title">{title}</div>
                        <div class="feature-desc">{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.write("---")
    st.markdown("<h2 style='text-align: center; font-size: 2rem; font-weight: 800; color: var(--text-color); margin-bottom: 2rem;'>How It Works</h2>", unsafe_allow_html=True)
    hw1, hw2, hw3 = st.columns(3)
    with hw1:
        st.markdown("""<div style='text-align: center;'><h1 style='color: #2563EB; font-size: 3rem; margin-bottom: 0;'>1</h1><h4>Create an Account</h4><p style='color: var(--text-color); opacity: 0.7;'>Sign up securely with PostgreSQL backend.</p></div>""", unsafe_allow_html=True)
    with hw2:
        st.markdown("""<div style='text-align: center;'><h1 style='color: #9333EA; font-size: 3rem; margin-bottom: 0;'>2</h1><h4>Track Spending</h4><p style='color: var(--text-color); opacity: 0.7;'>Upload receipts or log daily expenses.</p></div>""", unsafe_allow_html=True)
    with hw3:
        st.markdown("""<div style='text-align: center;'><h1 style='color: #16A34A; font-size: 3rem; margin-bottom: 0;'>3</h1><h4>Get AI Insights</h4><p style='color: var(--text-color); opacity: 0.7;'>Receive monthly anomaly and budget reports.</p></div>""", unsafe_allow_html=True)

    st.write("---")
    with st.container(border=True):
        st.markdown("<h3 style='text-align: center;'>🛡️ Our Privacy-First Promise</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>We believe your financial data belongs to you. FinGuru operates under the strict guidelines of the <b>DPDP Act 2023</b>.</p>", unsafe_allow_html=True)
        p1, p2 = st.columns(2)
        p1.markdown("✔️ **Anonymized AI:** Your real name and full account numbers are *never* sent to our AI models. We only process mathematical amounts and categories.")
        p2.markdown("✔️ **Right to be Forgotten:** You have absolute control. Our 'One-Click Wipe' permanently deletes all your records, transactions, and profiles from our servers.")

    st.write("---")
    st.markdown("<h2 style='text-align: center;'>Ready to outsmart yourself?</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 2rem;'>Join thousands of users who are building wealth with intelligence.</p>", unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([1.5, 1, 1.5])   
    with fc2:
        st.button("Create Your Free Account", type="primary", use_container_width=True, on_click=go_to_auth, key="footer_btn")
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.6; font-size: 0.8rem; margin-top: 3rem;'>© 2026 FinGuru AI. All rights reserved. | Privacy Policy | Terms of Service</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.4; font-size: 0.7rem;'>Disclaimer: FinGuru provides educational AI-generated insights. Always consult a certified financial planner for legal financial directives.</p>", unsafe_allow_html=True)