"""
Tests for the NL-36 base extractor utilities and Bajaj parser.

Runs against the real Bajaj PDF to verify detection and extraction.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

BAJAJ_PDF = os.path.expanduser(
    "~/Desktop/Forms/FY2026/Q3/NL36/NL36_BajajGeneral.pdf"
)

# Skip all tests if the PDF is not present
pytestmark = pytest.mark.skipif(
    not os.path.exists(BAJAJ_PDF),
    reason=f"Bajaj NL-36 PDF not found at {BAJAJ_PDF}",
)


@pytest.fixture(scope="module")
def bajaj_table():
    import pdfplumber
    with pdfplumber.open(BAJAJ_PDF) as pdf:
        tables = pdf.pages[0].extract_tables()
        assert tables, "No tables found in Bajaj NL-36 PDF"
        return tables[0]


@pytest.fixture(scope="module")
def bajaj_extract():
    from extractor.companies.bajaj_general import parse_bajaj_general
    return parse_bajaj_general(BAJAJ_PDF, "bajaj_allianz", "Q3", "202526")


# ---------------------------------------------------------------------------
# detect_period_columns
# ---------------------------------------------------------------------------

class TestDetectPeriodColumns:
    def test_returns_8_columns(self, bajaj_table):
        from extractor.companies._base_nl36 import detect_period_columns
        col_map = detect_period_columns(bajaj_table)
        assert len(col_map) == 8, f"Expected 8 mapped columns, got {len(col_map)}: {col_map}"

    def test_all_periods_present(self, bajaj_table):
        from extractor.companies._base_nl36 import detect_period_columns
        col_map = detect_period_columns(bajaj_table)
        periods = {v[0] for v in col_map.values()}
        assert periods == {"cy_qtr", "cy_ytd", "py_qtr", "py_ytd"}

    def test_all_metrics_present(self, bajaj_table):
        from extractor.companies._base_nl36 import detect_period_columns
        col_map = detect_period_columns(bajaj_table)
        metrics = {v[1] for v in col_map.values()}
        assert metrics == {"policies", "premium"}

    def test_column_positions(self, bajaj_table):
        from extractor.companies._base_nl36 import detect_period_columns
        col_map = detect_period_columns(bajaj_table)
        assert col_map[2] == ("cy_qtr", "policies")
        assert col_map[3] == ("cy_qtr", "premium")
        assert col_map[4] == ("cy_ytd", "policies")
        assert col_map[5] == ("cy_ytd", "premium")
        assert col_map[6] == ("py_qtr", "policies")
        assert col_map[7] == ("py_qtr", "premium")
        assert col_map[8] == ("py_ytd", "policies")
        assert col_map[9] == ("py_ytd", "premium")


# ---------------------------------------------------------------------------
# detect_channel_rows
# ---------------------------------------------------------------------------

class TestDetectChannelRows:
    def test_finds_expected_channels(self, bajaj_table):
        from extractor.companies._base_nl36 import detect_channel_rows
        ch_rows = detect_channel_rows(bajaj_table)
        keys = set(ch_rows.values())
        for expected in ("agent", "broker", "corporate_agent_bank", "total_channel", "grand_total"):
            assert expected in keys, f"'{expected}' not detected; got {keys}"

    def test_detects_direct_sub_channels(self, bajaj_table):
        from extractor.companies._base_nl36 import detect_channel_rows
        ch_rows = detect_channel_rows(bajaj_table)
        keys = set(ch_rows.values())
        assert "direct_online" in keys, f"direct_online not detected; got {keys}"
        assert "direct_others" in keys, f"direct_others not detected; got {keys}"


# ---------------------------------------------------------------------------
# Full extraction
# ---------------------------------------------------------------------------

class TestBajajExtract:
    def test_extract_not_empty(self, bajaj_extract):
        assert len(bajaj_extract.channels) > 0, "No channels extracted"

    def test_metadata(self, bajaj_extract):
        assert bajaj_extract.company_key == "bajaj_allianz"
        assert bajaj_extract.form_type == "NL36"
        assert bajaj_extract.quarter == "Q3"
        assert bajaj_extract.year == "202526"

    def test_total_channel_extracted(self, bajaj_extract):
        channel_map = {c.channel_key: c for c in bajaj_extract.channels}
        assert "total_channel" in channel_map, "total_channel missing"
        total = channel_map["total_channel"]
        # Bajaj CY YTD policies: 2,74,74,096 → 27474096
        assert total.cy_ytd_policies == pytest.approx(27474096.0, abs=1.0)

    def test_grand_total_extracted(self, bajaj_extract):
        channel_map = {c.channel_key: c for c in bajaj_extract.channels}
        assert "grand_total" in channel_map, "grand_total missing"

    def test_agent_cy_qtr_premium(self, bajaj_extract):
        channel_map = {c.channel_key: c for c in bajaj_extract.channels}
        agent = channel_map.get("agent")
        assert agent is not None, "agent channel missing"
        # "73,654" → 73654
        assert agent.cy_qtr_premium == pytest.approx(73654.0, abs=1.0)

    def test_broker_cy_qtr_policies(self, bajaj_extract):
        channel_map = {c.channel_key: c for c in bajaj_extract.channels}
        broker = channel_map.get("broker")
        assert broker is not None
        # "3,216,219" → 3216219
        assert broker.cy_qtr_policies == pytest.approx(3216219.0, abs=1.0)

    def test_grand_total_identity(self, bajaj_extract):
        """Grand Total (A+B) == Total (A) + Business outside India (B)."""
        channel_map = {c.channel_key: c for c in bajaj_extract.channels}
        total = channel_map.get("total_channel")
        grand = channel_map.get("grand_total")
        boi   = channel_map.get("business_outside_india")
        assert total is not None and grand is not None

        for field in ("cy_ytd_premium", "py_ytd_premium"):
            t = getattr(total, field)
            g = getattr(grand, field)
            b = getattr(boi, field) if boi else None
            if t is not None and g is not None:
                expected = t + (b or 0.0)
                assert abs(g - expected) <= 3.0, (
                    f"{field}: grand={g}, total={t}, boi={b}, delta={abs(g-expected)}"
                )
