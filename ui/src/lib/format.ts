/** "0.400000" → "$0.40" (API money is a 6-place decimal string). */
export function formatUsd(amount: string): string {
  return `$${Number(amount).toFixed(2)}`;
}

/** 52000 → "52,000 tokens". */
export function formatTokens(tokens: number): string {
  return `${tokens.toLocaleString("en-US")} tokens`;
}

/** 240 → "4 min", 45 → "45 s", null → "running". */
export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "running";
  if (seconds < 60) return `${seconds} s`;
  return `${Math.round(seconds / 60)} min`;
}

/** ISO-8601 UTC → "2026-11-26 14:05 UTC"; null → "—". */
export function formatTime(iso: string | null): string {
  if (iso === null) return "—";
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}
