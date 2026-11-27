from dataclasses import dataclass

from limo.llm.ports import LlmUsage

MICROS = 1_000_000


@dataclass(frozen=True)
class PriceMicros:
    """USD micro-dollars per million tokens."""

    input: int
    output: int
    cache_read: int
    cache_write: int


def to_micros(usd: float) -> int:
    return round(usd * MICROS)


def format_usd(micros: int) -> str:
    return f"{micros // MICROS}.{micros % MICROS:06d}"


def cost_micros(usage: LlmUsage, price: PriceMicros | None) -> int:
    if price is None:
        return 0
    total = (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_read_tokens * price.cache_read
        + usage.cache_write_tokens * price.cache_write
    )
    return (total + MICROS // 2) // MICROS
