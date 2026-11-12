import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { highlightedSourceParts } from "../lib/intent-sources.ts";
import { budgetRows, reasonSentence, reasonSentences } from "../lib/presentation.ts";

// Read the actual enum without importing backend code or environment configuration.
const source = readFileSync(new URL("../../backend/app/schemas/domain.py", import.meta.url), "utf8");
const declaration = source.split("class PolicyReasonCode(StrEnum):")[1].split("\n\nclass ")[0];
const codes = [...declaration.matchAll(/^    ([A-Z_]+) = "[A-Z_]+"$/gm)].map((match) => match[1]);
test("mapping matches the complete backend reason enum", () => {
  assert(codes.length > 0);
  assert.deepEqual(Object.keys(reasonSentences).sort(), [...codes].sort());
});
for (const code of codes) test(`${code} has an explanation without changing the code`, () => {
  assert.equal(typeof reasonSentence(code), "string");
  assert(reasonSentence(code).length > 30);
  assert.equal(reasonSentences[code], reasonSentence(code));
});
test("unknown and prototype-like codes use the safe fallback", () => {
  for (const code of ["FUTURE_REASON", "__proto__", "toString", ""])
    assert.equal(reasonSentence(code), "The backend supplied an additional condition. Keep the decision unchanged and inspect this code.");
});
const budget = { currency: "USD", limit_minor: 150000, settled_minor: 0, reserved_minor: 0, available_minor: 150000 };
test("zero budget has finite empty bars", () => {
  const rows = budgetRows({ ...budget, limit_minor: 0, available_minor: 0 });
  assert.deepEqual(rows.map((row) => row.value), [0, 0, 0]);
  assert(rows.every((row) => row.maximum > 0 && row.progress === 0));
});
test("exhausted budget preserves settled and held values with zero available", () => {
  const rows = budgetRows({ ...budget, settled_minor: 120000, reserved_minor: 30000, available_minor: 0 });
  assert.deepEqual(rows.map((row) => row.value), [120000, 30000, 0]);
  assert.equal(rows[2].progress, 0);
});
test("available is the supplied backend value, never inferred from other amounts", () => {
  const original = { ...budget, available_minor: 12345 };
  const before = structuredClone(original);
  assert.equal(budgetRows(original)[2].value, 12345);
  assert.deepEqual(original, before);
});
test("overcommitment only clamps the illustration, never the label", () => {
  const rows = budgetRows({ ...budget, settled_minor: 160000, available_minor: 0 });
  assert.equal(rows[0].value, 160000);
  assert.equal(rows[0].progress, 150000);
});

test("source highlight spans preserve Unicode code-point offsets", () => {
  const parts = highlightedSourceParts("🏔 Gym required", [{ start: 2, end: 14, quote: "Gym required" }]);
  assert.deepEqual(parts, [{ text: "🏔 ", highlighted: false }, { text: "Gym required", highlighted: true }]);
});
test("overlapping/grouped quotes preserve original text without duplicate content", () => {
  const parts = highlightedSourceParts("Gym and pool", [
    { start: 0, end: 12, quote: "Gym and pool" }, { start: 0, end: 3, quote: "Gym" },
    { start: 0, end: 12, quote: "Gym and pool" },
  ]);
  assert.deepEqual(parts, [{ text: "Gym and pool", highlighted: true }]);
});
test("legacy/malformed spans never create inferred highlights", () => {
  for (const sources of [undefined, [{ start: 0, end: 3, quote: "Fake" }]])
    assert.deepEqual(highlightedSourceParts("Gym", sources), [{ text: "Gym", highlighted: false }]);
});
