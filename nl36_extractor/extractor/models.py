"""
Data models for the NL-36 Distribution of Business via Intermediaries extractor.

NL-36 structure: rows = distribution channels, cols = 4 periods × 2 metrics.
No LOB breakdown — one flat list of NL36ChannelRow objects per company/quarter.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class NL36ChannelRow:
    """Holds extracted data for one distribution channel row."""
    channel_key: str                        # canonical key e.g. "agent"

    # Current Year
    cy_qtr_policies: Optional[float] = None
    cy_qtr_premium:  Optional[float] = None
    cy_ytd_policies: Optional[float] = None
    cy_ytd_premium:  Optional[float] = None

    # Prior Year
    py_qtr_policies: Optional[float] = None
    py_qtr_premium:  Optional[float] = None
    py_ytd_policies: Optional[float] = None
    py_ytd_premium:  Optional[float] = None


@dataclass
class NL36Extract:
    """Top-level container for one extracted NL-36 PDF."""
    source_file: str
    company_key: str
    company_name: str
    form_type: str                          # always "NL36"
    quarter: str                            # e.g. "Q3"
    year: str                               # e.g. "202526"
    channels: List[NL36ChannelRow] = field(default_factory=list)
    extraction_warnings: list = field(default_factory=list)
    extraction_errors: list = field(default_factory=list)

    def align_periods(self) -> None:
        """No-op: NL-36 channels always carry all 8 fields (set to None if absent).
        Present to satisfy pipeline.py calling extract.align_periods()."""
        pass
