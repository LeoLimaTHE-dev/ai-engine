import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_USAGE_DIR = Path(r"C:\IA\6_Dados\usage")

DEFAULT_USAGE_FILE = DEFAULT_USAGE_DIR / "api_usage.csv"


@dataclass
class UsageRecord:
    provider: str
    model: str

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    thought_tokens: int = 0
    cached_tokens: int = 0

    timestamp: str | None = None


def log_usage(
    record: UsageRecord,
    usage_file: str | Path = DEFAULT_USAGE_FILE,
) -> Path:
    path = Path(usage_file)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    exists = path.exists()

    timestamp = record.timestamp or datetime.now().isoformat(timespec="seconds")

    with path.open(
        "a",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.writer(file)

        if not exists:
            writer.writerow(
                [
                    "timestamp",
                    "provider",
                    "model",
                    "input_tokens",
                    "output_tokens",
                    "thought_tokens",
                    "cached_tokens",
                    "total_tokens",
                ]
            )

        writer.writerow(
            [
                timestamp,
                record.provider,
                record.model,
                record.input_tokens,
                record.output_tokens,
                record.thought_tokens,
                record.cached_tokens,
                record.total_tokens,
            ]
        )

    return path


def get_usage_totals(
    usage_file: str | Path = DEFAULT_USAGE_FILE,
) -> dict[str, int]:
    path = Path(usage_file)

    totals = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "thought_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
    }

    if not path.exists():
        return totals

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            totals["requests"] += 1

            totals["input_tokens"] += int(
                row.get(
                    "input_tokens",
                    0,
                )
                or 0
            )

            totals["output_tokens"] += int(
                row.get(
                    "output_tokens",
                    0,
                )
                or 0
            )

            totals["thought_tokens"] += int(
                row.get(
                    "thought_tokens",
                    0,
                )
                or 0
            )

            totals["cached_tokens"] += int(
                row.get(
                    "cached_tokens",
                    0,
                )
                or 0
            )

            totals["total_tokens"] += int(
                row.get(
                    "total_tokens",
                    0,
                )
                or 0
            )

    return totals


def usage_difference(
    before: dict[str, int],
    after: dict[str, int],
) -> dict[str, int]:
    return {key: (after.get(key, 0) - before.get(key, 0)) for key in after}


def format_usage_summary(
    usage: dict[str, int],
) -> str:
    lines = [
        "===== CONSUMO REAL =====",
        (f"Chamadas de API: {usage['requests']:,}"),
        (f"Input tokens: {usage['input_tokens']:,}"),
        (f"Output tokens: {usage['output_tokens']:,}"),
    ]

    if usage["thought_tokens"]:
        lines.append(f"Thinking tokens: {usage['thought_tokens']:,}")

    if usage["cached_tokens"]:
        lines.append(f"Cached tokens: {usage['cached_tokens']:,}")

    lines.append(f"Total registrado: {usage['total_tokens']:,} tokens")

    return "\n".join(lines)
