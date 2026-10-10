#!/usr/bin/env node
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("server-mode.js", "utf8");
assert(source.includes('"/api/v1/contract"'), "Must negotiate before any Server account request");
assert(source.indexOf("await ensureReleaseCompatibility()") < source.indexOf('await authRequest("csrf")'), "Contract check must precede authentication");
const m = source.match(/function checkReleaseCompatibility\(doc\) \{([\s\S]*?)\n  \}/);
assert(m, "Pure contract validator should be testable");
const check = vm.runInNewContext("(function checkReleaseCompatibility(doc) {" + m[1] + "\n})", {});
const valid = {schema:"ai-compass/api-contract@1", api_major:1, supported_client_api_majors:[1], min_client_api_major:1, max_client_api_major:1};
assert.equal(check(valid), true);
assert.throws(() => check({schema:"ai-compass/api-contract@1",api_major:2,supported_client_api_majors:[2]}), /incompatible/i);
assert.throws(() => check({schema:"ai-compass/api-contract@1",api_major:1,supported_client_api_majors:[]}), /incompatible/i);
assert.throws(() => check({schema:"unknown",api_major:1,supported_client_api_majors:[1]}), /incompatible/i);
assert.throws(() => check(null), /incompatible/i);
assert(source.includes("Demo data will NOT be loaded automatically"), "Server mode never loads Demo fallback");
const proto = fs.readFileSync("prototype.html","utf8");
assert(proto.includes("server-mode.js"));
console.log("API contract positive/negative, negotiation order and no Demo fallback: PASS");
