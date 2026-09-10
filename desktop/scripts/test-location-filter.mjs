import assert from "node:assert/strict";
import { countLocationScopes, matchesLocationFilter } from "../src/locationFilter.js";

const item = (scope) => ({ score: scope ? { location: { scope } } : null });
const items = [item("local"), item("regional"), item("distant"), item("unknown"), item(null)];

assert.deepEqual(countLocationScopes(items), {
  local: 1,
  regional: 1,
  distant: 1,
  unknown: 2,
});
assert.equal(matchesLocationFilter(items[0], "local_or_regional"), true);
assert.equal(matchesLocationFilter(items[1], "local_or_regional"), true);
assert.equal(matchesLocationFilter(items[2], "local_or_regional"), false);
assert.equal(matchesLocationFilter(items[2], "distant"), true);
assert.equal(matchesLocationFilter(items[4], "unknown"), true);
assert.equal(items.every((value) => matchesLocationFilter(value, "all")), true);

console.log("location filter regression passed");
