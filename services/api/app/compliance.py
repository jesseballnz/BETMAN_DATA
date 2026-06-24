from __future__ import annotations

RG_DISCLAIMER = (
    "BETMAN provides racing data and insights only. It is not betting advice. "
    "Wager responsibly and only where lawful."
)

COMPLIANCE_RULES = {
    "NZ": {
        "jurisdiction": "NZ",
        "age_gate_minimum": 18,
        "responsible_gambling_message": "R18. Gamble responsibly. Set limits before you bet.",
        "support_url": "https://www.gamblinghelponline.org.nz/",
        "support_phone": "0800 654 655",
    },
    "AU": {
        "jurisdiction": "AU",
        "age_gate_minimum": 18,
        "responsible_gambling_message": (
            "18+. Chances are you're about to lose. Set a deposit limit."
        ),
        "support_url": "https://www.gamblinghelponline.org.au/",
        "support_phone": "1800 858 858",
    },
    "UK": {
        "jurisdiction": "UK",
        "age_gate_minimum": 18,
        "responsible_gambling_message": "18+. BeGambleAware.org. Take time to think.",
        "support_url": "https://www.begambleaware.org/",
        "support_phone": "0808 8020 133",
    },
}


def get_compliance_rule(jurisdiction: str | None) -> dict[str, str | int]:
    if not jurisdiction:
        jurisdiction = "NZ"
    return COMPLIANCE_RULES.get(jurisdiction.upper(), COMPLIANCE_RULES["NZ"]) | {
        "advisory": RG_DISCLAIMER,
        "product_positioning": "data_and_insights_only",
    }
