(function () {
  const SOURCES = window.TQH_SOURCES;
  const ELSEWHERE = window.TQH_ELSEWHERE;
  const PREP = window.TQH_INTERVIEW;
  const { withTosca } = window.TQH_UTIL;
  const CACHE_TTL = 30 * 60 * 1000;
  const PAGE = 30;
  // "Tosca" is also an opera and an OASIS cloud standard; drop those.
  const NOISE = /\b(puccini|opera|soprano|oasis|topology[_ ]template|tosca[-_ ]parser|tosca_definitions_version|cloudify|onap)\b/i;

  const $ = (s) => document.querySelector(s);
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage full or blocked */ } },
  };

  const state = {
    query: "",
    status: {},            // sourceId -> { state: loading|ok|error, count, error, cached }
    items: {},             // sourceId -> items[]
    enabled: new Set(store.get("tqh:enabled", SOURCES.map((s) => s.id))),
    shown: PAGE,
    saved: store.get("tqh:saved", []),
    prepCat: "All",
    run: 0,
  };

  // ---------- helpers ----------
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) n.append(c);
    return n;
  }
  function ago(ms) {
    if (!ms || isNaN(ms)) return "";
    const s = (Date.now() - ms) / 1000;
    const units = [[31536000, "y"], [2592000, "mo"], [604800, "w"], [86400, "d"], [3600, "h"], [60, "m"]];
    for (const [sec, u] of units) if (s >= sec) return `${Math.floor(s / sec)}${u} ago`;
    return "just now";
  }
  const norm = (t) => (t || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const sourceOf = (id) => SOURCES.find((s) => s.id === id);
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

  // ---------- fetching ----------
  async function load(force = false) {
    const run = ++state.run;
    const q = state.query;
    state.shown = PAGE;
    SOURCES.forEach((s) => {
      state.status[s.id] = { state: "loading" };
      state.items[s.id] = [];
    });
    renderChips(); renderFeed();

    await Promise.all(SOURCES.map(async (s) => {
      const key = `tqh:cache:${s.id}:${norm(withTosca(q))}`;
      const hit = store.get(key, null);
      let items, cached = false;
      if (!force && hit && Date.now() - hit.t < CACHE_TTL) {
        items = hit.items; cached = true;
      } else {
        try {
          items = (await s.fetch(q)).filter((it) => it.url && it.title);
          store.set(key, { t: Date.now(), items });
        } catch (e) {
          if (run !== state.run) return;
          // Fall back to stale cache rather than showing nothing.
          if (hit) { items = hit.items; cached = true; }
          else { state.status[s.id] = { state: "error", error: e.message || "Failed" }; renderChips(); renderFeed(); return; }
        }
      }
      if (run !== state.run) return;
      items = items.filter((it) => !NOISE.test(`${it.title} ${it.excerpt}`)).map((it) => ({ ...it, source: s.id }));
      state.items[s.id] = items;
      state.status[s.id] = { state: "ok", count: items.length, cached };
      renderChips(); renderFeed();
    }));
  }

  // Merge sources, collapse cross-posts with the same title.
  function merged() {
    const byKey = new Map();
    for (const s of SOURCES) {
      if (!state.enabled.has(s.id)) continue;
      for (const it of state.items[s.id] || []) {
        const key = norm(it.title);
        const prev = byKey.get(key);
        if (!prev) { byKey.set(key, { ...it, also: [] }); continue; }
        if (prev.url === it.url) continue;
        if (!prev.also.some((a) => a.url === it.url)) prev.also.push({ source: it.source, url: it.url });
      }
    }
    return [...byKey.values()];
  }

  function relevance(it, words) {
    const t = it.title.toLowerCase(), e = (it.excerpt || "").toLowerCase();
    let r = 0;
    for (const w of words) { if (t.includes(w)) r += 3; if (e.includes(w)) r += 1; }
    return r + Math.log10(1 + Math.max(0, it.score)) + Math.log10(1 + it.answers) * 0.5;
  }

  function visibleItems() {
    let list = merged();
    if ($("#unanswered").checked) list = list.filter((it) => it.answered === false || (it.answered === null && it.answers === 0));
    const days = +$("#range").value;
    if (days) { const cut = Date.now() - days * 86400000; list = list.filter((it) => (it.activity || it.created) >= cut); }
    const sort = $("#sort").value;
    const words = norm(withTosca(state.query)).split(" ").filter(Boolean);
    const cmp = {
      recent: (a, b) => (b.activity || b.created) - (a.activity || a.created),
      votes: (a, b) => b.score - a.score,
      answers: (a, b) => b.answers - a.answers,
      relevance: (a, b) => relevance(b, words) - relevance(a, words),
    }[sort];
    return list.sort(cmp);
  }

  // ---------- rendering ----------
  function renderChips() {
    const box = $("#sourceChips");
    box.replaceChildren(...SOURCES.map((s) => {
      const st = state.status[s.id] || {};
      const on = state.enabled.has(s.id);
      let label = "…";
      if (st.state === "ok") label = String(st.count);
      if (st.state === "error") label = "!";
      return el("button", {
        type: "button", class: `chip ${st.state || ""}`, "aria-pressed": String(on),
        title: st.state === "error" ? `${s.name}: ${st.error}` : (st.cached ? `${s.name} (cached)` : s.name),
        style: `--src:${s.color}`,
        onclick: () => {
          on ? state.enabled.delete(s.id) : state.enabled.add(s.id);
          store.set("tqh:enabled", [...state.enabled]);
          state.shown = PAGE;
          renderChips(); renderFeed();
        },
      }, el("span", { class: "dot", "aria-hidden": "true" }), s.name, el("span", { class: "count", text: label }));
    }));
  }

  function isSaved(id) { return state.saved.some((x) => x.id === id); }
  function toggleSave(item, btn) {
    if (isSaved(item.id)) state.saved = state.saved.filter((x) => x.id !== item.id);
    else state.saved.unshift({ ...item, savedAt: Date.now() });
    store.set("tqh:saved", state.saved);
    if (btn) { const on = isSaved(item.id); btn.setAttribute("aria-pressed", String(on)); btn.setAttribute("aria-label", on ? "Remove from saved" : "Save question"); }
    $("#savedCount").textContent = state.saved.length;
    if (!$("#panel-saved").hidden) renderSaved();
  }

  const bookmarkSvg = () => {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", "M6 3h12v18l-6-4-6 4z");
    svg.append(p);
    return svg;
  };

  function card(it) {
    const s = sourceOf(it.source) || { name: it.source, color: "var(--muted)" };
    const status = it.answered === true ? el("span", { class: "badge ok", text: it.source === "github" ? "Closed" : "Answered" })
      : (it.answered === false ? el("span", { class: "badge open", text: it.source === "github" ? "Open" : "Unanswered" }) : null);
    const meta = [
      it.author && el("span", { text: it.author }),
      el("span", { text: ago(it.activity || it.created) }),
      el("span", { text: plural(it.score, it.source === "hn" ? "point" : "vote") }),
      el("span", { text: plural(it.answers, it.source.match(/stackoverflow|sqa/) ? "answer" : "comment") }),
    ].filter(Boolean);
    const saveBtn = el("button", {
      type: "button", class: "save", "aria-pressed": String(isSaved(it.id)),
      "aria-label": isSaved(it.id) ? "Remove from saved" : "Save question",
    }, bookmarkSvg());
    saveBtn.addEventListener("click", () => toggleSave(it, saveBtn));
    return el("li", { class: "card", style: `--src:${s.color}` },
      el("div", { class: "card-top" },
        el("span", { class: "src" }, el("span", { class: "dot", "aria-hidden": "true" }), s.name),
        status,
        saveBtn),
      el("h3", {}, el("a", { href: it.url, target: "_blank", rel: "noopener noreferrer", text: it.title })),
      it.excerpt ? el("p", { class: "excerpt", text: it.excerpt }) : null,
      el("div", { class: "meta" }, meta),
      (it.tags && it.tags.length) ? el("div", { class: "tags" }, it.tags.slice(0, 5).map((t) => el("span", { class: "tag", text: t }))) : null,
      (it.also && it.also.length) ? el("div", { class: "also" }, "Also on ",
        it.also.map((a, i) => [i ? ", " : "", el("a", { href: a.url, target: "_blank", rel: "noopener noreferrer", text: (sourceOf(a.source) || {}).name || a.source })])) : null,
    );
  }

  function renderFeed() {
    const list = visibleItems();
    const statuses = SOURCES.filter((s) => state.enabled.has(s.id)).map((s) => state.status[s.id] || {});
    const loading = statuses.filter((s) => s.state === "loading").length;
    const failed = SOURCES.filter((s) => state.enabled.has(s.id) && (state.status[s.id] || {}).state === "error");

    let text = `${plural(list.length, "question")}`;
    if (state.query.trim()) text += ` for “${state.query.trim()}”`;
    if (loading) text += ` · loading ${loading} more source${loading === 1 ? "" : "s"}…`;
    if (failed.length) text += ` · ${failed.map((s) => s.name).join(", ")} unavailable`;
    $("#summary").textContent = text;

    $("#feedList").replaceChildren(...list.slice(0, state.shown).map(card));
    const more = $("#moreBtn");
    more.hidden = list.length <= state.shown;
    more.textContent = `Show more (${list.length - state.shown} left)`;

    const empty = $("#feedEmpty");
    if (!list.length && !loading) {
      empty.hidden = false;
      empty.textContent = !state.enabled.size ? "All sources are switched off. Turn one on above."
        : failed.length === statuses.length ? "Couldn't reach any source. Check your connection, then press Refresh."
        : "No questions match. Try fewer words, a longer time range, or turn off “Unanswered only”.";
    } else empty.hidden = true;

    renderElsewhere();
  }

  function renderElsewhere() {
    const q = state.query.trim() || "tosca";
    $("#elsewhere").replaceChildren(...ELSEWHERE.map((e) =>
      el("a", { class: "btn ghost", href: e.url(q), target: "_blank", rel: "noopener noreferrer", text: e.name + " ↗" })));
  }

  function renderSaved() {
    const box = $("#savedList");
    box.replaceChildren(...state.saved.map((it) => it.prep ? prepCard(it.prep, true) : card(it)));
    $("#savedEmpty").hidden = state.saved.length > 0;
  }

  // ---------- interview prep ----------
  const prepId = (p) => "prep:" + norm(p.q).replace(/ /g, "-");
  function prepCard(p, inList) {
    const id = prepId(p);
    const saveBtn = el("button", { type: "button", class: "save", "aria-pressed": String(isSaved(id)), "aria-label": isSaved(id) ? "Remove from saved" : "Save question" }, bookmarkSvg());
    saveBtn.addEventListener("click", (e) => { e.preventDefault(); toggleSave({ id, prep: p, title: p.q }, saveBtn); });
    const d = el("details", { class: "qa-item" },
      el("summary", {}, el("span", { class: "qa-cat", text: p.cat }), el("span", { class: "qa-q", text: p.q }), saveBtn),
      el("p", { text: p.a }));
    return inList ? el("li", { class: "card prep" }, d) : d;
  }

  function renderPrep() {
    const cats = ["All", ...new Set(PREP.map((p) => p.cat))];
    $("#prepCats").replaceChildren(...cats.map((c) => el("button", {
      type: "button", class: "chip", "aria-pressed": String(state.prepCat === c), style: "--src:var(--accent)",
      onclick: () => { state.prepCat = c; renderPrep(); },
    }, c, el("span", { class: "count", text: String(c === "All" ? PREP.length : PREP.filter((p) => p.cat === c).length) }))));
    const f = norm($("#prepQ").value);
    const list = PREP.filter((p) => (state.prepCat === "All" || p.cat === state.prepCat) && (!f || norm(p.q + " " + p.a).includes(f)));
    $("#prepList").replaceChildren(...list.map((p) => prepCard(p)));
    $("#prepSummary").textContent = list.length ? plural(list.length, "question") : "No questions match that filter.";
  }

  // ---------- tabs & wiring ----------
  function showTab(name, push = true) {
    document.querySelectorAll('[role="tab"]').forEach((t) => {
      const on = t.dataset.tab === name;
      t.setAttribute("aria-selected", String(on));
      $("#" + t.getAttribute("aria-controls")).hidden = !on;
    });
    if (name === "saved") renderSaved();
    if (name === "prep") renderPrep();
    if (push) history.replaceState(null, "", location.pathname + location.search + (name === "feed" ? "" : "#" + name));
  }

  document.querySelectorAll('[role="tab"]').forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  $("#searchForm").addEventListener("submit", (e) => {
    e.preventDefault();
    state.query = $("#q").value.trim();
    const url = new URL(location.href);
    state.query ? url.searchParams.set("q", state.query) : url.searchParams.delete("q");
    history.replaceState(null, "", url);
    load();
  });
  $("#refreshBtn").addEventListener("click", () => { state.query = $("#q").value.trim(); load(true); });
  ["#unanswered", "#range", "#sort"].forEach((s) => $(s).addEventListener("change", () => { state.shown = PAGE; renderFeed(); }));
  $("#moreBtn").addEventListener("click", () => { state.shown += PAGE; renderFeed(); });
  $("#prepQ").addEventListener("input", renderPrep);
  $("#expandAll").addEventListener("click", () => document.querySelectorAll("#prepList details").forEach((d) => (d.open = true)));
  $("#collapseAll").addEventListener("click", () => document.querySelectorAll("#prepList details").forEach((d) => (d.open = false)));

  state.query = new URLSearchParams(location.search).get("q") || "";
  $("#q").value = state.query;
  $("#savedCount").textContent = state.saved.length;
  const tab = location.hash.slice(1);
  showTab(["prep", "saved"].includes(tab) ? tab : "feed", false);
  load();
  window.TQH = { state, load };
})();
