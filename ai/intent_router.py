"""
Intent Router — rule-based dispatch for the CA chatbot.
No LLM is used here: a small set of (intent → keyword) rules classifies the
user's question and selects which deterministic tool(s) will build the
grounding context. Rules over LLM = fast, free, deterministic, and testable:
the same question always picks the same tool.

Order matters — more specific intents (tax_saving) are checked first.
"""
from __future__ import annotations

from typing import Dict, List

# (intent, [keywords that trigger it]) — checked in order, first match wins.
INTENT_RULES: List[tuple[str, List[str]]] = [
    ("tax_saving", [
        "save tax", "reduce tax", "avoid tax", "tax saving", "tax savings",
        "lower my tax", "how can i save", "cut my tax", "minimise tax",
    ]),
    ("tax", [
        "tax", "regime", "slab", "80c", "80d", "80ccd", "hra", "salary",
        "deduction", "rebate", "183", "filing", "itr", "tds",
    ]),
    ("fire", [
        "fire", "retire", "retirement", "corpus", "independence",
        "retire early", "swr", "withdraw",
    ]),
    ("portfolio", [
        "portfolio", "investment", "mutual fund", "mf", "fd ", "sip", "xirr",
        "return", "allocation", "gold", "stock", "asset class", "divest",
    ]),
    ("net_worth", [
        "net worth", "balance sheet", "asset", "liability", "loan", "debt",
        "what i own", "borrow",
    ]),
    ("spending", [
        "spend", "spent", "spending", "expense", "expenses", "budget",
        "cashflow", "cash flow", "monthly", "overspend", "where does my money",
        "money go", "money going",
    ]),
]


def route_intent(user_message: str) -> str:
    """
    Classify a user message into one of:
      tax_saving | tax | fire | portfolio | net_worth | spending | general
    """
    text = (user_message or "").lower().strip()
    for intent, keywords in INTENT_RULES:
        for kw in keywords:
            if kw in text:
                return intent
    return "general"


# Tools loaded for each intent. `general` pulls a compact view of everything.
INTENT_TOOLS: Dict[str, List[str]] = {
    "tax_saving": ["tax_calculator", "tax_saving_opportunities"],
    "tax":        ["tax_calculator", "tax_saving_opportunities"],
    "portfolio":  ["portfolio_summary", "net_worth"],
    "net_worth":  ["net_worth"],
    "fire":       ["fire_status", "net_worth"],
    "spending":   ["spending_summary", "net_worth"],
    "general":    ["spending_summary", "net_worth", "portfolio_summary",
                   "fire_status", "tax_calculator"],
}

TOOL_DESCRIPTIONS: Dict[str, str] = {
    "tax_calculator": "Computed income-tax for the saved tax profile — both regimes, "
                      "all line items, recommended regime and saving.",
    "tax_saving_opportunities": "Deterministic tax-saving gaps (unused 80C/80D, "
                                "home-loan interest, better-regime switch).",
    "portfolio_summary": "Investment portfolio — invested, current value, XIRR, "
                         "allocation and health score.",
    "net_worth": "Balance sheet — bank cash + investment assets, liabilities, net worth.",
    "fire_status": "FIRE plan — required corpus, Monte-Carlo probability, projected age.",
    "spending_summary": "Recent monthly spending — average, total, income context.",
}


def describe_tool(name: str) -> str:
    return TOOL_DESCRIPTIONS.get(name, name)