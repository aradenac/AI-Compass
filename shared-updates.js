/* UX-R06: published-only Workgroup Updates / What's New.
 * A safe publication read surface over existing authorized objects. It is NOT a
 * second data store, an audit/activity feed, a personal queue or an assignment
 * list, and it never reveals drafts, internal hypotheses or private discussion.
 */
(function (root) {
  "use strict";
  function escape(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char];
    });
  }
  var KIND_LABELS = {
    measured_result: "Measured result",
    campaign_published: "Published campaign",
    recommendation_published: "Editorial Recommendation",
    guide_published: "Setup Guide",
    watch_published: "Technology Watch",
    technology_available: "New technology"
  };
  function safeLink(href) {
    var value = String(href || "");
    return value.startsWith("/") && !value.startsWith("//") ? value : "";
  }
  function sectionLabels() {
    return {"results":"Results Explorer","benchmark":"Benchmark Workspace",
      "recommendations":"Recommendations","guides":"Guides & Charter",
      "watch":"Technology Watch","catalog":"Technology Catalog"};
  }
  function present(payload, options) {
    options = options || {};
    if (!payload || !Array.isArray(payload.items))
      throw Error("Published updates payload required");
    if (payload.scope !== "published_only")
      throw Error("Only the published-only scope may be presented");
    var mode = options.mode;
    var workspace = typeof options.workspace === "function" ?
      options.workspace() : (options.workspace || "workgroup");
    if (!["demo", "server"].includes(mode)) throw Error("Explicit Demo or Server mode required");
    var route = options.route;
    if (typeof route !== "function") throw Error("Authorized route builder required");
    var sections = Array.isArray(options.sections) ? options.sections : null;
    var labels = sectionLabels();
    function sourceLink(item) {
      var source = item.source || {};
      var origin = (labels[source.section] || source.section || "Workspace") + " · " +
        (source.object_id || "unavailable") + (source.revision ? " · " + source.revision : "");
      if (sections && sections.indexOf(source.section) === -1)
        return '<p class="shared-updates-source" data-updates-source-denied>"' +
          escape(origin) + '" — the ' + escape(labels[source.section] || source.section) +
          ' workspace is not available to this account. The published summary stays readable ' +
          'and no other section is substituted.</p>';
      var href = safeLink(route(mode, workspace, source.section, {
        record: source.object_id, revision: source.revision}));
      if (!href)
        return '<p class="shared-updates-source">Source: ' + escape(origin) +
          ' (no authorized route is offered for this account)</p>';
      return '<p class="shared-updates-source">Source: <a href="' + escape(href) + '">' +
        escape(origin + " — open the exact authorized record") + '</a></p>';
    }
    function item(entry) {
      return '<article class="shared-updates-item" data-updates-kind="' +
        escape(entry.kind) + '" data-updates-id="' + escape((entry.source || {}).object_id) + '">' +
        '<span class="shared-updates-kind">' +
        escape(KIND_LABELS[entry.kind] || entry.kind) + '</span>' +
        '<h4>' + escape(entry.title || "Untitled") + '</h4>' +
        '<p>' + escape(entry.summary || "") + '</p>' +
        (entry.notice ? '<p class="muted small">' + escape(entry.notice) + '</p>' : "") +
        '<p class="muted small">' + escape(entry.published_at || "date unknown") +
        ' · source timestamp: ' + escape(String(entry.timestamp_basis || "not stated")
          .replaceAll("_", " ")) + '</p>' +
        sourceLink(entry) + '</article>';
    }
    var counts = payload.counts || {};
    var withheld = payload.excluded || {};
    var order = ["measured_result", "campaign_published", "recommendation_published",
      "guide_published", "watch_published", "technology_available"];
    function group(kind) {
      var rows = payload.items.filter(function (entry) { return entry.kind === kind; });
      if (!rows.length) return "";
      return '<section class="shared-updates-group" data-updates-group="' + escape(kind) + '">' +
        '<h3>' + escape((KIND_LABELS[kind] || kind) + " (" + rows.length + ")") + '</h3>' +
        rows.map(item).join("") + '</section>';
    }
    var grouped = order.map(group).join("");
    var other = payload.items.filter(function (entry) {
      return order.indexOf(entry.kind) === -1; });
    return '<section class="shared-updates" data-shared-updates="' + escape(mode) +
      '" aria-labelledby="shared-updates-title">' +
      '<div class="shared-updates-intro"><h2 id="shared-updates-title">Workgroup Updates · What\'s New</h2>' +
      '<p>Globally published platform knowledge, derived from the current effective published ' +
      'sources. This is general published knowledge, not a personal queue and not a ' +
      'privileged Activity Feed or audit log.</p>' +
      '<p class="muted small">Basis: ' + escape(payload.generated_from || "published sources") +
      ' · ' + escape(mode === "demo" ? "fictional Demo records" : "real authenticated Server records") +
      ' · no cross-mode data.</p></div>' +
      (payload.items.length ?
        '<ul class="shared-updates-counts">' + Object.keys(counts).sort().map(function (kind) {
          return '<li>' + escape((KIND_LABELS[kind] || kind) + ": " + counts[kind]) + '</li>';
        }).join("") + '</ul>' + grouped + other.map(item).join("") :
        '<p data-updates-empty>No published knowledge yet. Drafts and internal material ' +
        'are deliberately not shown here.</p>') +
      (payload.notes || []).map(function (note) {
        return '<p class="muted small">' + escape(note) + '</p>';
      }).join("") +
      '<details class="shared-updates-withheld"><summary>What this published view excludes</summary>' +
      '<dl>' + Object.keys(withheld).sort().map(function (key) {
        return '<dt>' + escape(key.replaceAll("_", " ")) + '</dt><dd>' +
          escape(String(withheld[key])) + '</dd>';
      }).join("") + '</dl></details></section>';
  }
  function serverProvider(fetcher, csrf) {
    var request = root.AICompassRuntime.ServerTransport(fetcher, csrf).request;
    return {load: function () { return request("/api/v1/updates", "GET"); }};
  }
  function serverSections(persona, grants) {
    /* Sections whose source links this persona may actually open. A published
     * summary that points at a workspace the account cannot reach is shown as a
     * non-link provenance line instead of an unreachable deep link. */
    grants = grants || [];
    if (persona === "workgroup" && grants.indexOf("business_write") !== -1) {
      var group = root.AICompassWorkgroup;
      return group ? Object.keys(group.SECTION_TO_SERVER) :
        ["results", "benchmark", "recommendations", "guides", "watch", "catalog"];
    }
    if (persona === "engineer") {
      return ["results", "guides", "watch", "catalog", "tasks", "engineer", "environment"];
    }
    return [];
  }
  function demoProvider(db) {
    /* Fictional offline Demo derivation; mirrors the Server publication states
     * without contacting any API and without importing Server records. */
    if (!db) throw Error("Fictional Demo data required");
    function taskName(caseId) {
      var row = (db.cases || []).find(function (c) { return c.id === caseId; });
      var parent = row && (db.tasks || []).find(function (t) { return t.id === row.task; });
      return parent ? parent.name : (row ? row.task : "Unknown Task");
    }
    function solutionName(id) {
      var row = (db.solutions || []).find(function (s) { return s.id === id; });
      return row ? row.name : id;
    }
    function build() {
      var items = [];
      (db.runs || []).filter(function (run) {
        return run.status === "published" && !run.withdrawn;
      }).slice().sort(function (a, b) {
        return String(b.date || "").localeCompare(String(a.date || ""));
      }).slice(0, 12).forEach(function (run) {
        var accepted = !!run.accepted;
        items.push({
          kind: "measured_result",
          title: (run.frameworkAggregate ? "Composite workflow " + run.framework :
            solutionName(run.solution)) + " on " + taskName(run.case),
          summary: accepted ? "Outcome: accepted Definition of Done." :
            "Outcome: failed Definition of Done (negative evidence).",
          notice: accepted ? "Measured fictional Demo evidence under its recorded method." :
            "A published failed-DoD Run is recorded negative evidence; it is never an endorsement.",
          published_at: run.date || "date unknown",
          timestamp_basis: "run_recorded_at",
          source: {object_id: run.id, revision: run.revision || "r001", section: "results"}
        });
      });
      (db.campaigns || []).filter(function (campaign) {
        return !campaign.archived && campaign.stage === "published";
      }).forEach(function (campaign) {
        items.push({
          kind: "campaign_published",
          title: campaign.title,
          summary: "Reviewed publication with " +
            (db.runs || []).filter(function (run) { return run.campaignId === campaign.id; })
              .length + " recorded Run(s).",
          notice: "Publication is an explicit reviewed decision; the working draft can continue.",
          published_at: campaign.updated || campaign.date || "date unknown",
          timestamp_basis: "publication_decision",
          source: {object_id: campaign.id, revision: campaign.revision || "demo",
                   section: "benchmark"}
        });
      });
      (db.solutions || []).filter(function (solution) {
        return solution.publication === "published" && solution.recommendation;
      }).forEach(function (solution) {
        items.push({
          kind: "recommendation_published",
          title: solution.name,
          summary: "Editorial context: " + solution.recommendation,
          notice: "An editorial opinion is descriptive context. It never overrides the " +
            "measured methodology result and is not a ranking.",
          published_at: solution.lastReviewed || "date unknown",
          timestamp_basis: "editorial_revision",
          source: {object_id: solution.id, revision: "demo", section: "recommendations"}
        });
      });
      (db.guides || []).filter(function (guide) {
        return guide.status === "published";
      }).forEach(function (guide) {
        items.push({
          kind: "guide_published",
          title: guide.title,
          summary: guide.type + " published for reuse.",
          notice: "A guide is documentation for an exact configuration, not a compatibility guarantee.",
          published_at: guide.date || "date unknown",
          timestamp_basis: "revision_created_at",
          source: {object_id: guide.id, revision: "demo", section: "guides"}
        });
      });
      (db.watch || []).filter(function (entry) {
        return entry.publication === "published";
      }).forEach(function (entry) {
        items.push({
          kind: "watch_published",
          title: entry.title,
          summary: entry.summary || "Reviewed Watch signal made visible.",
          notice: "A reviewed signal is not a measured Run and creates no obligation to run a benchmark.",
          published_at: entry.date || "date unknown",
          timestamp_basis: "revision_created_at",
          source: {object_id: entry.id, revision: "demo", section: "watch"}
        });
      });
      (db.components || []).filter(function (component) {
        return component.publication === "published";
      }).slice(0, 5).forEach(function (component) {
        items.push({
          kind: "technology_available",
          title: component.type + " · " + component.name,
          summary: "Available in the shared fictional Catalog.",
          notice: "Catalog availability is shared Workgroup metadata, not measured experimental evidence.",
          published_at: component.date || "date unknown",
          timestamp_basis: "record_created_at",
          source: {object_id: component.id, revision: "demo", section: "catalog"}
        });
      });
      items.sort(function (a, b) {
        return String(b.published_at).localeCompare(String(a.published_at));
      });
      var counts = {};
      items.forEach(function (entry) { counts[entry.kind] = (counts[entry.kind] || 0) + 1; });
      return {
        generated_from: "effective_published_sources",
        scope: "published_only",
        counts: counts,
        items: items.slice(0, 40),
        excluded: {
          "unpublished_or_draft_records": "never included",
          "discussions_internal_or_private": "never included",
          "activity_feed_and_audit_events": "never included",
          "theoretical_forecasts": "never included"
        },
        notes: [
          "Measured fictional Demo evidence only; published failed Runs stay negative evidence.",
          "Theoretical Forecasts, internal Watch hypotheses and drafts are absent by design."
        ]
      };
    }
    return {load: function () { return Promise.resolve(build()); }};
  }
  function mount(element, provider, mode, options) {
    if (!element || !provider || typeof provider.load !== "function")
      throw Error("Published updates presenter requires a provider");
    options = options || {};
    var enabled = false, generation = 0;
    element.hidden = true;
    function currentWorkspace() {
      /* Source links stay inside the workspace the reader is actually in, so a
       * read-only persona never receives an unreachable Workgroup deep link. */
      var value = new URLSearchParams(root.location.search).get("workspace");
      return ["workgroup", "engineer", "management"].includes(value) ?
        value : (options.workspace || "workgroup");
    }
    async function refresh() {
      if (!enabled) return;
      var ticket = ++generation;
      element.innerHTML = '<p role="status">Loading published knowledge…</p>';
      try {
        var payload = await provider.load();
        if (ticket !== generation || !enabled) return;
        element.innerHTML = present(payload, {
          mode: mode, workspace: currentWorkspace,
          sections: typeof options.sections === "function" ?
            options.sections() : options.sections,
          route: options.route || root.AICompassContext.route});
      } catch (error) {
        if (ticket !== generation || !enabled) return;
        element.innerHTML = '<p role="alert" data-updates-error>Published updates unavailable: ' +
          escape(error.message) + '. No drafts, Demo records or cross-mode fallback are shown.</p>';
      }
    }
    return {
      setAccess: function (on) {
        enabled = !!on;
        ++generation;
        element.hidden = !enabled;
        if (enabled) refresh();
        else element.replaceChildren();
      },
      refresh: refresh
    };
  }
  root.AICompassUpdates = {present: present, serverProvider: serverProvider,
    demoProvider: demoProvider, mount: mount, kinds: KIND_LABELS,
    serverSections: serverSections};
})(window);
