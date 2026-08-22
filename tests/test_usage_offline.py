import csv

import pytest

from ai_engine.usage import (
    UsageRecord,
    format_usage_summary,
    get_usage_totals,
    log_usage,
    usage_difference,
)


ZERO_TOTALS = {
    "requests": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "thought_tokens": 0,
    "cached_tokens": 0,
    "total_tokens": 0,
}


def test_usage_record_defaults_optional_counters_to_zero():
    record = UsageRecord(provider="openai", model="test-model")

    assert record.input_tokens == 0
    assert record.output_tokens == 0
    assert record.thought_tokens == 0
    assert record.cached_tokens == 0
    assert record.total_tokens == 0
    assert record.timestamp is None


def test_log_usage_creates_csv_with_header_and_record(tmp_path):
    usage_file = tmp_path / "nested" / "api_usage.csv"
    record = UsageRecord(
        provider="gemini",
        model="gemini-test",
        input_tokens=10,
        output_tokens=5,
        thought_tokens=2,
        cached_tokens=3,
        total_tokens=17,
        timestamp="2026-08-22T10:00:00",
    )

    result = log_usage(record, usage_file=usage_file)

    assert result == usage_file
    with usage_file.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))

    assert rows == [
        [
            "timestamp",
            "provider",
            "model",
            "input_tokens",
            "output_tokens",
            "thought_tokens",
            "cached_tokens",
            "total_tokens",
        ],
        [
            "2026-08-22T10:00:00",
            "gemini",
            "gemini-test",
            "10",
            "5",
            "2",
            "3",
            "17",
        ],
    ]


def test_log_usage_appends_multiple_providers_and_totals_them(tmp_path):
    usage_file = tmp_path / "api_usage.csv"
    records = [
        UsageRecord(
            provider="openai",
            model="openai-test",
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
            timestamp="2026-08-22T10:00:00",
        ),
        UsageRecord(
            provider="anthropic",
            model="claude-test",
            input_tokens=20,
            output_tokens=6,
            thought_tokens=2,
            cached_tokens=5,
            total_tokens=28,
            timestamp="2026-08-22T10:01:00",
        ),
    ]

    for record in records:
        log_usage(record, usage_file=usage_file)

    with usage_file.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert [row["provider"] for row in rows] == ["openai", "anthropic"]
    assert get_usage_totals(usage_file) == {
        "requests": 2,
        "input_tokens": 30,
        "output_tokens": 10,
        "thought_tokens": 2,
        "cached_tokens": 5,
        "total_tokens": 42,
    }


def test_get_usage_totals_returns_zeros_for_missing_csv(tmp_path):
    assert get_usage_totals(tmp_path / "missing.csv") == ZERO_TOTALS


def test_usage_difference_subtracts_before_from_after():
    before = {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
    }
    after = {
        "requests": 3,
        "input_tokens": 35,
        "output_tokens": 12,
        "total_tokens": 47,
    }

    assert usage_difference(before, after) == {
        "requests": 2,
        "input_tokens": 25,
        "output_tokens": 7,
        "total_tokens": 32,
    }


@pytest.mark.parametrize(
    ("usage", "expected_lines", "unexpected_lines"),
    [
        (
            {
                "requests": 2,
                "input_tokens": 1000,
                "output_tokens": 200,
                "thought_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 1200,
            },
            [
                "Chamadas de API: 2",
                "Input tokens: 1,000",
                "Output tokens: 200",
                "Total registrado: 1,200 tokens",
            ],
            ["Thinking tokens:", "Cached tokens:"],
        ),
        (
            {
                "requests": 1,
                "input_tokens": 10,
                "output_tokens": 5,
                "thought_tokens": 3,
                "cached_tokens": 4,
                "total_tokens": 18,
            },
            [
                "Thinking tokens: 3",
                "Cached tokens: 4",
                "Total registrado: 18 tokens",
            ],
            [],
        ),
    ],
)
def test_format_usage_summary_includes_available_counters(
    usage,
    expected_lines,
    unexpected_lines,
):
    formatted = format_usage_summary(usage)

    assert formatted.startswith("===== CONSUMO REAL =====")
    for line in expected_lines:
        assert line in formatted
    for line in unexpected_lines:
        assert line not in formatted
