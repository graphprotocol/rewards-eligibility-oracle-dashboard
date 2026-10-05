"""
Unit tests for reading the "Upcoming Eligibility Criteria" table out of the
oracle's ELIGIBILITY_CRITERIA.md.

The fixture is the real document as of the MIN_SUBGRAPHS 1 -> 5 announcement.
"""

import os
import sys
from datetime import date
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from generate_dashboard import (
    _extract_threshold_changes,
    _parse_upcoming_criteria,
    fetch_eligibility_criteria,
)

DOC = """# Indexing Rewards Eligibility Criteria

Intro text.

---

## Upcoming Eligibility Criteria

**We will announce changes to the eligibility criteria in the table below.**

| Upcoming Requirement | Justification | Date Requirement Will Be Updated/Introduced (YYYY-MM-DD) |
|----------------------|---------------|----------------------------------------------------------|
| **Subgraph Coverage:** To be active, an indexer must serve at least 1 qualifying query on each of **5 subgraphs** that day, up from **1 subgraph**. Indexers still need **5+ active days** in a given **28 day** period. | Encourages indexers to sync and reliably serve a range of subgraphs rather than a single one. | 2026-10-06 |

> **Note**:
> We will typically allow a 14 day window after announcing a change before it goes live.

---

## Active Eligibility Criteria

The following criteria are used to identify indexers that should be eligible to receive indexing rewards.

- **Days Online Requirement:** Indexers must be active for **5+ days** in a given **28 day** period for rewards eligibility.
- **Daily Query Requirement:** To be active, an indexer must serve at least **1 qualifying query**.
- **Query Quality Requirements:** A qualifying query is one that simultaneously meets **all** of the following criteria:
  - Query Response HTTP Status: **200 OK**.
  - Query Response Latency: **< 5,000 ms**.

---

## Eligibility Requirements Changelog

| Requirement Category | Requirement Details | Effective Date (YYYY-MM-DD) |
|---|---|---|
| **Indexer Activity** | Indexers must be active for **5+ days**. | 2026-08-25 |
"""

BEFORE = date(2026, 10, 5)


def _table(*rows):
    header = (
        "| Upcoming Requirement | Justification | Date |\n"
        "|---|---|---|\n"
    )
    return f"## Upcoming Eligibility Criteria\n\n{header}" + "\n".join(rows) + "\n\n---\n"


class TestParseUpcomingCriteria:
    def test_reads_the_real_announcement(self):
        upcoming = _parse_upcoming_criteria(DOC, BEFORE)

        assert upcoming == [{
            "label": "Subgraph Coverage",
            "summary": (
                "To be active, an indexer must serve at least 1 qualifying query on each of "
                "5 subgraphs that day, up from 1 subgraph. Indexers still need 5+ active days "
                "in a given 28 day period."
            ),
            "justification": (
                "Encourages indexers to sync and reliably serve a range of subgraphs rather "
                "than a single one."
            ),
            "effective_date": "2026-10-06",
            "changes": {"MIN_SUBGRAPHS": 5},
        }]

    def test_keeps_a_change_on_its_effective_date(self):
        assert len(_parse_upcoming_criteria(DOC, date(2026, 10, 6))) == 1

    def test_drops_a_change_once_its_date_has_passed(self):
        # Nobody has to move the row into "Active" for the banner to go away.
        assert _parse_upcoming_criteria(DOC, date(2026, 10, 7)) == []

    def test_ignores_the_changelog_table(self):
        # The changelog also has dated rows; only the Upcoming section counts.
        assert all(row["label"] != "Indexer Activity" for row in _parse_upcoming_criteria(DOC, date(2026, 1, 1)))

    def test_empty_table(self):
        assert _parse_upcoming_criteria(_table(), BEFORE) == []

    def test_missing_section(self):
        assert _parse_upcoming_criteria("## Active Eligibility Criteria\n\n- x\n", BEFORE) == []

    def test_skips_rows_without_a_valid_date(self):
        body = _table(
            "| **Thing:** Something changes. | Because. | TBD |",
            "| **Other:** Something else. | Because. | 2026-13-40 |",
        )
        assert _parse_upcoming_criteria(body, BEFORE) == []

    def test_keeps_a_row_whose_values_cannot_be_read(self):
        # The text still reaches the page; only the derived numbers are missing.
        body = _table("| **Query Quality:** Latency limits are being tightened. | Faster. | 2026-11-01 |")
        [row] = _parse_upcoming_criteria(body, BEFORE)
        assert row["label"] == "Query Quality"
        assert row["changes"] == {}

    def test_orders_rows_by_date(self):
        body = _table(
            "| **B:** Later, from **5 subgraphs** to **8 subgraphs**. | x | 2026-12-01 |",
            "| **A:** Sooner, up from **1 subgraph** to **5 subgraphs**. | x | 2026-11-01 |",
        )
        assert [row["label"] for row in _parse_upcoming_criteria(body, BEFORE)] == ["A", "B"]

    def test_row_without_a_label(self):
        body = _table("| Subgraphs per day go to 5 subgraphs, up from 1 subgraph. | x | 2026-11-01 |")
        [row] = _parse_upcoming_criteria(body, BEFORE)
        assert row["label"] == ""
        assert row["changes"] == {"MIN_SUBGRAPHS": 5}


class TestExtractThresholdChanges:
    def test_up_from(self):
        assert _extract_threshold_changes("on 5 subgraphs, up from 1 subgraph") == {"MIN_SUBGRAPHS": 5}

    def test_from_to(self):
        text = "Latency must drop from 5,000 ms to 3,000 ms."
        assert _extract_threshold_changes(text) == {"MAX_LATENCY_MS": 3000}

    def test_blocks_and_days(self):
        text = (
            "Freshness goes to 20,000 blocks, down from 50,000 blocks, and indexers need "
            "7+ online days, up from 5 online days."
        )
        assert _extract_threshold_changes(text) == {
            "MAX_BLOCKS_BEHIND": 20000,
            "MIN_ONLINE_DAYS": 7,
        }

    def test_restated_value_is_not_a_change(self):
        assert _extract_threshold_changes("Indexers still need 5+ active days.") == {}

    def test_ambiguous_values_are_not_guessed(self):
        # Two candidate new values: report nothing rather than pick one.
        text = "Either 3 subgraphs or 4 subgraphs, up from 1 subgraph."
        assert _extract_threshold_changes(text) == {}


class TestFetchEligibilityCriteria:
    def test_returns_active_and_upcoming(self):
        response = Mock(text=DOC)
        response.raise_for_status = Mock()
        with patch("generate_dashboard.requests.get", return_value=response):
            criteria = fetch_eligibility_criteria(today=BEFORE)

        assert criteria["is_fallback"] is False
        assert [item["label"] for item in criteria["items"]] == ["Days Online", "Daily Query", "Query Quality"]
        assert criteria["upcoming"][0]["changes"] == {"MIN_SUBGRAPHS": 5}

    def test_fetch_failure_announces_nothing(self):
        with patch("generate_dashboard.requests.get", side_effect=OSError("offline")):
            criteria = fetch_eligibility_criteria(today=BEFORE)

        assert criteria["is_fallback"] is True
        assert criteria["upcoming"] == []
