"""
Channel Master Registry for NL-36 Distribution of Business via Intermediaries.

All channel (row) labels in NL-36 forms are normalised to canonical keys.
Every company-specific label maps to one of these keys via CHANNEL_ALIASES.

Alias keys are the output of normalise_text() on observed PDF labels:
  lowercase, keep alphanumeric + spaces/:/()/'-., collapse spaces.
  Note: '+' is stripped, so "Grand Total (A+B)" → "grand total (ab)".
"""

# Canonical channel keys — ordered for output.
CHANNEL_ORDER = [
    "agent",
    "corporate_agent_bank",
    "corporate_agent_other",
    "broker",
    "micro_agent",
    "direct_selling",
    "direct_employees",
    "direct_online",
    "direct_others",
    "common_service_centre",
    "insurance_marketing_firm",
    "point_of_sales",
    "misp_direct",
    "misp_dealership",
    "web_aggregator",
    "referral_arrangements",
    "other_channels",
    "total_channel",
    "business_outside_india",
    "grand_total",
]

CHANNEL_DISPLAY_NAMES = {
    "agent":                    "Individual Agents",
    "corporate_agent_bank":     "Corporate Agents (Banks)",
    "corporate_agent_other":    "Corporate Agents (Others)",
    "broker":                   "Brokers",
    "micro_agent":              "Micro Agents",
    "direct_selling":           "Direct Business",
    "direct_employees":         "Direct - Officers/Employees",
    "direct_online":            "Direct - Online",
    "direct_others":            "Direct - Others",
    "common_service_centre":    "Common Service Centres (CSC)",
    "insurance_marketing_firm": "Insurance Marketing Firm",
    "point_of_sales":           "Point of Sales Person (Direct)",
    "misp_direct":              "MISP (Direct)",
    "misp_dealership":          "MISP (Dealership)",
    "web_aggregator":           "Web Aggregators",
    "referral_arrangements":    "Referral Arrangements",
    "other_channels":           "Other (to be specified)",
    "total_channel":            "Total (A)",
    "business_outside_india":   "Business outside India (B)",
    "grand_total":              "Grand Total (A+B)",
}

# Normalised PDF row labels → canonical channel key.
# Keys are normalise_text() output of observed PDF labels.
CHANNEL_ALIASES = {
    # Individual agents
    "individual agents":                        "agent",
    "individual agent":                         "agent",
    "agents":                                   "agent",
    "agent":                                    "agent",

    # Corporate agents - banks
    "corporate agents-banks":                   "corporate_agent_bank",
    "corporate agents - banks":                 "corporate_agent_bank",
    "corporate agents (bank)":                  "corporate_agent_bank",
    "corporate agents (banks)":                 "corporate_agent_bank",
    "corporate agent (bank)":                   "corporate_agent_bank",
    "corporate agent (banks)":                  "corporate_agent_bank",

    # Corporate agents - others
    "corporate agents -others":                 "corporate_agent_other",
    "corporate agents - others":                "corporate_agent_other",
    "corporate agents (other)":                 "corporate_agent_other",
    "corporate agents (others)":                "corporate_agent_other",
    "corporate agent (other)":                  "corporate_agent_other",
    "corporate agent (others)":                 "corporate_agent_other",

    # Brokers
    "brokers":                                  "broker",
    "broker":                                   "broker",

    # Micro agents
    "micro agents":                             "micro_agent",
    "micro agent":                              "micro_agent",

    # Direct Business (header row — may be blank or sub-total)
    "direct business":                          "direct_selling",

    # Direct sub-channels
    "officers/employees":                       "direct_employees",
    "online (through company website)":         "direct_online",
    "online":                                   "direct_online",
    "others":                                   "direct_others",

    # Common Service Centres
    "common service centres(csc)":              "common_service_centre",
    "common service centres (csc)":             "common_service_centre",
    "common service centre(csc)":               "common_service_centre",
    "common service centre (csc)":              "common_service_centre",
    "common service centre":                    "common_service_centre",
    "csc":                                      "common_service_centre",

    # Insurance Marketing Firm
    "insurance marketing firm":                 "insurance_marketing_firm",
    "imf":                                      "insurance_marketing_firm",

    # Point of Sales
    "point of sales person (direct)":           "point_of_sales",
    "point of sales person":                    "point_of_sales",
    "point of sales":                           "point_of_sales",
    "pos":                                      "point_of_sales",

    # MISP
    "misp (direct)":                            "misp_direct",
    "misp direct":                              "misp_direct",
    "misp (dealership)":                        "misp_dealership",
    "misp dealership":                          "misp_dealership",

    # Web aggregators
    "web aggregators":                          "web_aggregator",
    "web aggregator":                           "web_aggregator",

    # Referral
    "referral arrangements":                    "referral_arrangements",
    "referral":                                 "referral_arrangements",

    # Other channels — typo "sepcified" widespread; also variants with footnotes/blanks
    "other (to be sepcified)":                  "other_channels",
    "other (to be specified)":                  "other_channels",
    "other (to be specify)":                    "other_channels",
    "other to be specified":                    "other_channels",
    "other (sub intermediary)":                 "other_channels",
    "other":                                    "other_channels",

    # Direct sub-channels appearing as separate rows (dash-prefixed variants)
    "-officers/employees":                      "direct_employees",
    "-officers / employees":                    "direct_employees",
    "i).officers/employees":                    "direct_employees",
    "-online (through company website)":        "direct_online",
    "ii) online (through company website)":     "direct_online",
    "online (through company website)- others": "direct_online",   # Generali merged
    "-others":                                  "direct_others",
    "-others (other than through company website)": "direct_others",
    "iii) others":                              "direct_others",
    # Navi-specific direct channel labels
    "direct business internet":                 "direct_online",
    "direct business others":                   "direct_others",
    # United India colon-joined labels
    "direct business:officers/employees":       "direct_employees",
    "direct business:online (through company website)": "direct_online",
    "direct business:others":                   "direct_others",

    # Common Service Centres — American spelling variant
    "common service centers (csc)":             "common_service_centre",
    "common service centers":                   "common_service_centre",

    # Totals — '+' stripped by normalise_text, so "A+B" → "ab"
    "total (a)":                                "total_channel",
    "total":                                    "total_channel",
    "business outside india (b)":               "business_outside_india",
    "business outside india":                   "business_outside_india",
    "business outside india total (b)":         "business_outside_india",
    "grand total (ab)":                         "grand_total",
    "grand total":                              "grand_total",
}
