"""
Unit tests for reading the eligibility metrics subgraph into data.json.
"""

import json
import os
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import generate_dashboard
from generate_dashboard import fetch_indexer_metrics, write_dashboard_data

A = "0x00000000000000000000000000000000000000aa"
B = "0x00000000000000000000000000000000000000bb"

STATE = {
    "oracleState": {
        "windowStartDay": 20703,
        "windowEndDay": 20731,
        "criteria": {"minOnlineDays": "5", "minSubgraphs": "1", "maxLatencyMs": "5000", "maxBlocksBehind": "50000"},
        "latestRun": {
            "date": "2026-10-05",
            "runDay": 20731,
            "transactionHash": "0xabc",
            "blockNumber": "512398114",
            "blockTimestamp": "1791194400",
        },
    }
}

DAYS = {"days": [
    {"dayNumber": 20731, "isFinal": False},
    {"dayNumber": 20730, "isFinal": True},
]}


def _row(address, day, date, attempts):
    return {
        "id": f"{address}-{date}",
        "dayNumber": day,
        "queryAttempts": str(attempts),
        "qualifyingQueries": str(attempts - 1),
        "qualifyingSubgraphs": "6",
        "failedStatus": "1",
        "failedLatency": "0",
        "failedBlocksBehind": "1",
    }


ROWS = [
    _row(A, 20731, "2026-10-05", 40),
    _row(A, 20730, "2026-10-04", 90),
    _row(B, 20730, "2026-10-04", 7),
]


def _gateway(pages):
    """A fake gateway that answers by query shape, serving indexerDays in pages."""
    served = iter(pages)

    def post(url, json, timeout):
        query = json["query"]
        if "oracleState" in query:
            data = STATE
        elif "indexerDays" in query:
            data = {"indexerDays": next(served)}
        else:
            data = DAYS
        response = Mock()
        response.raise_for_status = Mock()
        response.json = Mock(return_value={"data": data})
        return response

    return post


class TestFetchIndexerMetrics:
    def test_reads_window_days_and_rows(self):
        with patch.object(generate_dashboard, "_METRICS_PAGE_SIZE", 2), \
                patch("generate_dashboard.requests.post", side_effect=_gateway([ROWS[:2], ROWS[2:]])):
            metrics = fetch_indexer_metrics("key")

        assert metrics["run_date"] == "2026-10-05"
        assert metrics["run_block"] == 512398114
        assert metrics["window_start_day"] == 20703
        assert metrics["criteria"] == {
            "min_online_days": 5, "min_subgraphs": 1, "max_latency_ms": 5000, "max_blocks_behind": 50000,
        }
        assert metrics["published_days"] == [20730, 20731]
        assert metrics["partial_days"] == [20731]
        # Pagination followed the cursor; rows are sorted oldest first.
        assert metrics["indexers"] == {
            A: [[20730, 90, 89, 6, 1, 0, 1], [20731, 40, 39, 6, 1, 0, 1]],
            B: [[20730, 7, 6, 6, 1, 0, 1]],
        }
        assert metrics["columns"][0] == "day"

    def test_gateway_error_degrades_to_none(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json = Mock(return_value={"errors": [{"message": "subgraph not found: no allocations"}]})
        with patch("generate_dashboard.requests.post", return_value=response):
            assert fetch_indexer_metrics("key") is None

    def test_network_failure_degrades_to_none(self):
        with patch("generate_dashboard.requests.post", side_effect=OSError("offline")):
            assert fetch_indexer_metrics("key") is None

    def test_no_oracle_state_yet(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json = Mock(return_value={"data": {"oracleState": None}})
        with patch("generate_dashboard.requests.post", return_value=response):
            assert fetch_indexer_metrics("key") is None


class TestWriteDashboardData:
    def test_metrics_attach_to_arbitrum_one_only(self, tmp_path):
        environments = {
            "mainnet": {"config": {"name": "Arbitrum One", "network_id": 42161}, "indexers": []},
            "testnet": {"config": {"name": "Arbitrum Sepolia", "network_id": 421614}, "indexers": []},
        }
        criteria = {"items": [], "upcoming": [], "source_url": "", "is_fallback": False}
        with patch("generate_dashboard.fetch_eligibility_criteria", return_value=criteria):
            path = write_dashboard_data(environments, str(tmp_path), metrics={"run_date": "2026-10-05"})

        written = {e["id"]: e for e in json.load(open(path))["environments"]}
        assert written["mainnet"]["metrics"] == {"run_date": "2026-10-05"}
        assert written["testnet"]["metrics"] is None
