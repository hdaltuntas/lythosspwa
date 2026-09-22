"use strict";
/* Lythos SPWA — the browser interface.
 *
 * The forms are built from the schema the server sends: field keys, labels,
 * units and defaults are declared once, in Python. Nothing here holds a second
 * copy of a label, so changing the language means fetching the schema again and
 * redrawing the forms.
 *
 * Every input lives in one flat object (S.values). That object is what is sent
 * to the server, and what a saved project file is made of.
 */

/* --------------------------------------------------------------- state */
const S = {
  meta: null,             // /api/meta
  values: {},             // current value of every field
  module: "inputs",       // inputs | study
  view: { inputs: "summary", study: "study" },
  analysis: null,         // last analysis payload
  study: null,            // last study payload
  figure: "net_pressure",
  output: "",
  selected: { soil: 0, anchors: 0, study: 0 },
  variables: [],          // inputs a study may sweep
  poll: null,
  plotVersion: 0,         // so a redrawn figure is not served from the cache
};

const $ = (id) => document.getElementById(id);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) node.setAttribute(k, v);
  }
  for (const c of children) if (c) node.append(c);
  return node;
};
const T = (key) => (S.meta && S.meta.strings[key]) || key;

/* ------------------------------------------------------------- server */
async function api(path, body) {
  const options = body === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data;
}

function status(message, isError = false) {
  $("statusMsg").textContent = message || "";
  $("statusBar").classList.toggle("error", !!isError);
}

function busy(on, note) {
  $("progressBar").style.width = on ? "65%" : "0";
  if (note !== undefined) status(note);
  for (const id of ["btnAnalyse", "btnStudy", "btnReport"]) {
    const node = $(id);
    if (node) node.disabled = on;
  }
  $("btnCancel").disabled = !on;
}

function progress(done, total) {
  const pct = total > 0 ? Math.round((100 * done) / total) : 0;
  $("progressBar").style.width = `${pct}%`;
}

async function download(path, body, filename) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || response.statusText);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = el("a", { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/* -------------------------------------------------------- form building */
function fieldNode(field) {
  const id = "f_" + field.key;
  const value = S.values[field.key];

  if (field.kind === "check") {
    const input = el("input", {
      type: "checkbox", id,
      onchange: (e) => { S.values[field.key] = e.target.checked; },
    });
    input.checked = !!value;
    return el("div", { class: "field check" }, input, el("label", { for: id, text: field.label }));
  }

  let input;
  if (field.kind === "select") {
    input = el("select", { id, onchange: (e) => onSelect(field.key, e.target.value) });
    for (const option of field.options || []) {
      input.append(el("option", { value: option.value, text: option.label }));
    }
    input.value = value ?? (field.options && field.options[0] && field.options[0].value);
  } else if (field.kind === "text") {
    input = el("input", {
      type: "text", id,
      oninput: (e) => { S.values[field.key] = e.target.value; },
    });
    input.value = value ?? "";
  } else {
    input = el("input", {
      type: "number", id,
      step: field.step || (field.decimals === 0 ? 1 : Math.pow(10, -(field.decimals ?? 2))),
      min: field.min, max: field.max,
      oninput: (e) => {
        const raw = e.target.value.trim();
        S.values[field.key] = raw === "" ? null : parseFloat(raw);
      },
    });
    input.value = value === null || value === undefined ? "" : value;
  }

  const label = el("label", { for: id }, document.createTextNode(field.label));
  if (field.unit) label.append(el("span", { class: "unit", text: field.unit }));
  return el("div", { class: "field" }, label, input);
}

function onSelect(key, value) {
  S.values[key] = value;
  // The section models on offer follow the manufacturer.
  if (key === "selected_manufacturer") {
    const models = (S.meta.schema.sections || {})[value] || [];
    if (models.length && !models.includes(S.values.selected_section_model)) {
      S.values.selected_section_model = models[0];
    }
    renderStructureForm();
  }
}

function groupNode(group) {
  const box = el("fieldset", {}, el("legend", { text: group.title }));
  for (const field of group.fields) box.append(fieldNode(field));
  if (group.note) box.append(el("div", { class: "note", text: group.note }));
  return box;
}

function renderForm(host, groups) {
  host.replaceChildren(...groups.map(groupNode));
}

function renderStructureForm() {
  // The section list depends on the chosen manufacturer, so the group is
  // rebuilt from the schema with that one field's options replaced.
  const groups = S.meta.schema.structure.groups.map((group) => ({
    ...group,
    fields: group.fields.map((field) => {
      if (field.key !== "selected_section_model") return field;
      const models = (S.meta.schema.sections || {})[S.values.selected_manufacturer] || [];
      return { ...field, options: models.map((m) => ({ value: m, label: m })) };
    }),
  }));
  renderForm($("structureForm"), groups);
}

/* ------------------------------------------------------------ input tables */
const TABLES = {
  soil: { values: "soil_profile", head: "soilHead", body: "soilBody", schema: "soil" },
  anchors: { values: "anchors", head: "anchorHead", body: "anchorBody", schema: "anchors" },
  study: { values: "study_variables", head: "studyHead", body: "studyBody", schema: "study_vars" },
};

function columnsOf(name) {
  const columns = S.meta.schema[TABLES[name].schema].columns.map((c) => ({ ...c }));
  if (name === "study") {
    // The variables on offer depend on how many soil layers and anchors there are.
    columns[0] = { ...columns[0], options: S.variables };
  }
  return columns;
}

function renderTable(name) {
  const spec = TABLES[name];
  const columns = columnsOf(name);
  $(spec.head).replaceChildren(...columns.map((c) => el("th", { text: c.label })));

  const rows = S.values[spec.values] || (S.values[spec.values] = []);
  const body = $(spec.body);
  body.replaceChildren();
  rows.forEach((row, index) => {
    const tr = el("tr", {
      class: index === S.selected[name] ? "selected" : "",
      onclick: () => { S.selected[name] = index; renderTable(name); },
    });
    for (const column of columns) {
      let input;
      if (column.kind === "select") {
        input = el("select", { onchange: (e) => { row[column.key] = e.target.value; } });
        for (const option of column.options || []) {
          input.append(el("option", { value: option.value, text: option.label }));
        }
        input.value = row[column.key] ?? (column.options[0] ? column.options[0].value : "");
        row[column.key] = input.value;
      } else {
        input = el("input", {
          type: column.kind === "number" ? "number" : "text",
          step: "any",
          oninput: (e) => {
            const raw = e.target.value;
            row[column.key] = column.kind === "number"
              ? (raw === "" ? null : parseFloat(raw))
              : raw;
          },
        });
        input.value = row[column.key] ?? "";
      }
      tr.append(el("td", {}, input));
    }
    body.append(tr);
  });
}

function blankRow(name) {
  if (name === "soil") {
    const last = (S.values.soil_profile || []).slice(-1)[0];
    return last ? { ...last } : {};
  }
  if (name === "anchors") {
    const last = (S.values.anchors || []).slice(-1)[0] || {};
    return { ...last, depth: (last.depth || 0) + 2.5 };
  }
  const first = S.variables[0];
  return {
    path: first ? first.value : "", label: first ? first.label : "",
    mode: "range", min: 0, max: 1, dist: "normal", mean: 0, cov: 0.1, n_points: 5,
  };
}

function addRow(name) {
  const key = TABLES[name].values;
  (S.values[key] = S.values[key] || []).push(blankRow(name));
  S.selected[name] = S.values[key].length - 1;
  renderTable(name);
  if (name !== "study") refreshVariables();
}

function removeRow(name) {
  const rows = S.values[TABLES[name].values] || [];
  const minimum = name === "soil" ? 1 : 0;
  if (rows.length <= minimum) return;
  rows.splice(S.selected[name], 1);
  S.selected[name] = Math.max(0, S.selected[name] - 1);
  renderTable(name);
  if (name !== "study") refreshVariables();
}

async function refreshVariables() {
  try {
    const data = await api("/api/variables", { values: S.values });
    S.variables = data.choices || [];
    if (S.module === "study") renderTable("study");
  } catch {
    /* the list is a convenience; a failure here must not stop the analysis */
  }
}

/* ------------------------------------------------------------ views */
const VIEWS = {
  inputs: [["summary", "view_summary"], ["text", "view_text"], ["figures", "view_figures"]],
  study: [["study", "view_study"], ["figures", "view_figures"], ["text", "view_text"]],
};

function renderTabs() {
  $("viewTabs").replaceChildren(...VIEWS[S.module].map(([key, label]) =>
    el("button", {
      text: T(label),
      class: S.view[S.module] === key ? "active" : "",
      onclick: () => { S.view[S.module] = key; renderTabs(); renderView(); },
    })));
}

function placeholder(text) {
  return el("div", { class: "placeholder", text });
}

function plotImage(target, kind, output) {
  const query = `target=${target}&kind=${kind}` +
    (output ? `&output=${encodeURIComponent(output)}` : "") + `&v=${S.plotVersion}`;
  return el("img", { src: `/api/plot?${query}`, alt: kind });
}

function dataTable(columns, rows) {
  return el("table", { class: "data" },
    el("thead", {}, el("tr", {}, ...columns.map((c) => el("th", { text: c })))),
    el("tbody", {}, ...rows.map((row) => el("tr", {}, ...row.map((cell) =>
      el("td", { text: cell }))))));
}

function cardRow(cards) {
  return el("div", { class: "cards" }, ...cards.map((card) =>
    el("div", { class: "card " + (card.state || "") },
      el("small", { text: card.title }),
      el("b", { text: card.value }),
      el("span", { class: "sub", text: card.sub || "" }))));
}

function warningBox(warnings) {
  if (!warnings || !warnings.length) return null;
  return el("div", { class: "warnings" },
    el("h3", { text: T("warnings_title").replace(/[\n-]/g, "").trim() }),
    el("ul", {}, ...warnings.map((w) => el("li", { text: w }))));
}

function updatePicker() {
  const showFigures = S.view[S.module] === "figures";
  $("picker").hidden = !showFigures;
  if (!showFigures) return;

  const figure = $("figure");
  if (S.module === "inputs") {
    const keys = (S.analysis && S.analysis.figures) || [];
    figure.replaceChildren(...keys.map((key) =>
      el("option", { value: key, text: S.meta.figure_labels[key] || key })));
    if (!keys.includes(S.figure)) S.figure = keys[0] || "net_pressure";
    figure.value = S.figure;
    $("outputWrap").hidden = true;
  } else {
    const views = (S.study && S.study.views) || [];
    figure.replaceChildren(...views.map((view) =>
      el("option", { value: view, text: S.meta.study_view_labels[view] || view })));
    if (!views.includes(S.figure)) S.figure = views[0] || "hist";
    figure.value = S.figure;

    const outputs = (S.study && S.study.outputs) || [];
    $("outputWrap").hidden = outputs.length === 0;
    const output = $("output");
    output.replaceChildren(...outputs.map((o) =>
      el("option", { value: o.value, text: o.label })));
    if (!outputs.some((o) => o.value === S.output)) {
      S.output = outputs.length ? outputs[0].value : "";
    }
    output.value = S.output;
  }
}

function renderView() {
  const view = $("view");
  const which = S.view[S.module];
  updatePicker();

  if (S.module === "inputs") {
    if (!S.analysis) return view.replaceChildren(placeholder(T("no_results")));
    if (which === "summary") {
      const parts = [cardRow(S.analysis.cards)];
      const warnings = warningBox(S.analysis.warnings);
      if (warnings) parts.push(warnings);
      parts.push(plotImage("analysis", "net_pressure"));
      return view.replaceChildren(...parts);
    }
    if (which === "text") return view.replaceChildren(el("pre", { text: S.analysis.text }));
    return view.replaceChildren(plotImage("analysis", S.figure));
  }

  if (!S.study) return view.replaceChildren(placeholder(T("no_study")));
  if (which === "figures") {
    return view.replaceChildren(plotImage("study", S.figure, S.output));
  }
  if (which === "text") return view.replaceChildren(el("pre", { text: S.study.text }));

  const parts = [el("pre", { text: S.study.text })];
  if (S.study.table && S.study.table.rows.length) {
    parts.push(el("h2", { text: T("study_vars_group") }));
    parts.push(dataTable(S.study.table.columns, S.study.table.rows));
    if (S.study.table.truncated) {
      parts.push(el("div", { class: "note", text: T("study_export_csv") }));
    }
  }
  view.replaceChildren(...parts);
}

/* ------------------------------------------------------------- actions */
async function runAnalysis() {
  busy(true, T("running_analysis"));
  try {
    const data = await api("/api/analyse", { values: S.values });
    S.analysis = data;
    S.plotVersion += 1;
    if (!data.figures.includes(S.figure)) S.figure = data.figures[0];
    switchModule("inputs");
    S.view.inputs = S.view.inputs === "text" ? "text" : "summary";
    renderTabs();
    renderView();
    status(`${T("analysis_complete")} ${data.headline}`);
  } catch (error) {
    S.analysis = null;
    renderView();
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

async function runStudy() {
  busy(true, T("running_analysis"));
  try {
    const data = await api("/api/study", { values: S.values });
    if (!data.ok) throw new Error(data.error);
    S.study = null;
    switchModule("study");
    startPolling();
  } catch (error) {
    busy(false);
    status(`${T("error")}: ${error.message}`, true);
  }
}

async function cancelStudy() {
  try {
    await api("/api/cancel", {});
    status(T("cancelled"));
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  }
}

async function loadStudy() {
  try {
    const data = await api("/api/study");
    if (!data.ok) throw new Error(data.error);
    S.study = data;
    S.output = data.outputs.length ? data.outputs[0].value : "";
    S.figure = data.views[0] || "hist";
    S.plotVersion += 1;
    renderTabs();
    renderView();
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  }
}

async function downloadReport() {
  busy(true, T("report_running"));
  try {
    const format = $("reportFormat").value || "pdf";
    await download("/api/report", { format }, `lythosspwa_report.${format}`);
    status(T("report_action") + " ✓");
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  } finally {
    busy(false);
  }
}

async function exportStudy(format) {
  try {
    await download("/api/export-study", { format }, `lythosspwa_study.${format}`);
    status(T("saved"));
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  }
}

/* --------------------------------------------------- background polling */
function startPolling() {
  if (S.poll) return;
  S.poll = setInterval(async () => {
    let state;
    try {
      state = await api("/api/state");
    } catch {
      return;
    }
    if (state.job === "running") {
      progress(state.done, state.total);
      if (state.total) {
        status(T("study_progress").replace("{done}", state.done).replace("{total}", state.total));
      }
      return;
    }
    clearInterval(S.poll);
    S.poll = null;
    busy(false);

    if (state.job === "error") {
      status(`${T("error")}: ${state.error}`, true);
      return;
    }
    if (state.has_study) {
      await loadStudy();
      $("btnCsv").disabled = false;
      $("btnXlsx").disabled = false;
    }
    if (state.note) status(state.note);
  }, 400);
}

/* ------------------------------------------------------------- layout */
function switchModule(name) {
  S.module = name;
  $("paneInputs").hidden = name !== "inputs";
  $("paneStudy").hidden = name !== "study";
  for (const button of document.querySelectorAll("nav.modules button")) {
    button.classList.toggle("active", button.dataset.module === name);
  }
  if (name === "study") renderTable("study");
  renderTabs();
  renderView();
}

function applyMeta(meta) {
  S.meta = meta;
  document.documentElement.lang = meta.language;

  $("tagline").textContent = T("tagline");
  $("lblLanguage").textContent = T("language");
  $("btnOpen").textContent = T("open");
  $("btnSave").textContent = T("save");
  $("lblReport").textContent = T("report_format");
  $("btnReport").textContent = T("report_action");
  $("tabInputs").textContent = T("tab_inputs");
  $("tabStudy").textContent = T("tab_study_inputs");
  $("lblSoil").textContent = T("soil_group");
  $("lblAnchors").textContent = T("anchor_group");
  $("lblStudyVars").textContent = T("study_vars_group");
  $("btnAnalyse").textContent = T("run_analysis_button");
  $("btnStudy").textContent = T("study_run");
  $("btnCancel").textContent = T("study_cancel");
  $("btnCsv").textContent = T("study_export_csv");
  $("btnXlsx").textContent = T("study_export_xlsx");
  $("lblFigure").textContent = T("figure");
  $("lblOutput").textContent = T("output");
  for (const button of document.querySelectorAll("button.add")) button.textContent = T("add_row");
  for (const button of document.querySelectorAll("button.del")) button.textContent = T("del_row");

  const language = $("language");
  language.replaceChildren(...meta.languages.map((code) =>
    el("option", { value: code, text: code.toUpperCase() })));
  language.value = meta.language;

  const report = $("reportFormat");
  const previous = report.value;
  report.replaceChildren(...["pdf", "html", "docx"].map((format) =>
    el("option", { value: format, text: T("report_" + format) })));
  report.value = previous || "pdf";

  renderForm($("projectForm"), meta.schema.project.groups);
  renderStructureForm();
  renderForm($("studyForm"), meta.schema.study.groups);
  renderTable("soil");
  renderTable("anchors");
  renderTabs();
  renderView();
  status(T("ready"));
}

async function setLanguage(code) {
  applyMeta(await api("/api/language", { lang: code }));
  if (S.analysis) await runAnalysis();
  if (S.study) await loadStudy();
}

/* ------------------------------------------------------------ save / open */
async function saveProject() {
  try {
    await download("/api/project", { values: S.values }, "project.spwa");
    status(T("saved"));
  } catch (error) {
    status(`${T("error")}: ${error.message}`, true);
  }
}

function openProject(file) {
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const project = JSON.parse(reader.result);
      const data = await api("/api/load", { project });
      S.values = data.values;
      S.analysis = null;
      S.study = null;
      renderForm($("projectForm"), S.meta.schema.project.groups);
      renderStructureForm();
      renderForm($("studyForm"), S.meta.schema.study.groups);
      renderTable("soil");
      renderTable("anchors");
      await refreshVariables();
      renderTable("study");
      renderView();
      status(T("loaded"));
    } catch (error) {
      status(`${T("error")}: ${error.message}`, true);
    }
  };
  reader.readAsText(file);
}

/* ------------------------------------------------------------------ theme */
async function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("lythosspwa-theme", theme);
  } catch { /* storage can be switched off in a private window */ }
  try {
    await api("/api/theme", { theme });           // the figures follow the page
    if (S.analysis || S.study) {
      S.plotVersion += 1;
      renderView();
    }
  } catch { /* the page is themed either way */ }
}

function storedTheme() {
  try {
    return localStorage.getItem("lythosspwa-theme");
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------- start-up */
async function start() {
  const theme = storedTheme();
  if (theme) document.documentElement.setAttribute("data-theme", theme);

  const meta = await api("/api/meta");
  S.values = JSON.parse(JSON.stringify(meta.defaults));
  applyMeta(meta);
  if (theme === "dark") await applyTheme("dark");
  await refreshVariables();

  $("language").addEventListener("change", (e) => setLanguage(e.target.value));
  $("btnTheme").addEventListener("click", () => applyTheme(
    document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"));
  $("btnSave").addEventListener("click", saveProject);
  $("btnOpen").addEventListener("click", () => $("fileInput").click());
  $("fileInput").addEventListener("change", (e) => {
    if (e.target.files[0]) openProject(e.target.files[0]);
    e.target.value = "";
  });
  $("btnReport").addEventListener("click", downloadReport);
  $("btnAnalyse").addEventListener("click", runAnalysis);
  $("btnStudy").addEventListener("click", runStudy);
  $("btnCancel").addEventListener("click", cancelStudy);
  $("btnCsv").addEventListener("click", () => exportStudy("csv"));
  $("btnXlsx").addEventListener("click", () => exportStudy("xlsx"));
  $("figure").addEventListener("change", (e) => { S.figure = e.target.value; renderView(); });
  $("output").addEventListener("change", (e) => { S.output = e.target.value; renderView(); });
  for (const button of document.querySelectorAll("button.add")) {
    button.addEventListener("click", () => addRow(button.dataset.table));
  }
  for (const button of document.querySelectorAll("button.del")) {
    button.addEventListener("click", () => removeRow(button.dataset.table));
  }
  for (const button of document.querySelectorAll("nav.modules button")) {
    button.addEventListener("click", () => switchModule(button.dataset.module));
  }
  $("btnCancel").disabled = true;
  $("btnCsv").disabled = true;
  $("btnXlsx").disabled = true;
}

start().catch((error) => status("Error: " + error.message, true));
