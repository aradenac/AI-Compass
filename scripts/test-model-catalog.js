#!/usr/bin/env node
"use strict";
/* PLAT-05: executable client contract, DOM-card and no-Demo-fallback smoke.
 * No new npm dependencies: node:assert + node:vm only. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

async function main() {
  const requests = [];
  let remoteRows = [];
  const revisions = {};
  let inaccessible = false;
  let networkDown = false;

  function row(id, name, number, properties) {
    return {id, uuid: "test-uuid", name, type: "model", revision: "r" + String(number).padStart(3, "0"),
      schema_version: 2, compatibility: {status: "current", read_only: false, source_schema_version: 2, current_schema_version: 2}, properties, created_at: "2026-10-09T00:00:00+00:00", created_by: "contributor"};
  }
  const fetch = async (url, options) => {
    requests.push({url, options});
    if (networkDown) throw Error("network down");
    if (inaccessible) return {ok: false, status: 403, json: async () => ({error: "forbidden"})};
    const method = options.method || "GET";
    const path = url.replace("/api/v1/models", "");
    const body = method === "POST" ? JSON.parse(options.body) : null;
    if (path === "" && method === "GET")
      return {ok: true, status: 200, json: async () => ({results: remoteRows})};
    if (path === "" && method === "POST") {
      const created = row("mdl-blue-quiet-fox", body.name, 1, body.properties);
      remoteRows.push(created); revisions[created.id] = [created];
      return {ok: true, status: 201, json: async () => created};
    }
    const id = path.split("/")[1], current = remoteRows.find(x => x.id === id);
    if (path.endsWith("/revisions") && method === "GET")
      return {ok: true, status: 200, json: async () => ({id, revisions: revisions[id]})};
    if (path.endsWith("/revisions") && method === "POST") {
      if (body.expected_revision !== current.revision)
        return {ok: false, status: 409, json: async () => ({error: "revision_conflict", detail: "stale"})};
      const updated = row(id, body.name, revisions[id].length + 1, body.properties);
      remoteRows[remoteRows.indexOf(current)] = updated;
      revisions[id].push(updated);
      return {ok: true, status: 201, json: async () => updated};
    }
    if (current && path === "/" + id)
      return {ok: true, status: 200, json: async () => current};
    return {ok: false, status: 404, json: async () => ({error: "not_found"})};
  };
  const sandbox = {window: {fetch}, console};
  vm.runInNewContext(fs.readFileSync("model-catalog.js", "utf8"), sandbox, {filename: "model-catalog.js"});
  const library = sandbox.window.AICompassModels;
  assert(library && library.LocalStorageDataProvider && library.ApiDataProvider && library.renderLane);

  let local = [{id: "demo-1", type: "model", name: "Fake Demo model"}];
  const demo = library.LocalStorageDataProvider({
    list: () => local.filter(x => x.type === "model"),
    get: id => local.find(x => x.id === id),
    create: m => { local.push(m); return m; },
    revise: (id, m) => Object.assign(local.find(x => x.id === id), m)
  });
  assert.equal(demo.list()[0].name, "Fake Demo model");
  demo.create({id: "demo-2", type: "model", name: "Another fake"});
  demo.revise("demo-2", {name: "Updated fake"});
  assert.equal(demo.get("demo-2").name, "Updated fake");
  assert.equal(remoteRows.length, 0, "Demo data must not invoke the Server");

  const api = library.ApiDataProvider(() => "csrf-rotated");
  assert.equal((await api.list()).length, 0, "Fresh Server must be empty");
  const created = await api.create({
    name: "Real <Model>",
    properties: {context_window: 32000, custom: {nested: true}, details: "<img src=x onerror=alert(1)>"}
  });
  assert.equal(created.id, "mdl-blue-quiet-fox");
  assert.equal(created.revision, "r001");
  assert.equal(created.properties.custom.nested, true);
  assert.equal((await api.list()).length, 1);
  assert.equal((await api.get(created.id)).name, created.name);
  assert.equal(requests.find(x => x.options.method === "POST").options.headers["X-CSRFToken"], "csrf-rotated");
  assert(requests.every(x => x.options.credentials === "same-origin"));
  assert(requests.every(x => x.url.startsWith("/api/v1/models")));

  const second = await api.revise(created.id, {
    expected_revision: created.revision,
    name: "Real Model corrected",
    properties: Object.assign({}, created.properties, {context_window: 64000})
  });
  assert.equal(second.revision, "r002");
  assert.equal(second.properties.custom.nested, true, "Unknown JSON properties preserved");
  const history = await api.revisions(created.id);
  assert.deepEqual(Array.from(history, x => x.revision), ["r001", "r002"]);
  assert.equal(history[0].properties.context_window, 32000);
  assert.equal(history[1].properties.context_window, 64000);
  await assert.rejects(api.revise(created.id, {expected_revision: "r001", name: "stale", properties: {}}),
    e => e.status === 409 && e.code === "revision_conflict");

  const card = library.renderLane([{...second, details: '<img src=x onerror=alert(1)>', testedCount: 0}],
    {canWrite: true, showRevisions: true});
  assert(card.includes("data-act=\"editComponent\""));
  assert(card.includes("data-act=\"modelHistory\""));
  assert(card.includes("r002"));
  assert(card.includes("&lt;img"));
  assert(!card.includes("<img"));
  assert(!card.includes("Fake Demo model"));
  // Older objects and unsupported/invalid records are still readable.
  // Never silently insert defaults or expose unsafe edit controls.
  const legacyRaw = row("mdl-old-quiet-tree", "Historic", 1, {
    release_channel: "unknown <script>", context_window: 4096,
    extra: null
  });
  legacyRaw.schema_version = 1;
  legacyRaw.compatibility = {
    status: "needs_review", read_only: true, source_schema_version: 1,
    current_schema_version: 2, null_fields: ["extra"],
    missing_fields: ["supports_tools"], unknown_fields: ["extra"],
    incompatible_fields: ["release_channel"], reason: "Manual review required"
  };
  const oldModel = library.modelFromApi(legacyRaw);
  assert.equal(oldModel.readOnly, true);
  assert.equal(oldModel.schema_version, 1);
  assert.equal(oldModel.properties.release_channel, "unknown <script>");
  const oldCard = library.renderLane([oldModel], {canWrite: true, showRevisions: true});
  assert(oldCard.includes("needs_review"));
  assert(oldCard.includes("Missing: supports_tools"));
  assert(oldCard.includes("Null: extra"));
  assert(oldCard.includes("Incompatible: release_channel"));
  assert(oldCard.includes('data-act="modelRaw"'));
  assert(oldCard.includes('data-act="modelHistory"'));
  assert(!oldCard.includes('data-act="editComponent"'));
  assert(!oldCard.includes("<script>"));
  const unsupported = library.modelFromApi({
    id: "other-unknown-002", type: "futuretype", name: "Unknown",
    revision: "r001", schema_version: 99,
    properties: [1, null, {raw: true}],
    compatibility: {status: "unsupported", read_only: true}
  });
  assert.equal(unsupported.properties.length, 3);
  assert(unsupported.readOnly);
  assert(!library.renderLane([unsupported], {canWrite: true, showRevisions: true})
    .includes('data-act="editComponent"'));
  const noRevision = library.modelFromApi({
    id: "other-missing-003", type: "futuretype", name: null,
    revision: null, schema_version: null, properties: null,
    compatibility: {status: "unsupported", read_only: true}
  });
  assert.equal(noRevision.name, "");
  assert.equal(noRevision.properties, null);
  assert(library.renderLane([noRevision], {canWrite: false, showRevisions: true})
    .includes("Original data"));
  assert(serverModeSourceSupportsRawInspector());

  function serverModeSourceSupportsRawInspector() {
    const source = fs.readFileSync("server-mode.js", "utf8");
    return source.includes("server-inspect-catalog-form") &&
      source.includes("/api/v1/catalog/items/") &&
      source.includes("Original catalog data") &&
      source.includes("if (item && item.readOnly)") &&
      !source.includes("localStorage");
  }

  const empty = library.renderLane([], {canWrite: true});
  assert(empty.includes("No Models yet"));
  const viewer = library.renderLane([second], {canWrite: false, showRevisions: true});
  assert(!viewer.includes('data-act="editComponent"'));

  inaccessible = true;
  await assert.rejects(api.create({name: "Not allowed", properties: {}}), e => e.status === 403);
  inaccessible = false;
  networkDown = true;
  await assert.rejects(api.list(), /No Demo fallback/);
  assert.equal(local.length, 2, "Server failures must never overwrite local Demo");
  assert.equal(remoteRows.length, 1, "Server failures must not introduce sample rows");

  const proto = fs.readFileSync("prototype.html", "utf8");
  const server = fs.readFileSync("server-mode.js", "utf8");
  assert(proto.includes('<script src="model-catalog.js"></script>'));
  assert(proto.includes("demoCatalogProviders[type].list()"));
  assert(proto.includes("window.AICompassModels.renderLane"));
  assert(server.includes("modelsUi.renderLane"));
  assert(server.includes("modelsUi.ApiDataProvider"));
  assert(!/\blocalStorage\b/.test(server), "Server code must not read Demo localStorage");
  assert(server.includes("expected_revision"));
  assert(server.includes("server-model-history"));
  const inline = proto.match(/<script>\s*([\s\S]*?)<\/script>/);
  assert(inline, "Missing inline Demo code");
  new vm.Script(inline[1], {filename: "prototype.html inline demo JS"});
  new vm.Script(server, {filename: "server-mode.js"});
  console.log("PLAT-05 client providers, shared Model UI, revision history, conflict, RBAC and isolation: PASS");
}
main().catch(error => { console.error(error); process.exitCode = 1; });
