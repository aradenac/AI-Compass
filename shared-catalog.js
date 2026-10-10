/* FUT-03: one catalog presentation/controller for both locally fictional and real Server data. */
(function (root) {
  "use strict";
  var TYPES = ["model", "provider", "harness", "framework"];
  function mount(element, provider, options) {
    if (!provider || !provider.catalog) throw new Error("Catalog domain provider required");
    var models = root.AICompassModels, esc = models.escapeHtml;
    var canRead = false, canWrite = false, generation = 0, rows = [], selected = null;
    var mode = options.mode;
    element.classList.add("shared-catalog-workspace");
    element.innerHTML = '<div class="server-model-toolbar"><h2>Technology Catalog</h2>' +
      '<button type="button" data-common-action="refresh">Refresh</button></div>' +
      '<p data-common-status role="status" aria-live="polite"></p>' +
      '<label>Harness/Framework OS discovery <select data-common-os-filter>'+
      '<option value="all">All (including other-OS and unknown)</option>'+
      '<option value="windows">Windows compatible</option>'+
      '<option value="linux">Linux compatible</option>'+
      '<option value="both">Both systems</option>'+
      '<option value="unknown">Unknown / needs classification</option>'+
      '</select></label>'+
      '<div data-common-list class="grid g2"></div>' +
      '<section data-common-editor hidden></section><section data-common-history hidden></section>';
    var status = element.querySelector("[data-common-status]");
    var list = element.querySelector("[data-common-list]");
    var osFilter = element.querySelector("[data-common-os-filter]");
    var editor = element.querySelector("[data-common-editor]");
    var history = element.querySelector("[data-common-history]");
    function message(text) { status.textContent = text; }
    async function refresh() {
      if (!canRead) return;
      var ticket = ++generation;
      message("Loading " + (mode === "demo" ? "fictional Demo" : "authoritative Server") + " catalog…");
      try {
        var data = await Promise.all(TYPES.map(function (type) { return provider.catalog[type].list(); }));
        if (ticket !== generation || !canRead) return;
        rows = data.flat();
        if (options.onRows) options.onRows(rows);
        drawCatalog();
        message(rows.length + " catalog record(s) · " + (mode === "demo" ? "Fictional local data" : "Real authenticated data"));
      } catch (e) {
        if (ticket !== generation) return;
        rows = []; list.replaceChildren();
        message("Catalog unavailable: " + e.message + ". No Demo fallback.");
      }
    }
    function matchesOS(row, filter) {
      if (filter === "all" || !["harness","framework"].includes(row.type)) return true;
      var known = root.AICompassEnvironment.normalize((row.properties || {}).supported_os);
      if (filter === "unknown") return known === null;
      return known !== null && (filter === "both" ?
        known.length === 2 : known.includes(filter));
    }
    function drawCatalog() {
      var filter = osFilter && osFilter.value || "all";
      list.innerHTML = TYPES.map(function (type) {
        var group = rows.filter(function (r) {return r.type === type;});
        if (filter !== "all" && ["harness","framework"].includes(type))
          group = group.filter(function (r) {return matchesOS(r,filter);});
        return models.renderLane(group,{type:type,canWrite:canWrite,showRevisions:true}) +
          (["harness","framework"].includes(type) ?
            '<p class="muted">OS classification: '+group.map(function(r){
              var supported=root.AICompassEnvironment.normalize((r.properties||{}).supported_os);
              return esc(r.name)+': '+(supported?supported.join(' + '):
                'Unknown / not classified');
            }).join(' · ')+'</p>':"");
      }).join("");
    }
    if (osFilter && osFilter.addEventListener) osFilter.addEventListener("change",drawCatalog);
    function edit(model, type) {
      if (!canWrite) return;
      selected = model;
      var existing = model && (model.properties || {});
      editor.hidden = false; history.hidden = true;
      editor.innerHTML = '<h3>' + (model ? "Revise" : "Create") + ' ' + esc(type) + '</h3>' +
        '<form data-common-form><label>Name <input name="name" required maxlength="160" value="' +
        esc(model && model.name || "") + '"></label>' +
        (["harness","framework"].includes(type) ?
          '<fieldset data-os-fields><legend>Supported operating systems (both = OS-agnostic)</legend>'+
          '<label><input name="osWindows" type="checkbox"'+
             ((existing.supported_os||[]).includes("windows")?' checked':'')+'> Windows</label>'+
          '<label><input name="osLinux" type="checkbox"'+
             ((existing.supported_os||[]).includes("linux")?' checked':'')+'> Linux</label>'+
          '<p>Classify before publishing or asserting this record usable. Unknown historical records remain readable.</p></fieldset>' : '') +
        '<label>Original properties (JSON) <textarea name="properties" rows="10">' +
        esc(JSON.stringify(existing, null, 2)) + '</textarea></label>' +
        '<p>Immutable revision ' + esc(model && model.revision || "new") +
        ' · Preserve unknown fields; no automatic publication.</p>' +
        '<button type="submit">Save</button> <button type="button" data-common-action="cancel">Cancel</button></form>';
      editor.querySelector("form").onsubmit = async function (event) {
        event.preventDefault();
        var button = editor.querySelector('button[type="submit"]');
        button.disabled = true;
        try {
          var values = Object.fromEntries(new FormData(event.currentTarget).entries());
          var properties = JSON.parse(values.properties);
          if (!properties || typeof properties !== "object" || Array.isArray(properties))
            throw new Error("Properties must be a JSON object");
          if (["harness","framework"].includes(type)) {
            var supported = [];
            if (event.currentTarget.elements.osWindows.checked) supported.push("windows");
            if (event.currentTarget.elements.osLinux.checked) supported.push("linux");
            if (!supported.length) throw new Error("Select Windows and/or Linux before saving a usable Harness/Framework.");
            properties.supported_os = supported;
          }
          var adapter = provider.catalog[type];
          if (model) {
            await adapter.revise(model.id, {
              name: values.name, properties: properties, expected_revision: model.revision
            });
          } else {
            await adapter.create({name: values.name, properties: properties});
          }
          editor.hidden = true; await refresh();
        } catch (e) {
          message("Save rejected: " + e.message + (e.status === 409 ?
            " Reload current revision; original record was not overwritten." : ""));
        } finally { button.disabled = false; }
      };
    }
    async function showHistory(model) {
      history.hidden = false; editor.hidden = true;
      history.textContent = "Loading immutable revision history…";
      try {
        var records = await provider.catalog[model.type].revisions(model.id);
        history.textContent = JSON.stringify(records, null, 2);
      } catch (e) { history.textContent = "History unavailable: " + e.message; }
    }
    element.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-common-action],button[data-act]");
      if (!button) return;
      event.stopPropagation(); // never also invoke legacy Demo/Server page handlers
      var action = button.dataset.commonAction || button.dataset.act;
      var id = button.dataset.id;
      if (action === "refresh") { editor.hidden = true; history.hidden = true; refresh(); return; }
      if (action === "cancel") { editor.hidden = true; return; }
      if (action === "newComponentType" && canWrite && TYPES.includes(id)) edit(null, id);
      var model = rows.find(function (row) { return row.id === id; });
      if (!model) return;
      if (action === "editComponent" && canWrite && model.compatibility?.read_only !== true) edit(model, model.type);
      if (action === "modelHistory") showHistory(model);
      if (action === "modelRaw" || action === "catalogEvidence") {
        if (action === "modelRaw" && options.onRaw) return options.onRaw(model);
        if (action === "catalogEvidence" && options.onEvidence) return options.onEvidence(model.id);
        history.hidden = false; editor.hidden = true;
        history.textContent = action === "modelRaw" ? JSON.stringify(model, null, 2) :
          "Evidence is immutable and remains accessible through the authenticated Server detail tools.";
      }
    });
    return {
      setAccess: function (read, write) {
        canRead = !!read; canWrite = !!(read && write);
        ++generation; rows = [];
        element.hidden = !canRead;
        editor.hidden = true; history.hidden = true;
        list.replaceChildren();
        if (canRead) return refresh();
      },
      refresh: refresh
    };
  }
  root.AICompassSharedCatalog = {mount: mount};
})(window);
