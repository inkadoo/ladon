import assert from "node:assert/strict";
import { test } from "node:test";
import { lookalikeOf, sharedEnds } from "./poison.ts";

const mine = "8qbHw2BbbTHBW1sbeqakYXVKRQM8Ne7pLK7m6CVfeR";
const poisoned = "8qbHx9KdZrT4mPq2LwYc3sVnB7uEhJ5aFgD1oCVfeR";

test("measures how many characters two addresses share at each end", () => {
  assert.deepEqual(sharedEnds(mine, poisoned), { start: 4, end: 5 });
  assert.deepEqual(sharedEnds("abc", "abc"), { start: 3, end: 0 });
});

test("flags a new address that copies the start and end of one you've used", () => {
  assert.equal(lookalikeOf(poisoned, [mine]), mine);
});

test("never flags an address you've already used", () => {
  assert.equal(lookalikeOf(mine, [poisoned, mine]), null);
});

test("ignores addresses that only share a few characters by chance", () => {
  assert.equal(lookalikeOf("8qbZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZfeR", [mine]), null);
  assert.equal(lookalikeOf("8qbHw2BbZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ", [mine]), null);
  assert.equal(lookalikeOf("ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZCVfeR", [mine]), null);
  assert.equal(lookalikeOf(poisoned, []), null);
});

test("picks the closest match when several look similar", () => {
  const closer = "8qbHx9KZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZCVfeR";
  assert.equal(lookalikeOf(poisoned, [mine, closer]), closer);
});
