import streamlit as st
import pandas as pd
import time
import json
from datetime import datetime
from utils.security import encrypt_data, decrypt_data
from utils.anomaly_engine import check_and_alert_anomaly # ✨ NEW: Import the anomaly engine

# ==========================================
# --- 1. THE BACKGROUND SYNC ENGINE ---
# ==========================================
def run_background_sync(supabase, user_id, bank_data=None):
    """Fetches data from the uploaded JSON and returns (count, error_message)."""
    
    if 'aa_consent_token' not in st.session_state:
        st.session_state.aa_consent_token = False
    if 'has_synced_this_session' not in st.session_state:
        st.session_state.has_synced_this_session = False

    if st.session_state.aa_consent_token == True and st.session_state.has_synced_this_session == False:
        try:
            target_account_id = st.session_state.get('aa_selected_account_id')
            account_name = "Linked Bank Account" 
            
            if not target_account_id:
                acc_res = supabase.table("accounts").select("id, account_name").eq("user_id", user_id).execute()
                if not acc_res.data:
                    return 0, "No bank accounts found! Please add an account in the Dashboard first."
                target_account_id = acc_res.data[0]['id']
                account_name = acc_res.data[0].get('account_name', account_name)
            else:
                acc_res = supabase.table("accounts").select("account_name").eq("id", target_account_id).execute()
                if acc_res.data:
                    account_name = acc_res.data[0].get('account_name', account_name)

            if not bank_data or len(bank_data) == 0: 
                return 0, None
                
            # ✨ THE FIX 1: Detect if the JSON is a full export dict or a simple list
            transaction_list = []
            if isinstance(bank_data, dict) and "transactions" in bank_data:
                transaction_list = bank_data["transactions"]
            elif isinstance(bank_data, list):
                transaction_list = bank_data
            else:
                return 0, "Invalid JSON format. Cannot find transactions."
            
            existing_txns = supabase.table("transactions").select("amount, transaction_time").eq("user_id", user_id).execute()
            
            existing_fingerprints = set()
            if existing_txns.data:
                for t in existing_txns.data:
                    db_time = str(t['transaction_time']).replace('T', ' ')[:16]
                    existing_fingerprints.add((float(t['amount']), db_time))

            new_transactions = []
            raw_anomaly_data = [] 
            
            for txn in transaction_list:
                # ✨ THE FIX 2: Smartly check for both naming conventions
                desc = txn.get("desc") or txn.get("description", "Unknown")
                amt = float(txn.get("amount", 0.0))
                cat = txn.get("category", "Other")
                date = txn.get("date") or txn.get("transaction_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                json_time = str(date)[:16]
                fingerprint = (amt, json_time)
                
                if fingerprint not in existing_fingerprints:
                    new_transactions.append({
                        "user_id": user_id,
                        "account_id": target_account_id, 
                        "transaction_time": date,
                        "description": encrypt_data(desc), 
                        "amount": amt,
                        "category": cat,
                        "type": txn.get("type", "Expense") # dynamically grab Income/Expense if available
                    })
                    raw_anomaly_data.append({
                        "amount": amt,
                        "category": cat,
                        "desc": desc,
                        "date": date
                    })
            
            if new_transactions:
                supabase.table("transactions").insert(new_transactions).execute()
                
                user_res = supabase.table("profiles").select("email, full_name").eq("id", user_id).execute()
                if user_res.data:
                    user_email = user_res.data[0].get("email")
                    raw_name = user_res.data[0].get("full_name")
                    user_name = raw_name.split(" ")[0] if raw_name else "User"
                    
                    for raw_txn in raw_anomaly_data:
                        check_and_alert_anomaly(
                            supabase=supabase,
                            user_id=user_id,
                            user_email=user_email,
                            user_name=user_name,
                            amount=raw_txn["amount"],
                            category=raw_txn["category"],
                            description=raw_txn["desc"],
                            transaction_time_iso=raw_txn["date"],
                            account_name=account_name
                        )
            
            st.session_state.has_synced_this_session = True
            return len(new_transactions), None
            
        except Exception as e:
            return 0, f"Database Error: {str(e)}"
            
    return 0, None

# ==========================================
# --- 2. THE MAIN UI RENDERER ---
# ==========================================
def render_page(supabase):
    st.markdown("""
        <style>
        .aa-header-title {
            margin: 0 !important; 
            padding: 0 !important; 
            background: linear-gradient(45deg, #2563EB, #10b981) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">🔗</div>
            <h1 class="aa-header-title">Account Aggregator Sync</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Securely link your bank accounts using the RBI-regulated Account Aggregator network.</p>
    """, unsafe_allow_html=True)

    # Initialize all required states
    if 'aa_step' not in st.session_state: st.session_state.aa_step = 1
    if 'sync_error' not in st.session_state: st.session_state.sync_error = None
    if 'synced_count' not in st.session_state: st.session_state.synced_count = 0
    if 'aa_selected_account_id' not in st.session_state: st.session_state.aa_selected_account_id = None
    if 'just_synced' not in st.session_state: st.session_state.just_synced = False
    if 'aa_selected_duration' not in st.session_state: st.session_state.aa_selected_duration = "12 Months (Recurring)"

    # --- ACTIVE STATE UI ---
    if st.session_state.get('aa_consent_token', False) == True:
        st.write("---")
        
        if st.session_state.just_synced:
            st.success("🎉 Secure AA Link Established & Sync Complete!")
            with st.container(border=True):
                if st.session_state.synced_count > 0:
                    st.markdown(f"**{st.session_state.synced_count} new transactions** were securely pulled and synced to your encrypted database.")
                else:
                    st.markdown("**0 new transactions** synced. The system successfully detected and skipped existing duplicate transactions.")
            
            st.session_state.just_synced = False 
            st.write("---")

        c1, c2 = st.columns([3, 1])
        with c1:
            st.success("✅ **AA Status: Active (Consent Granted)**")
            st.info("Your bank accounts are securely linked. Transactions are automatically syncing in the background.")
        with c2:
            if st.button("Revoke Consent", use_container_width=True):
                st.session_state.aa_consent_token = False
                st.session_state.has_synced_this_session = False
                st.session_state.aa_step = 1
                st.session_state.aa_selected_account_id = None
                st.rerun()

        st.write("---")
        st.subheader("📥 Live Encrypted Ledger")
        show_decrypted = st.toggle("🔓 Decrypt Payloads for Viewing", value=False)

        with st.spinner("Fetching latest encrypted transactions..."):
            try:
                query = supabase.table("transactions").select("*").eq("user_id", st.session_state.user_id)
                if st.session_state.get('aa_selected_account_id'):
                    query = query.eq("account_id", st.session_state.aa_selected_account_id)
                    
                trans_res = query.order("transaction_time", desc=True).limit(10).execute()
                
                if trans_res.data:
                    df = pd.DataFrame(trans_res.data)
                    display_df = df[['transaction_time', 'type', 'category', 'amount', 'description']].copy()
                    display_df['transaction_time'] = pd.to_datetime(display_df['transaction_time'], format='ISO8601').dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    if show_decrypted:
                        display_df['description'] = display_df['description'].apply(lambda x: decrypt_data(str(x)) if pd.notnull(x) else "")
                        display_df.rename(columns={'description': 'Decrypted Merchant'}, inplace=True)
                    else:
                        display_df.rename(columns={'description': 'Encrypted Payload (Raw)'}, inplace=True)
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No transactions found for this linked account yet.")
            except Exception as e:
                st.error(f"Failed to fetch live ledger: {e}")
        return

    # --- WIZARD PROGRESS BAR ---
    st.write("---")
    
    display_step = min(st.session_state.aa_step, 3) 
    progress_val = int((display_step / 3) * 100) 
    
    st.progress(progress_val, text=f"Connection Progress: Step {display_step} of 3")
    st.write("")

    # --- Step 1: Discovery ---
    if st.session_state.aa_step == 1:
        with st.container(border=True):
            st.subheader("Step 1: Discover Accounts")
            st.markdown("Enter your phone number connected to your financial institutions.")
            mobile = st.text_input("Mobile Number", value="+91 ", max_chars=14)
            aa_handle = st.selectbox("Account Aggregator Handle", ["@onemoney", "@setu", "@finvu"])
            
            st.write("")
            if st.button("Discover Accounts", type="primary", use_container_width=True):
                cleaned_mobile = mobile.replace("+91", "").strip()
                if not cleaned_mobile.isdigit() or len(cleaned_mobile) != 10:
                    st.error("⚠️ Please enter a valid 10-digit mobile number.")
                else:
                    with st.spinner(f"Pinging FIPs via {aa_handle}..."):
                        time.sleep(1.5)
                        st.session_state.aa_step = 2
                        st.rerun()

    # --- Step 2: Select Account & Consent ---
    elif st.session_state.aa_step == 2:
        with st.container(border=True):
            st.subheader("Step 2: Select Account & Grant Consent")
            st.markdown("Select the account you wish to sync:")
            
            try:
                acc_res = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).execute()
                user_accounts = acc_res.data
            except Exception as e:
                user_accounts = []
                st.error(f"Error fetching accounts: {e}")

            if not user_accounts:
                st.warning("⚠️ No bank accounts found! Add one in 'Dashboard' first.")
                if st.button("← Go Back", use_container_width=True):
                    st.session_state.aa_step = 1
                    st.rerun()
            else:
                account_options = {}
                for acc in user_accounts:
                    b_name = acc.get('bank_name') or 'Bank'
                    acc_num = str(acc.get('account_number') or 'XXXX')[-4:] 
                    display_name = f"🏦 {b_name} - {acc['account_name']} (****{acc_num})"
                    account_options[display_name] = acc['id']
                
                selected_display = st.radio("Discovered Accounts", list(account_options.keys()))
                selected_id = account_options[selected_display]
                
                st.write("")
                st.session_state.aa_selected_duration = st.selectbox("Consent Duration", ["One-Time Fetch", "1 Month", "3 Months", "6 Months", "12 Months (Recurring)"], index=4)
                
                with st.expander("📄 View Consent Details"):
                    fip_name = selected_display.split('(')[0].replace('🏦', '').strip()
                    st.markdown(f"**FIP:** {fip_name}")
                    st.markdown("**Data:** Profile, Balances, Transactions")
                    st.markdown(f"**Duration:** {st.session_state.aa_selected_duration}")
                
                st.warning("Authorize read-only access to sync transactions.")
                
                st.write("")
                col1, col2 = st.columns(2)
                if col1.button("Deny", use_container_width=True):
                    st.session_state.aa_step = 1
                    st.rerun()
                if col2.button("Approve & Generate OTP", type="primary", use_container_width=True):
                    st.session_state.aa_selected_account_id = selected_id
                    st.session_state.aa_step = 3
                    st.rerun()

    # --- Step 3: OTP Verification & JSON UPLOAD ---
    elif st.session_state.aa_step == 3:
        with st.container(border=True):
            st.subheader("Step 3: Verify OTP & Upload Data")
            st.markdown("Because this is a simulated portfolio project, please upload your simulated bank JSON file to proceed.")
            
            uploaded_file = st.file_uploader("Upload Bank Statement (JSON format)", type=["json"])
            otp = st.text_input("6-Digit OTP", max_chars=6, placeholder="Enter OTP")
            
            st.write("")
            if st.button("Verify & Sync", type="primary", use_container_width=True):
                if len(otp) != 6:
                    st.error("⚠️ Invalid OTP. Please enter 6 digits.")
                elif uploaded_file is None:
                    st.error("⚠️ Please upload a JSON file to sync.")
                else:
                    try:
                        # Securely read the file in memory
                        user_bank_data = json.load(uploaded_file)
                        
                        with st.spinner("Syncing uploaded transactions to your secure ledger..."):
                            time.sleep(1.5)
                            st.session_state.aa_consent_token = True
                            
                            # Pass the loaded JSON directly to the sync engine
                            synced_count, sync_error = run_background_sync(supabase, st.session_state.user_id, user_bank_data)
                            
                            if sync_error:
                                st.session_state.aa_consent_token = False
                                st.session_state.sync_error = sync_error 
                                st.session_state.aa_step = 4 
                            else:
                                st.session_state.synced_count = synced_count
                                st.session_state.just_synced = True
                                st.session_state.aa_step = 1 
                            st.rerun() 
                    except json.JSONDecodeError:
                        st.error("⚠️ The uploaded file is not a valid JSON document.")
                    except Exception as e:
                        st.error(f"⚠️ An error occurred reading the file: {e}")

    # --- Step 4: Error Handling ---
    elif st.session_state.aa_step == 4:
        st.error(f"⚠️ **Sync Failed:** {st.session_state.sync_error}")
        if st.button("Retry Sync", type="primary"):
            st.session_state.has_synced_this_session = False 
            st.session_state.aa_step = 3 
            st.rerun()