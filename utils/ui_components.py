"""
Reusable UI Components
Centralizes common Streamlit UI patterns to avoid duplication.
"""
import streamlit as st
from typing import Optional, List, Dict, Any


def render_gradient_header(icon: str, title: str, subtitle: str,
                           gradient_colors: List[str] = None,
                           header_class: str = "custom-header") -> None:
    """
    Render a consistent gradient header across all pages.

    Args:
        icon: Emoji or icon string
        title: Main header title
        subtitle: Subtitle/description text
        gradient_colors: List of 2 hex colors for gradient (default: teal to blue)
        header_class: CSS class name for customization
    """
    if gradient_colors is None:
        gradient_colors = ["#10b981", "#3b82f6"]

    gradient_css = f"linear-gradient(45deg, {gradient_colors[0]}, {gradient_colors[1]})"

    st.markdown(f"""
        <style>
        .{header_class}-title {{
            margin: 0 !important;
            padding: 0 !important;
            background: {gradient_css} !important;
            -webkit-background-clip: text !important;
            background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
            color: transparent !important;
            display: inline-block !important;
            width: fit-content !important;
        }}
        </style>

        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color);
                        padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                {icon}
            </div>
            <h1 class="{header_class}-title">{title}</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem;
                  margin-bottom: 2rem; padding-left: 5px;">{subtitle}</p>
    """, unsafe_allow_html=True)


def render_metric_card(label: str, value: str, delta: Optional[str] = None,
                       delta_color: str = "normal", help_text: Optional[str] = None) -> None:
    """Render a styled metric card."""
    st.metric(label, value, delta=delta, delta_color=delta_color, help=help_text)


def render_alert_banner(message: str, alert_type: str = "info",
                        dismissible: bool = False) -> None:
    """
    Render a styled alert banner.

    Args:
        message: Alert message
        alert_type: One of 'info', 'success', 'warning', 'error'
        dismissible: Whether to show dismiss button
    """
    styles = {
        "info": {"bg": "rgba(59, 130, 246, 0.1)", "border": "rgba(59, 130, 246, 0.2)", "color": "#3b82f6", "icon": "ℹ️"},
        "success": {"bg": "rgba(46, 204, 113, 0.1)", "border": "rgba(46, 204, 113, 0.2)", "color": "#2ecc71", "icon": "✅"},
        "warning": {"bg": "rgba(255, 193, 7, 0.1)", "border": "rgba(255, 193, 7, 0.2)", "color": "#ffc107", "icon": "⚠️"},
        "error": {"bg": "rgba(231, 76, 60, 0.1)", "border": "rgba(231, 76, 60, 0.2)", "color": "#e74c3c", "icon": "🚨"},
    }

    style = styles.get(alert_type, styles["info"])

    dismiss_html = ""
    if dismissible:
        dismiss_html = """
        <button onclick="this.parentElement.style.display='none'"
                style="background: none; border: none; font-size: 1.2rem; cursor: pointer;
                       color: inherit; opacity: 0.5; padding: 0 10px;">×</button>
        """

    st.markdown(f"""
        <div style="background-color: {style['bg']}; border: 1px solid {style['border']};
                    border-radius: 8px; padding: 16px; margin: 16px 0;
                    display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 1.5rem;">{style['icon']}</span>
            <span style="color: {style['color']}; font-weight: 500; flex: 1;">{message}</span>
            {dismiss_html}
        </div>
    """, unsafe_allow_html=True)


def render_progress_bar(current: float, target: float, label: str = "",
                        show_percentage: bool = True) -> None:
    """
    Render a styled progress bar with color coding.

    Args:
        current: Current value
        target: Target/maximum value
        label: Optional label
        show_percentage: Whether to show percentage
    """
    if target <= 0:
        st.info(f"{label}: No target set")
        return

    percent = (current / target) * 100
    capped = min(percent, 100.0)

    if percent >= 100:
        color = "#dc3545"
        status = f"⚠️ Exceeded by {current - target:,.2f}"
    elif percent >= 85:
        color = "#ffc107"
        status = f"⚠️ {target - current:,.2f} remaining"
    else:
        color = "#2ecc71"
        status = ""

    label_html = f"<div style='display: flex; justify-content: space-between; margin-bottom: 5px;'>"
    if label:
        label_html += f"<span style='font-weight: bold; color: var(--text-color); opacity: 0.9;'>{label}</span>"
    if show_percentage:
        label_html += f"<span style='color: var(--text-color); opacity: 0.7; font-size: 0.9em;'>{percent:.1f}% used</span>"
    label_html += "</div>"

    st.markdown(f"""
        {label_html}
        <div style="background-color: rgba(150, 150, 150, 0.2); border-radius: 8px;
                    height: 12px; width: 100%; overflow: hidden;">
            <div style="background-color: {color}; height: 100%; width: {capped}%;
                        transition: width 0.5s ease-in-out;"></div>
        </div>
        {f"<div style='margin-top: 4px; color: {color}; font-size: 0.85rem;'>{status}</div>" if status else ""}
    """, unsafe_allow_html=True)


def render_category_progress_bars(categories: List[Dict], title: str = "Category Breakdown") -> None:
    """
    Render multiple category progress bars.

    Args:
        categories: List of dicts with keys: name, spent, target
        title: Section title
    """
    st.markdown(f"<h5 style='margin-bottom: 15px;'>{title}</h5>", unsafe_allow_html=True)

    for cat in categories:
        name = cat['name']
        spent = cat['spent']
        target = cat['target']

        if target == 0 and spent == 0:
            continue

        display_target = target if target > 0 else spent
        pct = (spent / display_target) * 100 if display_target > 0 else 0
        capped_pct = min(pct, 100.0)

        if pct >= 100:
            color = "#dc3545"
        elif pct >= 85:
            color = "#ffc107"
        else:
            color = "#2ecc71"

        st.markdown(f"""
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
                    <span style="color: var(--text-color); font-weight: 500;">{name}</span>
                    <span style="color: var(--text-color); opacity: 0.8;">₹{spent:,.0f} / ₹{target:,.0f}</span>
                </div>
                <div style="background-color: rgba(150, 150, 150, 0.2); border-radius: 4px; height: 6px; width: 100%; overflow: hidden;">
                    <div style="background-color: {color}; height: 100%; width: {capped_pct}%; transition: width 0.5s ease-in-out;"></div>
                </div>
            </div>
        """, unsafe_allow_html=True)


def render_transaction_row(row: Dict, show_account: bool = False) -> str:
    """
    Generate HTML for a single transaction row.

    Args:
        row: Transaction dict with keys: description, amount, type, category, transaction_time, is_recurring, account_name
        show_account: Whether to show account name

    Returns:
        HTML string
    """
    from utils.security import decrypt_data

    date_str = row['transaction_time'].strftime("%b %d, %Y")
    desc = decrypt_data(str(row['description'])).title() if row.get('description') else "Unknown"
    if row.get('is_recurring'):
        desc += " <span style='font-size: 0.8em; color: var(--text-color); opacity: 0.5;'>(Recur)</span>"

    amt_color = "#2ecc71" if row['type'] == 'Income' else "#e74c3c"
    arrow = "↗" if row['type'] == 'Income' else "↘"

    account_html = f" • 🏦 {row['account_name']}" if show_account and row.get('account_name') else ""

    return f"""<div style='display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(150,150,150,0.2);'>
        <div style='line-height: 1.3;'>
            <div style='font-weight: 600; font-size: 0.95rem; color: var(--text-color);'>{desc}</div>
            <div style='font-size: 0.8rem; color: var(--text-color); opacity: 0.7;'>{date_str} • {row['category']}{account_html}</div>
        </div>
        <div style='text-align: right; color: {amt_color}; font-weight: 700; font-size: 1.05rem;'>
            {arrow} ₹{row['amount']:,.2f}
        </div>
    </div>"""


def render_transaction_list(transactions: List[Dict], max_items: int = 6,
                            show_account: bool = False) -> None:
    """Render a list of transaction rows."""
    if not transactions:
        st.info("No transactions found.")
        return

    html = "<div style='display: flex; flex-direction: column; gap: 0px;'>"
    for row in transactions[:max_items]:
        html += render_transaction_row(row, show_account)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_section_divider() -> None:
    """Render a consistent section divider."""
    st.markdown("<hr style='margin: 1.5rem 0; border: none; border-bottom: 1px solid rgba(150,150,150,0.2);' />", unsafe_allow_html=True)


def render_empty_state(message: str, icon: str = "📊") -> None:
    """Render a friendly empty state."""
    st.markdown(f"""
        <div style="text-align: center; padding: 3rem 1rem; color: var(--text-color); opacity: 0.6;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">{icon}</div>
            <div style="font-size: 1.1rem;">{message}</div>
        </div>
    """, unsafe_allow_html=True)