import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = readFileSync(new URL("../src/multivalue.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const module = { exports: {} };
vm.runInNewContext(compiled, { exports: module.exports, module });
const { formatMultivalueText, parseMultivalueText } = module.exports;

assert.deepEqual(
  Array.from(parseMultivalueText("Principal Product Manager\r\nDirector of Product\nVP Product\rProduct Lead")),
  ["Principal Product Manager", "Director of Product", "VP Product", "Product Lead"],
);
assert.deepEqual(Array.from(parseMultivalueText("Raleigh, NC\r\nWashington, DC")), [
  "Raleigh, NC",
  "Washington, DC",
]);
assert.deepEqual(Array.from(parseMultivalueText(" Remote \nRemote\n")), ["Remote"]);
assert.equal(formatMultivalueText(["Raleigh, NC", "Remote"]), "Raleigh, NC\nRemote");

console.log("Multi-value parsing checks passed.");
