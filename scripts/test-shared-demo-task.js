#!/usr/bin/env node
"use strict";
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const html = fs.readFileSync("prototype.html", "utf8");

/* UX-R04 #123 / TD-01: the Demo Tasks page renders through the single shared
   mount. The legacy second `return` (an unreachable organizer over the dead
   treeHtml/taskOrganizerPage surface) has been removed and must not resurface
   as duplicated detail DOM. */
assert.equal((html.match(/return heading\("Explore","Engineering task hierarchy"/g) || []).length, 1,
  "prototype.html must keep exactly one Explore task-heading return");
assert.equal((html.match(/id="shared-demo-tasks"/g) || []).length, 1,
  "prototype.html must mount the shared Demo task surface exactly once");
assert(!html.includes("An evolving, arbitrary-depth tree."),
  "The unreachable legacy task-taxonomy return must stay removed");
/* UX-R04 #123 bead ai-w3x.4: the orphaned Demo organizer surface (inline task
   forms, drag-and-drop handlers, root/add/reorder dispatcher branches, organizer
   CSS and their ui-state) is fully dead now that tasksPage() renders only the
   shared server-tasks.js mount. It was deleted and must not resurface. */
for (const dead of ["taskOrganizerPage", "taskOrganizerNode", "taskOrganizerReorder",
  "taskDropZone", "taskDropTarget", "resetTaskDropStyle", "inlineTaskFields",
  "saveInlineTask", "dropTaskOn", "moveTaskNode", "isValidTaskMove", "treeHtml",
  "data-task-drag", "inline-task-form", "ui.taskView", "ui.draggedTask"]) {
  assert(!html.includes(dead), "orphaned organizer surface must stay removed: " + dead);
}

const start = html.indexOf("function demoTaskVersion(id){");
const end = html.indexOf("if(!localStorage.getItem(KEY))persist();", start);
assert(start > 0 && end > start, "Shared Demo provider must be defined before persistence bootstrap");
const domainCode = html.slice(start, end);
new vm.Script(domainCode);
let nextId = 1, saves = 0, writable = true;
const db = {tasks: [{id: "t1", name: "Original", parent: null, order: 0,
  baseline: 30, phase: "SWE", criteria: "Original DoD"}], revisions: []};
const catalog = {};
for (const type of ["model", "provider", "harness", "framework"]) {
  catalog[type] = {list: () => [], create: () => ({id: type + "1", type}),
    revise: () => ({}), revisions: () => []};
}
const context = {
  db, demoCatalogProviders: catalog, window: {AICompassRuntime: {
    createProviders: (mode, local) => {assert.equal(mode, "demo"); return {data: local};}
  }, AICompassEnvironment: {
    // FUT-06's Demo environment adapter is outside the Task provider's scope.
    demoProvider: () => ({})
  }},
  canEdit: () => writable, next: () => "t" + (++nextId),
  revision: (type, id, before, after) => db.revisions.push({
    type, objectId: id,
    before: JSON.parse(JSON.stringify(before)), after: JSON.parse(JSON.stringify(after))
  }),
  persist: () => {saves += 1;}, console, Set, Object, JSON
};
vm.runInNewContext(domainCode, context, {filename: "demo-task-provider.js"});
const provider = context.demoDomain.tasks;
(async () => {
  let rows = await provider.request("");
  assert.equal(rows.results.length, 1);
  assert.equal(rows.results[0].revision, "r001");
  let created = await provider.request("", "POST", {name: "Child", parent_id: "t1",
    properties: {phase: "SWE", domain: "Embedded", criteria: "Covered", unknown: null}});
  assert.equal(created.revision, "r001");
  assert.equal(created.parent_id, "t1");
  assert.equal(created.properties.unknown, null);
  assert.equal(saves, 1);
  const before = JSON.stringify(db);
  await assert.rejects(provider.request("/" + created.id, "PATCH", {
    expected_revision: "r000", name: "Bad"
  }), e => e.status === 409);
  assert.equal(JSON.stringify(db), before, "Optimistic conflict must not mutate the Demo");
  let updated = await provider.request("/" + created.id, "PATCH", {
    expected_revision: "r001", name: "Updated",
    properties: {phase: "SWE", domain: "Embedded", criteria: "Covered", unknown: null}
  });
  assert.equal(updated.task.revision, "r002");
  assert.equal(updated.task.properties.unknown, null);
  const revs = await provider.request("/" + created.id + "/revisions");
  assert.equal(revs.revisions.length, 2);
  assert.equal(revs.revisions[0].name, "Child", "Creation snapshot must remain immutable");
  assert.equal(revs.revisions[1].name, "Updated");
  const v = JSON.stringify(db);
  await assert.rejects(provider.request("/" + created.id, "PATCH", {
    expected_revision: "r002", parent_id: "t1", before: "not-an-existing-sibling",
    name: "Unsafe"
  }), /Invalid sibling/);
  assert.equal(JSON.stringify(db), v, "Invalid move must be atomic (no premature name change)");
  await assert.rejects(provider.request("/t1", "PATCH", {
    expected_revision: "r001", parent_id: created.id
  }), /own ancestor/);
  assert.equal(JSON.stringify(db), v);
  await assert.rejects(provider.request("", "POST", {
    name: "Unsafe", properties: {id: "override"}
  }), /Protected Task fields/);
  writable = false;
  await assert.rejects(provider.request("/" + created.id, "PATCH", {
    name: "Unauthorized", expected_revision: "r002"
  }), /no write permission/);
  assert.equal(JSON.stringify(db), v, "Denied write cannot alter fictional data");
  console.log("FUT-03 offline Demo Task create, revision, concurrency, rollback and role security: PASS");
})().catch(err => {console.error(err); process.exitCode = 1;});
