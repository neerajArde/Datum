// lib/highlight.ts
// Finds where a value sits inside its quote, so we can highlight it.
// Shared by the evidence card and the review panel.

// "exhibits a µC* of 47 ± 6"  ->  ["exhibits a µC* of ", "47", " ± 6"].
// Returns null if the value isn't in the quote.
export function splitAtValue(quote: string, value: string): [string, string, string] | null {
  if (value === "") return null;
  // escape characters like "." and "*" so they're matched literally
  const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // match the value as a whole number: "47" must not match inside "147" or "4.7"
  const match = new RegExp(`(?<![\\d.])${escaped}(?!\\d)`).exec(quote);
  if (match === null) return null;
  const start = match.index;
  const end = start + value.length;
  return [quote.slice(0, start), quote.slice(start, end), quote.slice(end)];
}
