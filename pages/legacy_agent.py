import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
import networkx as nx
from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe

# Initialize AI client
genai_client = get_gemini_client()

# ✨ NEW FEATURE: The Pop-up Claim Toolkit Modal
@st.dialog("💼 India Asset Claim Navigator", width="large")
def show_claim_toolkit(asset_name):
    st.markdown(f"### Claiming: **{asset_name}**")
    st.markdown("Use this guide to understand the exact legal and administrative steps required to claim this asset in India.")
    
    c1, c2 = st.columns(2)
    asset_type = c1.selectbox("What type of asset is this?", 
                              ["Bank Savings / FD", "Mutual Funds", "Stocks (Demat)", "Life Insurance", "EPF / PPF"])
    nom_status = c2.radio("What is your status?", 
                          ["I am the Registered Nominee", "I am a Legal Heir (No Nomination)"])
    
    st.write("---")
    
    # Dynamic Logic based on Indian Financial Laws
    if nom_status == "I am the Registered Nominee":
        st.success("✅ **Fast Track Settlement:** Because you are the registered nominee, the RBI/SEBI mandates settlement within 15-30 days of document submission.")
        
        st.markdown("#### 📄 Document Checklist")
        docs = ["Original Death Certificate (issued by Municipal Authority)", "Your PAN Card & Aadhaar Card (Self-Attested)", "Cancelled Cheque (with your name printed)"]
        
        if asset_type == "Bank Savings / FD":
            docs.append("Form DA3 (Standard Bank Deceased Claim Form)")
            docs.append("Original Passbook or FD Receipt")
        elif asset_type == "Mutual Funds":
            docs.append("Transmission Request Form (Form T3)")
            docs.append("FATCA/CRS Declaration")
        elif asset_type == "Stocks (Demat)":
            docs.append("Transmission Form (Annexure O)")
            docs.append("Client Master Report (CMR) of your own Demat account")
        elif asset_type == "Life Insurance":
            docs.append("Original Policy Bond")
            docs.append("Claim Form A (from the Insurer)")
            docs.append("Medical Attendant's Certificate (if applicable)")
        elif asset_type == "EPF / PPF":
            docs.append("Form 20 (for EPF) or Form G (for PPF)")
            
        for doc in docs:
            st.markdown(f"- {doc}")
            
        st.markdown("#### 👣 Next Steps")
        st.markdown("1. **Gather Documents:** Collect all documents listed above. Keep 3 photocopies of each.")
        st.markdown("2. **Branch Visit:** Visit the home branch or the Mutual Fund Registrar (CAMS/KFintech).")
        st.markdown("3. **Submit & Await:** Submit the file. The funds will be transferred electronically to your provided cancelled cheque account.")
        
        if asset_type in ["Bank Savings / FD", "Mutual Funds"]:
            st.info("💡 **Pro-Tip (Fiduciary Duty):** Remember, for banks and mutual funds, a nominee is legally considered a 'Trustee'. You are receiving this money on behalf of the legal heirs and are obligated to distribute it according to the Will or Hindu Succession Act.")
        elif asset_type == "Stocks (Demat)":
            st.info("💡 **Pro-Tip (Absolute Ownership):** Under the Companies Act, a nominee for Demat shares becomes the absolute legal owner, overriding even a Will!")

    else:
        st.error("⚠️ **Legal Route Required:** Because there is no nomination, this process will take 6 to 8 months and requires intervention from a Civil Court.")
        
        st.markdown("#### 📄 Document Checklist")
        st.markdown("- Original Death Certificate")
        st.markdown("- **Succession Certificate** (Issued by a Civil Court) OR **Probate of Will**")
        st.markdown("- Notarized Indemnity Bond on Non-Judicial Stamp Paper")
        st.markdown("- No Objection Certificates (NOC) signed by all other Class 1 Legal Heirs")
        st.markdown("- Your KYC (PAN & Aadhaar)")
        
        st.markdown("#### 👣 Next Steps")
        st.markdown("1. **Hire Legal Counsel:** You must apply to the local civil court for a Succession Certificate. This process includes publishing a notice in a local newspaper.")
        st.markdown("2. **Gather NOCs:** Get written affidavits from your siblings, parent, or spouse stating they have no objection to you claiming this asset.")
        st.markdown("3. **Submit to Institution:** Once the court grants the certificate, submit it along with the Indemnity Bond to the bank or registrar.")
        
        st.warning("🚨 **Beware of the IEPF:** If an asset remains unclaimed for 7 consecutive years, it is transferred to the government's Investor Education and Protection Fund (IEPF). Reclaiming it from the IEPF is extremely difficult.")

def render_page(supabase):
    # ✨ THE FIX: Moved gradient styles to a dedicated CSS class with !important tags to prevent Streamlit render glitches
    st.markdown("""
        <style>
        .legacy-header-title {
            margin: 0 !important; 
            padding: 0 !important; 
            background: linear-gradient(45deg, #16a34a, #0284c7) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">🌳</div>
            <h1 class="legacy-header-title">Intergenerational Legacy Agent</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Prevent 'financial ghosting'. Map your assets to your successors permanently, and securely view assets assigned to you.</p>
    """, unsafe_allow_html=True)

    # --- 0. ENSURE USER EMAIL EXISTS ---
    user_email = st.session_state.get('user_email')
    if not user_email:
        st.warning("⚠️ We need your email address to link you to incoming assets.")
        user_email = st.text_input("Confirm your email address to unlock the Legacy Vault:")
        if st.button("Save Email"):
            st.session_state.user_email = user_email
            st.rerun()
        return

    # --- 1. FETCH OUTGOING DATA (Assets you own) ---
    try:
        acc_res = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).execute()
        my_accounts = acc_res.data
        my_account_ids = [acc['id'] for acc in my_accounts]
        
        trans_res = supabase.table("transactions").select("account_id, transaction_time").eq("user_id", st.session_state.user_id).execute()
        transactions = trans_res.data
        
        succ_res = supabase.table("successors").select("*").eq("owner_id", st.session_state.user_id).execute()
        my_successors = succ_res.data
        
        if my_account_ids:
            nom_res = supabase.table("nominations").select("*").in_("account_id", my_account_ids).execute()
            my_nominations = nom_res.data
        else:
            my_nominations = []
            
    except Exception as e:
        st.error(f"Failed to fetch your data: {e}")
        return

    email_to_name = {s['successor_email']: s.get('successor_name', s['successor_email']) for s in my_successors}

    # --- 2. FETCH INCOMING DATA (Assets assigned TO you) ---
    try:
        incoming_nom_res = supabase.table("nominations").select("*").eq("successor_email", user_email).execute()
        incoming_nominations = incoming_nom_res.data
        
        incoming_accounts = []
        if incoming_nominations:
            incoming_acc_ids = [n['account_id'] for n in incoming_nominations]
            in_acc_res = supabase.table("accounts").select("id, account_name").in_("id", incoming_acc_ids).execute()
            incoming_accounts = in_acc_res.data
            
    except Exception as e:
        st.error(f"Failed to fetch incoming vault data: {e}")
        return

    # Calculate Stagnancy
    df_trans = pd.DataFrame(transactions)
    last_active = {}
    if not df_trans.empty:
        df_trans['transaction_time'] = pd.to_datetime(df_trans['transaction_time'], format='ISO8601', utc=True).dt.tz_localize(None)
        last_active = df_trans.groupby('account_id')['transaction_time'].max().to_dict()

    stagnant_accounts = []
    today = datetime.now()
    stagnancy_threshold = today - timedelta(days=180)

    for acc in my_accounts:
        last_date = last_active.get(acc['id'])
        if pd.isnull(last_date) or last_date < stagnancy_threshold:
            stagnant_accounts.append({"id": acc['id'], "name": acc['account_name']})

    # --- 3. UI: ADD & REMOVE SUCCESSORS ---
    st.write("---")
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("👨‍👩‍👧 My Successors")
        st.markdown("Add family members by email. This permanently saves them to your vault.")
        
        with st.form("add_heir_form", clear_on_submit=True):
            h_name = st.text_input("Successor Name", placeholder="e.g., Aarav")
            h_email = st.text_input("Successor Email", placeholder="aarav@example.com")
            h_rel = st.selectbox("Relationship", ["Spouse", "Child", "Parent", "Sibling", "Trustee"])
            
            if st.form_submit_button("Add Successor", type="primary"):
                if h_name and h_email:
                    if h_email not in [h['successor_email'] for h in my_successors]:
                        supabase.table("successors").insert({
                            "owner_id": st.session_state.user_id,
                            "successor_name": h_name, 
                            "successor_email": h_email,
                            "relationship": h_rel
                        }).execute()
                        st.success("Successor added permanently!")
                        st.rerun()
                    else:
                        st.error("This email is already a successor!")
                else:
                    st.error("Please provide both a Name and an Email.")
                    
        if my_successors:
            st.markdown("**Manage Successors:**")
            for succ in my_successors:
                succ_name = succ.get('successor_name', succ['successor_email'])
                with st.expander(f"👤 {succ_name} ({succ['relationship']}) - {succ['successor_email']}"):
                    
                    assigned_acc_ids = [n['account_id'] for n in my_nominations if n['successor_email'] == succ['successor_email']]
                    assigned_assets = [a['account_name'] for a in my_accounts if a['id'] in assigned_acc_ids]
                    
                    if assigned_assets:
                        st.markdown(f"**Visible Assets:** {', '.join(assigned_assets)}")
                    else:
                        st.markdown("*No assets assigned to this person yet.*")
                        
                    st.write("")
                    btn_c1, btn_c2 = st.columns(2)
                    
                    # RESTORED: Draft Invite Feature with Gemini
                    if btn_c1.button("✉️ Draft Invite", key=f"inv_{succ['id']}", use_container_width=True):
                        with st.spinner("Drafting secure message..."):
                            try:
                                target_model = get_best_model(genai_client, prefer_flash=True)
                                model = genai_client.GenerativeModel(target_model)

                                asset_context = f"the following assets: {', '.join(assigned_assets)}" if assigned_assets else "my financial portfolio"
                                prompt = f"Draft a short, warm WhatsApp message to my {succ['relationship']}, {succ_name}. Let them know I added them as a 'Successor-Viewer' for {asset_context} on the AI Financial Twin app. Reassure them it's a Zero-Balance view for safety."
                                response_text = generate_content_safe(model, prompt)

                                if response_text:
                                    st.info("📋 **Copy & Paste:**\n\n" + response_text)
                                else:
                                    raise Exception("Empty response from model")
                            except Exception as e:
                                st.error(f"Failed to generate invite: {e}")

                    if btn_c2.button("❌ Remove", key=f"del_init_{succ['id']}", use_container_width=True):
                        st.session_state[f"confirm_del_{succ['id']}"] = True

                    if st.session_state.get(f"confirm_del_{succ['id']}", False):
                        st.error(f"⚠️ Remove {succ_name} and revoke their access to all assets?")
                        warn_c1, warn_c2 = st.columns(2)
                        if warn_c1.button("✅ Yes, Remove", key=f"yes_{succ['id']}", type="primary", use_container_width=True):
                            supabase.table("successors").delete().eq("id", succ['id']).execute()
                            supabase.table("nominations").delete().eq("successor_email", succ['successor_email']).in_("account_id", my_account_ids).execute()
                            st.session_state.pop(f"confirm_del_{succ['id']}", None)
                            st.rerun()
                        if warn_c2.button("❌ Cancel", key=f"no_{succ['id']}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_{succ['id']}", None)
                            st.rerun()

    with c2:
        st.subheader("🔗 Assign Visibility")
        if not my_accounts:
            st.info("Add a bank account in the Dashboard first.")
        elif not my_successors:
            st.info("Add a successor first to assign assets.")
        else:
            succ_display_to_email = {f"{s.get('successor_name', s['successor_email'])} ({s['successor_email']})": s['successor_email'] for s in my_successors}
            acc_names = [a['account_name'] for a in my_accounts]
            
            with st.form("link_form"):
                selected_acc_name = st.selectbox("Select Asset", acc_names)
                selected_display = st.selectbox("Grant Visibility To", ["None"] + list(succ_display_to_email.keys()))
                
                if st.form_submit_button("Update Nomination Graph"):
                    acc_id_match = next(a['id'] for a in my_accounts if a['account_name'] == selected_acc_name)
                    supabase.table("nominations").delete().eq("account_id", acc_id_match).execute()
                    
                    if selected_display != "None":
                        selected_email = succ_display_to_email[selected_display]
                        supabase.table("nominations").insert({
                            "account_id": acc_id_match,
                            "successor_email": selected_email,
                            "owner_email": st.session_state.user_email 
                        }).execute()
                        succ_name = email_to_name.get(selected_email, selected_email)
                        st.success(f"Visibility granted to {succ_name}")
                    else:
                        st.success(f"Visibility revoked for {selected_acc_name}")
                    st.rerun()

    # --- 4. NEO4J-STYLE GRAPH VISUALIZATION ---
    st.write("---")
    st.subheader("🕸️ Global Knowledge Graph")
    st.markdown("A unified view of assets you are passing down, and assets being passed down to you.")

    G = nx.Graph()
    if my_accounts:
        G.add_node("ME", type="user")
        for acc in my_accounts:
            node_type = "stagnant" if acc['id'] in [s['id'] for s in stagnant_accounts] else "active"
            G.add_node(acc['account_name'], type=node_type)
            G.add_edge("ME", acc['account_name'], relation="OWNS")

        for succ in my_successors:
            succ_name = succ.get('successor_name', succ['successor_email'])
            if succ_name not in G:
                G.add_node(succ_name, type="heir")
            
        for nom in my_nominations:
            acc_name = next((a['account_name'] for a in my_accounts if a['id'] == nom['account_id']), None)
            nom_email = nom['successor_email']
            succ_name = email_to_name.get(nom_email, nom_email) 
            if acc_name and succ_name in G:
                G.add_edge(acc_name, succ_name, relation="VIEWABLE_BY")

    if incoming_accounts:
        if "ME" not in G: G.add_node("ME", type="user")
        vaults_by_owner = {}
        for nom in incoming_nominations:
            owner = nom.get('owner_email', 'Unknown Benefactor')
            if owner not in vaults_by_owner: vaults_by_owner[owner] = []
            acc_name = next((a['account_name'] for a in incoming_accounts if a['id'] == nom['account_id']), None)
            if acc_name: vaults_by_owner[owner].append(acc_name)
                
        for owner_email, assets in vaults_by_owner.items():
            owner_display = owner_email.split('@')[0].capitalize() 
            vault_node = f"Vault of {owner_display}"
            G.add_node(vault_node, type="vault")
            G.add_edge("ME", vault_node, relation="ACCESSES")
            for acc_name in assets:
                node_name = f"🔒 {acc_name} (from {owner_display})"
                G.add_node(node_name, type="inherited")
                G.add_edge(vault_node, node_name, relation="CONTAINS")

    if len(G.nodes) > 0:
        pos = nx.spring_layout(G, seed=42)
        edge_x, edge_y = [], []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]; x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None]); edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=1, color='rgba(150,150,150,0.5)'), hoverinfo='none', mode='lines')

        node_x, node_y, node_text, node_color = [], [], [], []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x); node_y.append(y); node_text.append(node)
            n_type = G.nodes[node].get('type', 'active')
            node_color.append({"user": "#2563EB", "active": "#2ECC71", "stagnant": "#E74C3C", "heir": "#F39C12", "vault": "#8E44AD", "inherited": "#9B59B6"}.get(n_type, "#9B59B6"))

        node_trace = go.Scatter(
            x=node_x, y=node_y, mode='markers+text', text=node_text, textposition="bottom center", hoverinfo='text',
            marker=dict(size=30, color=node_color, line=dict(width=2, color='white')),
            textfont=dict(color=st.get_option("theme.textColor") if st.get_option("theme.textColor") else "gray")
        )

        fig = go.Figure(data=[edge_trace, node_trace],
                        layout=go.Layout(
                            showlegend=False, hovermode='closest', margin=dict(b=0, l=0, r=0, t=0),
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            height=500, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                        ))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("🔵 You | 🟢 Active Asset | 🔴 Stagnant Asset | 🟡 Successor | 🟣 Inherited Vault")
    else:
        st.info("No data available to draw the graph.")

    # ✨ Successor Action Center
    if incoming_accounts:
        st.write("---")
        st.subheader("💼 Successor Action Center")
        st.markdown("You have been assigned as a Successor-Viewer. Use the toolkit if you need to legally claim assets.")
        for inc_acc in incoming_accounts:
            col1, col2 = st.columns([3, 1])
            col1.markdown(f"**🔒 {inc_acc['account_name']}**")
            if col2.button("Open Claim Toolkit", key=f"claim_{inc_acc['id']}", use_container_width=True):
                show_claim_toolkit(inc_acc['account_name'])

    # --- 5. THE AI DISCOVERY AGENT ---
    st.write("---")
    st.subheader("🚨 Discovery Agent Alerts")
    unassigned_stagnant = [s for s in stagnant_accounts if s['id'] not in [n['account_id'] for n in my_nominations]]

    if not stagnant_accounts:
        st.success("✅ All your assets are active.")
    elif not unassigned_stagnant:
        st.success("✅ Stagnant assets are safely assigned. No ghosting detected!")
    else:
        st.error(f"⚠️ We detected {len(unassigned_stagnant)} stagnant, unassigned account(s).")
        st.write(", ".join([s['name'] for s in unassigned_stagnant]))
        if st.button("Consult AI Legacy Agent", type="primary"):
            with st.spinner("Agent is analyzing..."):
                try:
                    target_model = get_best_model(genai_client, prefer_flash=True)
                    model = genai_client.GenerativeModel(target_model)
                    prompt = f"You are an empathetic Intergenerational Wealth Agent. User has dormant accounts: {', '.join([s['name'] for s in unassigned_stagnant])}. Write a short 2-paragraph message noting the stagnation and urging them to assign a successor."
                    response_text = generate_content_safe(model, prompt)

                    if response_text:
                        st.warning(response_text)
                    else:
                        raise Exception("Empty response from model")
                except Exception as e:
                    st.error("Please assign a Successor-Viewer above.")