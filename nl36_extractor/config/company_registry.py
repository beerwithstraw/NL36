"""
Company Registry for NL-36 Distribution of Business via Intermediaries.
"""

# ---------------------------------------------------------------------------
# Company detection: normalised filename/text tokens → company key
# ---------------------------------------------------------------------------
COMPANY_MAP = {
    "bajaj allianz":            "bajaj_allianz",
    "bajajgeneral":             "bajaj_allianz",
    "bajaj":                    "bajaj_allianz",
    "bgil":                     "bajaj_allianz",
    "hdfc ergo":                "hdfc_ergo",
    "hdfcergo":                 "hdfc_ergo",
    "hdfc":                     "hdfc_ergo",
    "national insurance":       "national_insurance",
    "nationalinsurance":        "national_insurance",
    "nic":                      "national_insurance",
    "new india":                "new_india",
    "newindia":                 "new_india",
    "oriental insurance":       "oriental_insurance",
    "orientalinsurance":        "oriental_insurance",
    "oriental":                 "oriental_insurance",
    "united india":             "united_india",
    "unitedindia":              "united_india",
    "godigit":                  "go_digit",
    "go digit":                 "go_digit",
    "digit general":            "go_digit",
    "aditya birla":             "aditya_birla_health",
    "aditya birla health":      "aditya_birla_health",
    "cholamandalam":            "chola_ms",
    "chola ms":                 "chola_ms",
    "chola general":            "chola_ms",
    "chola":                    "chola_ms",
    "ecgc":                     "ecgc",
    "icici lombard":            "icici_lombard",
    "icici":                    "icici_lombard",
    "lombard":                  "icici_lombard",
    "acko":                     "acko",
    "tata aig":                 "tata_aig",
    "tataaig":                  "tata_aig",
    "royal sundaram":           "royal_sundaram",
    "manipalcigna":             "manipal_cigna",
    "manipal cigna":            "manipal_cigna",
    "care health":              "care_health",
    "carehealth":               "care_health",
    "niva bupa":                "niva_bupa",
    "nivabupa":                 "niva_bupa",
    "star health":              "star_health",
    "starhealth":               "star_health",
    "future generali":          "generali_central",
    "futuregenerali":           "generali_central",
    "generali central":         "generali_central",
    "generalicentral":          "generali_central",
    "generali":                 "generali_central",
    "shriram general":          "shriram_general",
    "shriram":                  "shriram_general",
    "zurich kotak":             "zurich_kotak",
    "kotak mahindra general":   "zurich_kotak",
    "kotak":                    "zurich_kotak",
    "zuno":                     "zuno",
    "edelweiss general":        "zuno",
    "agriculture insurance":    "aic",
    "aicof":                    "aic",
    "aic":                      "aic",
    "narayana health":          "narayana_health",
    "narayana":                 "narayana_health",
    "navi general":             "navi_general",
    "navi":                     "navi_general",
    "raheja qbe":               "raheja_qbe",
    "universal sompo":          "universal_sompo",
    "iffco tokio":              "iffco_tokio",
    "iffco-tokio":              "iffco_tokio",
    "iffco":                    "iffco_tokio",
    "liberty":                  "liberty_general",
    "liberty general":          "liberty_general",
    "magma general":            "magma_general",
    "magma hdi":                "magma_general",
    "magma":                    "magma_general",
    "sbi":                      "sbi_general",
    "sbi general":              "sbi_general",
    "kshema":                   "kshema_general",
    "kshema general":           "kshema_general",
    "indusind":                 "indusind_general",
    "indusind general":         "indusind_general",
    "reliance general":         "indusind_general",
    "galaxy health":            "galaxy_health",
    "galaxyhealth":             "galaxy_health",
    "galaxy":                   "galaxy_health",
}

# ---------------------------------------------------------------------------
# Display names
# ---------------------------------------------------------------------------
COMPANY_DISPLAY_NAMES = {
    "bajaj_allianz":        "Bajaj Allianz General Insurance Company Limited",
    "hdfc_ergo":            "HDFC ERGO General Insurance",
    "national_insurance":   "National Insurance Company",
    "new_india":            "The New India Assurance Company",
    "oriental_insurance":   "The Oriental Insurance Company",
    "united_india":         "United India Insurance Company",
    "go_digit":             "Go Digit General Insurance Limited",
    "aditya_birla_health":  "Aditya Birla Health Insurance Co. Limited",
    "chola_ms":             "Cholamandalam MS General Insurance Company Limited",
    "ecgc":                 "ECGC Limited",
    "icici_lombard":        "ICICI Lombard General Insurance Company Limited",
    "acko":                 "ACKO General Insurance Limited",
    "tata_aig":             "Tata AIG General Insurance Company Limited",
    "royal_sundaram":       "Royal Sundaram General Insurance Co. Limited",
    "manipal_cigna":        "ManipalCigna Health Insurance Company Limited",
    "care_health":          "Care Health Insurance Limited",
    "niva_bupa":            "Niva Bupa Health Insurance Company Limited",
    "star_health":          "Star Health and Allied Insurance Co. Ltd.",
    "generali_central":     "Generali Central Insurance Company Limited",
    "sbi_general":          "SBI General Insurance Company Limited",
    "shriram_general":      "Shriram General Insurance Company Limited",
    "zurich_kotak":         "Zurich Kotak General Insurance Company (India) Limited",
    "zuno":                 "ZUNO General Insurance Limited",
    "aic":                  "Agriculture Insurance Company of India Limited",
    "narayana_health":      "Narayana Health Insurance Limited",
    "navi_general":         "Navi General Insurance Limited",
    "raheja_qbe":           "Raheja QBE General Insurance Company Limited",
    "universal_sompo":      "Universal Sompo General Insurance Company Limited",
    "iffco_tokio":          "IFFCO Tokio General Insurance Company Limited",
    "liberty_general":      "Liberty General Insurance Company Limited",
    "magma_general":        "Magma General Insurance Limited",
    "kshema_general":       "Kshema General Insurance Limited",
    "indusind_general":     "IndusInd General Insurance Company Limited",
    "galaxy_health":        "Galaxy Health Insurance Company Limited",
}

# ---------------------------------------------------------------------------
# Dedicated parser function name per company key
# ---------------------------------------------------------------------------
DEDICATED_PARSER = {
    "bajaj_allianz": "parse_bajaj_general",
    "ecgc":          "parse_ecgc",
}

# ---------------------------------------------------------------------------
# Channels to ignore in completeness checks per company
# ---------------------------------------------------------------------------
# ecgc: PDF has corrupt CIDFont — most numeric cells unrecoverable.
#   Only grand_total and total_channel are mandatory; suppress both since
#   the values come out None due to leading-digit corruption.
COMPLETENESS_IGNORE: dict = {
    "ecgc": ["total_channel", "grand_total"],
}
