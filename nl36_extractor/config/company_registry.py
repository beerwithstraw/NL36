"""
Company Registry for NL-36 Distribution of Business via Intermediaries.
"""

# ---------------------------------------------------------------------------
# Company detection: normalised filename/text tokens → company key
# ---------------------------------------------------------------------------
COMPANY_MAP = {
    "bajaj allianz":                "bajaj_allianz",
    "bajajgeneral":                 "bajaj_allianz",
    "bajaj":                        "bajaj_allianz",
    "bgil":                         "bajaj_allianz",
}

# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------
COMPANY_DISPLAY_NAMES = {
    "bajaj_allianz": "Bajaj Allianz General Insurance Company Limited",
}

# ---------------------------------------------------------------------------
# Dedicated parser function name per company key
# ---------------------------------------------------------------------------
DEDICATED_PARSER = {
    "bajaj_allianz": "parse_bajaj_general",
}

# ---------------------------------------------------------------------------
# Channels to ignore in completeness checks per company
# ---------------------------------------------------------------------------
COMPLETENESS_IGNORE: dict = {}
