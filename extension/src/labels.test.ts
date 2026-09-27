import assert from "node:assert/strict";
import { test } from "node:test";
import { headline, ordered, type QuickRisk } from "./labels.ts";

const risk = (labels: QuickRisk["labels"], level: QuickRisk["level"] = "high"): QuickRisk => ({ mint: "m", score: 80, level, labels });

test("a serial rugger leads, ahead of the generic high risk label", () => {
  const h = headline(
    risk([
      { kind: "high_risk", text: "High rug risk", severity: "danger" },
      { kind: "top_holders", text: "Top 10 hold 40%", severity: "warning" },
      { kind: "serial_rugger", text: "Dev rugged 5 coins", severity: "danger" },
    ]),
  );
  assert.deepEqual(h, { text: "Rugged 5", severity: "danger", more: 2 });
});

test("warnings alone are shown as warnings", () => {
  const h = headline(risk([{ kind: "top_holders", text: "Top 10 hold 22%", severity: "warning" }], "medium"));
  assert.deepEqual(h, { text: "Top 10: 22%", severity: "warning", more: 0 });
});

test("high risk on its own is still shown", () => {
  assert.equal(headline(risk([{ kind: "high_risk", text: "High rug risk", severity: "danger" }]))?.text, "High risk");
});

test("coins with no labels show nothing", () => {
  assert.equal(headline(risk([], "low")), null);
});

test("unknown label kinds sort last", () => {
  const kinds = ordered([
    { kind: "something_new", text: "x", severity: "warning" },
    { kind: "bundled", text: "Bundled 30%", severity: "warning" },
  ]).map((l) => l.kind);
  assert.deepEqual(kinds, ["bundled", "something_new"]);
});
