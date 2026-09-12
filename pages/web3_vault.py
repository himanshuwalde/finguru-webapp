import streamlit as st
import pandas as pd
import hashlib
import time
from datetime import datetime
from web3 import Web3

def generate_zk_proof(user_id, total_balance, threshold):
    """
    Simulates a Zero-Knowledge Proof (zk-SNARK).
    It proves to a third party (like a lender) that the user's balance is > threshold,
    WITHOUT revealing the actual balance. Returns a cryptographic hash.
    """
    if total_balance >= threshold:
        # Create a deterministic but secure hash representing the proof of solvency
        secret_salt = "zk_finance_protocol_2026"
        data_string = f"{user_id}_{threshold}_{secret_salt}"
        proof_hash = hashlib.sha256(data_string.encode()).hexdigest()
        return True, f"0x{proof_hash}"
    return False, None

def render_page(supabase):
    st.title("⛓️ Web3 Financial Data Vault")
    st.markdown("Self-sovereign identity and zero-knowledge financial proofs using simulated Polygon smart contracts.")

    # --- 1. FETCH ACTUAL DATA ---
    try:
        acc_res = supabase.table("accounts").select("balance").eq("user_id", st.session_state.user_id).execute()
        actual_balance = sum(float(acc['balance']) for acc in acc_res.data) if acc_res.data else 0.0
    except Exception:
        actual_balance = 0.0

    # Simulate a generated Web3 Wallet Address for the user based on their email
    w3 = Web3()
    seed = st.session_state.user_email.encode('utf-8')
    simulated_wallet = w3.keccak(seed).hex()[:42] # Looks like an ETH address

    # --- 2. SELF-SOVEREIGN IDENTITY DASHBOARD ---
    st.write("---")
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("### 🔐 Self-Sovereign Identity")
        st.markdown(f"**Connected Wallet:** `{simulated_wallet}`")
        st.markdown("Your financial data is currently encrypted off-chain. You control exactly who gets to verify your data via smart contract permissions.")
    
    with c2:
        with st.container(border=True):
            st.markdown("#### Data Monetization")
            monetize = st.toggle("Share Anonymized Data", value=False)
            if monetize:
                st.success("✅ Earning **0.5 FIN** tokens / day")
            else:
                st.caption("Opt-in to share zero-knowledge market trends and earn protocol rewards.")

    st.write("---")

    # --- 3. ZERO-KNOWLEDGE PROOF GENERATOR ---
    st.subheader("🛡️ Generate zk-Proof for Lenders")
    st.markdown("Prove your financial health to external dApps or banks without exposing your transaction history or exact account balance.")
    
    with st.container(border=True):
        col1, col2 = st.columns([1, 2])
        with col1:
            proof_target = st.selectbox("I want to prove my Net Worth is:", 
                                        ["Greater than ₹1,00,000", "Greater than ₹5,00,000", "Greater than ₹10,00,000"])
            
            # Extract the number from the string
            target_amount = float(proof_target.split('₹')[1].replace(',', ''))
            
            if st.button("Mint zk-Proof to Polygon", type="primary"):
                with st.spinner("Compiling Circom circuits and interacting with simulated Oracle..."):
                    time.sleep(1.5) # Simulate network delay
                    
                    is_valid, zk_hash = generate_zk_proof(st.session_state.user_id, actual_balance, target_amount)
                    
                    if is_valid:
                        st.session_state.latest_proof = {
                            "target": proof_target,
                            "hash": zk_hash,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    else:
                        st.error("❌ zk-Proof Failed: On-chain oracle verified your balance does not meet this threshold. No proof generated.")

        with col2:
            if 'latest_proof' in st.session_state:
                st.success("✅ **zk-SNARK Proof Generated & Verified!**")
                st.markdown(f"**Assertion:** `{st.session_state.latest_proof['target']}`")
                st.markdown(f"**Cryptographic Proof (TxHash):**")
                st.code(st.session_state.latest_proof['hash'], language='text')
                st.caption("You can share this hash with a lending protocol. They can verify the mathematical truth of your wealth without ever seeing your bank statements.")
            else:
                st.info("Select a threshold and mint a proof to see the cryptographic output here.")

    # --- 4. IMMUTABLE AUDIT TRAIL ---
    st.write("---")
    st.subheader("📜 Immutable Access Audit Trail")
    st.markdown("Smart contract logs showing exactly who accessed your data and when.")
    
    # Simulated audit trail data
    audit_data = [
        {"Date": datetime.now().strftime("%Y-%m-%d"), "Accessor": "Decentralized Lending Protocol A", "Action": "Verified zk-Proof (> ₹1L)", "Status": "Success"},
        {"Date": "2026-03-24", "Accessor": "Data Monetization Pool", "Action": "Aggregated Anonymized Spend Category", "Status": "Authorized"},
        {"Date": "2026-03-20", "Accessor": "Unknown Third Party", "Action": "Attempted to read Account Balance", "Status": "Blocked by Smart Contract"}
    ]
    
    st.dataframe(pd.DataFrame(audit_data), use_container_width=True, hide_index=True)