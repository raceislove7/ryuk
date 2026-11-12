export interface SourceSpan { start: number; end: number; quote: string }
export function highlightedSourceParts(query: string, sources: SourceSpan[] = []) {
  const points = Array.from(query);
  const spans = sources.filter((s) => Number.isInteger(s.start) && Number.isInteger(s.end)
    && s.start >= 0 && s.end <= points.length && s.end > s.start
    && points.slice(s.start, s.end).join("") === s.quote)
    .map(({ start, end }) => ({ start, end })).sort((a, b) => a.start - b.start);
  const merged: { start: number; end: number }[] = [];
  for (const span of spans) {
    const previous = merged.at(-1);
    if (previous && span.start <= previous.end) previous.end = Math.max(previous.end, span.end);
    else merged.push({ ...span });
  }
  const parts: { text: string; highlighted: boolean }[] = [];
  let cursor = 0;
  for (const span of merged) {
    if (cursor < span.start) parts.push({ text: points.slice(cursor, span.start).join(""), highlighted: false });
    parts.push({ text: points.slice(span.start, span.end).join(""), highlighted: true });
    cursor = span.end;
  }
  if (cursor < points.length) parts.push({ text: points.slice(cursor).join(""), highlighted: false });
  return parts;
}
