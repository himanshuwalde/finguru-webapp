import streamlit as st
import json
from datetime import datetime
from utils.security import decrypt_data

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

    # ✨ THE FIX: Replaced basic st.title with the premium gradient header block
    st.markdown("""
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">⚙️</div>
            <h1 style="margin: 0; padding: 0; background: -webkit-linear-gradient(45deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; width: fit-content;">Profile & Settings</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Manage your identity, customize your AI, and secure your account.</p>
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
                
                st.info("🟢 **KYC Status:** Not Required for basic tracking. Verification required only for live bank sync.")
                
                if st.form_submit_button("Save Personal Info", type="primary"):
                    try:
                        # ✨ THE FIX: Added the user's email into the upsert payload so it saves to Supabase!
                        supabase.table("profiles").upsert({
                            "id": st.session_state.user_id,
                            "email": st.session_state.user_email, 
                            "full_name": full_name,
                            "phone": phone,
                            "updated_at": "now()"
                        }).execute()
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
                st.select_slider(
                    "⚠️ Investment Risk Tolerance", 
                    options=["Very Conservative", "Moderate", "Aggressive", "Wall Street Bets"],
                    value="Moderate"
                )

                if st.form_submit_button("Update AI Preferences", type="primary"):
                    try:
                        # ✨ THE FIX: Actually send the selected AI settings to the database
                        supabase.table("profiles").update({
                            "ai_tone": selected_tone,
                            "financial_phase": selected_phase,
                            "updated_at": "now()"
                        }).eq("id", st.session_state.user_id).execute()
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
                    st.session_state.confirm_total_wipe = True
                    
            if st.session_state.get('confirm_total_wipe'):
                st.error("⚠️ **CRITICAL:** This will permanently wipe all your accounts, transactions, and profile data. This cannot be undone.")
                wc1, wc2 = st.columns(2)
                if wc1.button("❌ Confirm Permanent Wipe", type="primary", use_container_width=True):
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
                if wc2.button("Cancel", use_container_width=True):
                    st.session_state.confirm_total_wipe = False
                    st.rerun()