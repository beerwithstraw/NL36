"""Tests for extractor.normaliser — identical to NL36 normaliser."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from extractor.normaliser import clean_number, normalise_text


class TestCleanNumber:
    def test_none(self):
        assert clean_number(None) is None

    def test_empty(self):
        assert clean_number("") is None
        assert clean_number("   ") is None

    def test_dashes(self):
        for v in ("-", "--", "–", "—", "n/a", "nil"):
            assert clean_number(v) is None

    def test_plain_number(self):
        assert clean_number("1234") == 1234.0
        assert clean_number("1,234") == 1234.0
        assert clean_number("1,24,941") == 124941.0

    def test_space_broken(self):
        # Bajaj PDF: "7 32,479" → 732479
        assert clean_number("7 32,479") == 732479.0
        assert clean_number("2 30,973") == 230973.0

    def test_parentheses(self):
        assert clean_number("(500)") == -500.0
        assert clean_number("( 500 )") == -500.0

    def test_float(self):
        assert clean_number("3.14") == pytest.approx(3.14)

    def test_already_float(self):
        assert clean_number(42.0) == 42.0


class TestNormaliseText:
    def test_lowercase(self):
        assert normalise_text("Individual Agents") == "individual agents"

    def test_strips_plus(self):
        # '+' not in kept chars
        assert normalise_text("Grand Total (A+B)") == "grand total (ab)"

    def test_strips_newlines(self):
        result = normalise_text("No. of\nPolicies")
        assert "\n" not in result

    def test_none(self):
        assert normalise_text(None) == ""

    def test_collapse_spaces(self):
        assert normalise_text("a  b   c") == "a b c"
