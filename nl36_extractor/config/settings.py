"""
Global constants and configuration for the NL36 Extractor.

NL-36 Distribution of Business via Intermediaries.
"""

# --- Versioning ---
EXTRACTOR_VERSION = "1.0.0"

# --- Default Paths ---
DEFAULT_INPUT_DIR = "inputs"
DEFAULT_OUTPUT_DIR = "outputs"

# --- FY Year String Helper ---

def make_fy_string(start_year: int, end_year: int) -> str:
    """Build the 6-character FY string.  2025, 2026 → '202526'."""
    return f"{start_year}{end_year % 100:02d}"


QUARTER_TO_FY = {
    "Q1": lambda y: make_fy_string(y, y + 1),      # June 2025 → 202526
    "Q2": lambda y: make_fy_string(y, y + 1),
    "Q3": lambda y: make_fy_string(y, y + 1),
    "Q4": lambda y: make_fy_string(y - 1, y),
}

# --- Master Sheet Column Order (fixed) ---
# One row per (company, quarter, year, channel).
MASTER_COLUMNS = [
    "Company_Name",        # A
    "Company_Key",         # B
    "Quarter",             # C
    "Fiscal_Year",         # D
    "Source_File",         # E
    "Channel_Key",         # F
    "Channel_Display_Name",# G
    # --- 8 data columns ---
    "CY_Qtr_Policies",     # H
    "CY_Qtr_Premium",      # I
    "CY_YTD_Policies",     # J
    "CY_YTD_Premium",      # K
    "PY_Qtr_Policies",     # L
    "PY_Qtr_Premium",      # M
    "PY_YTD_Policies",     # N
    "PY_YTD_Premium",      # O
]

# --- Excel Formatting ---
NUMBER_FORMAT = "#,##0.00"
LOW_CONFIDENCE_FILL_COLOR = "FFFF99"


def company_key_to_pascal(company_key: str) -> str:
    """snake_case → PascalCase.  'bajaj_general' → 'BajajGeneral'."""
    return company_key.replace("_", " ").title().replace(" ", "")
