import streamlit as st
import json
from datetime import datetime
from utils.currency import CURRENCIES, symbol
from utils.security import decrypt_data
from utils.user_settings import invalidate_user_settings


@st.dialog("Delete account")
def confirm_total_wipe(supabase):
    """Ask before permanently wiping all of the user's data."""
    st.error("⚠️ **CRITICAL:** This will permanently wipe all your accounts, "
             "transactions, and profile data. This cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("❌ Confirm Permanent Wipe", type="primary", use_container_width=True):
        try:
            user_id = st.session_state.user_id
            supabase.table("transactions").delete().eq("user_id", user_id).execute()
            supabase.table("accounts").delete().eq("user_id", user_id).execute()
            supabase.table("profiles").delete().eq("id", user_id).execute()

            st.success("Data wiped. Logging out...")
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        except Exception as e:
            st.error(f"Error during wipe: {e}")
            return  # keep the dialog open so the error is visible
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def render_page(supabase):
    # ✨ THE FIX: Upgraded Tab CSS to explicitly use dynamic theme variables
    st.markdown("""
    <style>
        /* Force the tab list container to span 100% width */
        div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
            display: flex;
            width: 100%;
        }
        
        /* Force individual tabs to grow equally, fill the space, and respect theme text color */
        div[data-testid="stTabs"] button[data-baseweb="tab"] {
            flex: 1 !important;
            font-size: 1.15rem !important; 
            font-weight: 600 !important;
            justify-content: center !important; 
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            color: var(--text-color) !important; 
            opacity: 0.7;
        }
        
        /* Highlight the active tab using the theme's primary color */
        div[data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--primary-color) !important;
            opacity: 1.0;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="page-header">
            <h2>Profile & Settings</h2>
            <p>Manage your identity, customize your AI, and secure your account.</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("---")

    # --- FETCH PROFILE DATA ---
    try:
        prof_res = supabase.table("profiles").select("*").eq("id", st.session_state.user_id).execute()
        user_profile = prof_res.data[0] if prof_res.data else {}
    except Exception:
        user_profile = {} 

    # --- THE TAB LAYOUT (Billing Removed) ---
    tab1, tab2, tab3 = st.tabs(["👤 Identity", "🧠 AI Persona", "🔐 Security & DPDP"])

    # ==========================================
    # TAB 1: IDENTITY & BASIC INFO
    # ==========================================
    with tab1:
        st.subheader("Personal Information")
        with st.container(border=True):
            st.text_input("Email Address", value=st.session_state.user_email, disabled=True, help="Your email cannot be changed.")
            
            with st.form("identity_form"):
                c1, c2 = st.columns(2)
                with c1:
                    full_name = st.text_input("Full Name", value=user_profile.get("full_name", ""))
                with c2:
                    phone = st.text_input("Phone Number", value=user_profile.get("phone", ""))

                cur_options = list(CURRENCIES.keys())
                current_cur = user_profile.get("preferred_currency", "INR")
                selected_cur = st.selectbox(
                    "🌍 Preferred Currency",
                    cur_options,
                    index=cur_options.index(current_cur) if current_cur in cur_options else 0,
                    help="The currency used everywhere money is shown and in AI answers. "
                         "Your amounts are still stored in ₹; when you pick a non-INR "
                         "currency we show their live-converted equivalent."
                )
                st.caption(f"Symbol shown across the app: **{symbol(selected_cur)}**")

                st.info("🟢 **KYC Status:** Not Required for basic tracking. Verification required only for live bank sync.")

                if st.form_submit_button("Save Personal Info", type="primary"):
                    try:
                        # ✨ THE FIX: Added the user's email into the upsert payload so it saves to Supabase!
                        supabase.table("profiles").upsert({
                            "id": st.session_state.user_id,
                            "email": st.session_state.user_email,
                            "full_name": full_name,
                            "phone": phone,
                            "preferred_currency": selected_cur,
                            "updated_at": "now()"
                        }).execute()
                        # Apply the currency immediately app-wide (all pages + AI).
                        st.session_state.preferred_currency = selected_cur
                        invalidate_user_settings()
                        st.success("Profile updated successfully!")
                    except Exception as e:
                        st.error(f"Failed to update profile: {e}")

    # ==========================================
    # TAB 2: AI PERSONA HUB
    # ==========================================
    with tab2:
        st.subheader("Customize Your Financial Twin")
        st.markdown("Control how the AI Guardrail and Twin analyze your spending and talk to you.")
        with st.container(border=True):
            with st.form("ai_settings_form"):
                
                current_tone = user_profile.get("ai_tone", "Strict Accountant")
                tone_options = ["Gentle Advisor", "Strict Accountant", "Brutal Reality Check"]
                tone_idx = tone_options.index(current_tone) if current_tone in tone_options else 1
                
                selected_tone = st.selectbox(
                    "🤖 AI Conversational Tone", 
                    tone_options, 
                    index=tone_idx,
                    help="Determines how harsh the AI is when you try to buy something impulsive."
                )
                
                st.write("")
                
                current_phase = user_profile.get("financial_phase", "Building Wealth")
                phase_options = ["Student/Entry Level", "Building Wealth", "Family Planning", "Nearing Retirement"]
                phase_idx = phase_options.index(current_phase) if current_phase in phase_options else 1
                
                selected_phase = st.selectbox(
                    "📈 Current Financial Phase", 
                    phase_options,
                    index=phase_idx,
                    help="Helps the Financial Twin simulate appropriate future scenarios."
                )
                
                st.write("")
                current_risk = user_profile.get("risk_tolerance", "Moderate")
                risk_options = ["Very Conservative", "Moderate", "Aggressive", "Wall Street Bets"]
                risk_idx = risk_options.index(current_risk) if current_risk in risk_options else 1

                selected_risk = st.select_slider(
                    "⚠️ Investment Risk Tolerance",
                    options=risk_options,
                    value=risk_options[risk_idx]
                )

                if st.form_submit_button("Update AI Preferences", type="primary"):
                    try:
                        # ✨ THE FIX: Actually send the selected AI settings to the database
                        supabase.table("profiles").update({
                            "ai_tone": selected_tone,
                            "financial_phase": selected_phase,
                            "risk_tolerance": selected_risk,
                            "updated_at": "now()"
                        }).eq("id", st.session_state.user_id).execute()
                        # Apply the persona immediately so the AI adapts on the
                        # very next rerun, and let the settings loader re-fetch.
                        st.session_state.ai_tone = selected_tone
                        st.session_state.financial_phase = selected_phase
                        st.session_state.risk_tolerance = selected_risk
                        invalidate_user_settings()
                        st.success("AI Persona updated! The Guardrail will now adapt to these settings.")
                    except Exception as e:
                        st.error(f"Failed to update AI Preferences: {e}")

    # ==========================================
    # TAB 3: SECURITY & DPDP COMPLIANCE
    # ==========================================
    with tab3:
        st.subheader("Account Security")
        
        # 1. Update Password
        with st.container(border=True):
            st.markdown("#### Change Password")
            with st.form("change_pwd_form"):
                new_pwd = st.text_input("New Password", type="password")
                confirm_pwd = st.text_input("Confirm New Password", type="password")
                
                if st.form_submit_button("Update Password"):
                    if new_pwd != confirm_pwd:
                        st.error("Passwords do not match!")
                    elif len(new_pwd) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            supabase.auth.update_user({"password": new_pwd})
                            st.success("Password successfully updated!")
                        except Exception as e:
                            st.error(f"Failed to update password: {e}")

        # 2. DPDP Data Portability
        st.write("")
        st.subheader("DPDP Act 2023 - Data Management")
        with st.container(border=True):
            st.markdown("You have the right to data portability and the right to be forgotten.")
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("**Export Data**")
                st.caption("Download a complete JSON file of your accounts and decrypted transactions.")
                if st.button("📥 Prepare JSON Export", use_container_width=True):
                    with st.spinner("Encrypting and packaging your data..."):
                        try:
                            acc_res = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).execute()
                            txn_res = supabase.table("transactions").select("*").eq("user_id", st.session_state.user_id).execute()
                            
                            decrypted_txns = []
                            for t in txn_res.data:
                                t_copy = t.copy()
                                t_copy['description'] = decrypt_data(t['description'])
                                decrypted_txns.append(t_copy)
                                
                            export_data = {
                                "accounts": acc_res.data,
                                "transactions": decrypted_txns
                            }
                            
                            st.download_button(
                                label="Download Now",
                                data=json.dumps(export_data, default=str),
                                file_name=f"FinGuru_export_{datetime.now().strftime('%Y%m%d')}.json",
                                mime="application/json",
                                type="primary",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error("Failed to package data.")

            with c2:
                st.markdown("**Delete Account**")
                st.caption("Permanently wipe all records, transactions, and profiles.")
                if st.button("🗑️ Request Account Deletion", use_container_width=True):
                    confirm_total_wipe(supabase)