// Renders docs/data/dashboard.json, which src/export.py writes from the dbt marts.
// No framework, no chart library: every chart is a few lines of SVG.

const MODEL_GROUPS = [
  ["Heuristic", ["last_touch", "first_touch", "linear", "time_decay", "position_based"]],
  ["Data-driven", ["markov_chain", "shapley_value"]],
];
const MODELS = MODEL_GROUPS.flatMap(([, ms]) => ms);
const TOUCHPOINT_MODELS = ["last_touch", "first_touch", "linear", "time_decay"];

const state = { model: "last_touch", campaignModel: "last_touch", sort: { key: "spend_usd", dir: -1 } };
let D;

// ---------- helpers ----------
const $ = (sel) => document.querySelector(sel);
const NS = "http://www.w3.org/2000/svg";
const MINUS = "−";
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid);
  return el;
}

function s(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid != null) el.append(kid);
  return el;
}

const f = {
  usd: (v) => "$" + Math.round(v).toLocaleString("en-US"),
  usd2: (v) => (v == null ? "–" : "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })),
  int: (v) => Math.round(v).toLocaleString("en-US"),
  dec: (v) => v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 }),
  pct: (v, d = 1) => (v * 100).toFixed(d) + "%",
  x: (v) => (v == null ? "–" : v.toFixed(1) + "×"),
  pts: (v) => (v >= 0 ? "+" : MINUS) + Math.abs(v).toFixed(1) + " pts",
  date: (iso, opts = { month: "short", day: "numeric" }) =>
    new Date(iso.slice(0, 10) + "T00:00:00Z").toLocaleDateString("en-US", { ...opts, timeZone: "UTC" }),
};
const ordinal = (n) => ["first", "second", "third", "fourth", "fifth", "sixth", "seventh"][n - 1] ?? `#${n}`;

const label = (m) => D.channels.find((r) => r.model === m)?.model_label ?? m;
const rowsFor = (m) => D.channels.filter((r) => r.model === m);
const rec = (m, ch) => D.channels.find((r) => r.model === m && r.channel === ch);
const hasTruth = () => D.meta.synthetic && rowsFor("ground_truth").length > 0;
const truth = (ch) => rec("ground_truth", ch);
const channelOrder = () =>
  rowsFor(hasTruth() ? "ground_truth" : "last_touch")
    .sort((a, b) => b.credit - a.credit)
    .map((r) => r.channel);

// The reference tick: an I-beam drawn at the true value, wherever truth appears.
const truthTick = (x, y, half = 9) =>
  s("path", { class: "truth", d: `M${x} ${y - half}V${y + half}M${x - 3} ${y - half}H${x + 3}M${x - 3} ${y + half}H${x + 3}` });

// ---------- tooltip ----------
const tip = $("#tooltip");
function showTip(html, e) {
  tip.innerHTML = html;
  tip.classList.add("on");
  const pad = 14;
  const { width, height } = tip.getBoundingClientRect();
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  if (x + width > innerWidth - 8) x = e.clientX - width - pad;
  if (y + height > innerHeight - 8) y = e.clientY - height - pad;
  tip.style.left = `${Math.max(8, x)}px`;
  tip.style.top = `${Math.max(8, y)}px`;
}
const hideTip = () => tip.classList.remove("on");
document.addEventListener("pointermove", (e) => {
  const target = e.target.closest?.("[data-tip]");
  if (target && target.__tip) showTip(typeof target.__tip === "function" ? target.__tip(e) : target.__tip, e);
  else hideTip();
});
document.addEventListener("scroll", hideTip, { passive: true });
const withTip = (el, html) => {
  el.setAttribute("data-tip", "");
  el.__tip = html;
  return el;
};
const tipRows = (head, rows) =>
  `<div class="t-head">${esc(head)}</div>` +
  rows.map(([k, v, strong]) => `<div class="t-row"><span>${esc(k)}</span>${strong ? `<b>${esc(v)}</b>` : `<span>${esc(v)}</span>`}</div>`).join("");

// ---------- header, stats, snapshot ----------
function renderHeader() {
  const t = D.totals;
  const days = D.daily.length;
  $("#period").textContent =
    `${f.date(t.start_date)} to ${f.date(t.end_date, { month: "short", day: "numeric", year: "numeric" })} · ${days} days · ` +
    `${D.meta.synthetic ? "synthetic data" : "event data"} · ${D.meta.attribution_window_days}-day attribution window`;

  const stats = [
    ["Spend", f.usd(t.spend_usd), `${f.int(t.impressions)} impressions`],
    ["Revenue", f.usd(t.revenue_usd), `${f.int(t.late_conversions)} conversions arrived late`],
    ["Return on ad spend", f.x(t.roas), `revenue ÷ spend, all ${rowsFor("last_touch").length} channels`],
    ["Conversions", f.int(t.conversions), `${f.pct(t.conversion_rate)} of ${f.int(t.users_reached)} users reached`],
  ];
  $("#stats").replaceChildren(
    ...stats.map(([k, v, note]) =>
      h("div", { class: "stat" }, h("div", { class: "stat-label" }, k), h("div", { class: "stat-value" }, v), h("div", { class: "stat-note" }, note))
    )
  );

  const dbt = D.pipeline.dbt ?? {};
  const all = [...(dbt.models ?? []), ...(dbt.tests ?? [])];
  const ok = all.filter((r) => r.status === "success" || r.status === "pass").length;
  const q = D.pipeline.quality?.results ?? [];
  const qok = q.filter((r) => r.passed).length;
  $("#snapshot").replaceChildren(
    h("div", {}, "Data through", h("strong", {}, f.date(D.totals.end_date))),
    h("div", {}, "dbt build", h("strong", {}, `${ok}/${all.length} passed`)),
    h("div", {}, "Quality gate", h("strong", {}, `${qok}/${q.length} passed`)),
    h("a", { href: "https://github.com/Pranavmodem/ads-attribution-metrics-pipeline" }, "Source on GitHub")
  );
  $("#generated").textContent = `Generated ${D.meta.generated_at.replace("T", " ").slice(0, 16)} UTC`;
}

// ---------- model picker ----------
function renderPicker() {
  $("#model-picker").replaceChildren(
    ...MODEL_GROUPS.map(([group, models]) =>
      h(
        "div",
        { class: "picker-group" },
        h("span", {}, group),
        h(
          "div",
          { class: "segmented" },
          models.map((m) =>
            h("button", { type: "button", role: "radio", "aria-checked": String(m === state.model), onclick: () => setModel(m) }, h("i"), label(m))
          )
        )
      )
    )
  );
}

function setModel(m) {
  state.model = m;
  renderPicker();
  renderAccuracy();
  renderCalibration();
  renderRoas();
}

// ---------- calibration chart (the main moment) ----------
function renderCalibration() {
  const el = $("#calibration");
  const W = el.clientWidth || 720;
  const narrow = W < 560;
  const L = narrow ? 92 : 112;
  const R = narrow ? 72 : 112;
  const top = 28;
  const rowH = narrow ? 44 : 52;
  const channels = channelOrder();
  const others = MODELS.filter((m) => m !== state.model);
  const max = Math.ceil(Math.max(...D.channels.map((r) => r.credit)) * 10) / 10;
  const x = (v) => L + (v / max) * (W - L - R);
  const H = top + channels.length * rowH;

  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": `Channel credit under ${label(state.model)} compared with the true share` });
  const step = max > 0.5 ? 0.1 : 0.05;
  for (let t = 0; t <= max + 1e-9; t += step) {
    svg.append(
      s("line", { class: "grid-line", x1: x(t), x2: x(t), y1: top - 8, y2: H }),
      s("text", { x: x(t), y: top - 14, "text-anchor": "middle" }, f.pct(t, 0))
    );
  }
  svg.append(s("text", { x: W, y: top - 14, "text-anchor": "end" }, narrow ? "gap" : "gap to truth"));

  channels.forEach((ch, i) => {
    const y = top + i * rowH + rowH / 2;
    const pick = rec(state.model, ch);
    const tr = hasTruth() ? truth(ch) : null;
    const g = s("g");
    g.append(
      s("rect", { class: "row-hover", x: 0, y: y - rowH / 2 + 2, width: W, height: rowH - 4, rx: 6 }),
      s("text", { class: "label", x: 8, y: y + 4 }, ch),
      s("line", { class: "track", x1: x(0), x2: x(max), y1: y, y2: y })
    );
    for (const m of others) {
      const r = rec(m, ch);
      if (r) g.append(s("circle", { class: "dot-other", cx: x(r.credit), cy: y, r: 4 }));
    }
    if (tr) g.append(s("line", { class: "gap-line", x1: x(tr.credit), x2: x(pick.credit), y1: y, y2: y }), truthTick(x(tr.credit), y));
    g.append(s("circle", { class: "dot-pick", cx: x(pick.credit), cy: y, r: 6 }));
    if (tr) {
      const strong = Math.abs(pick.error_pp) >= 5;
      g.append(s("text", { class: strong ? "value-strong" : "value", x: W - 4, y: y + 4, "text-anchor": "end" }, f.pts(pick.error_pp)));
    }

    const hit = s("rect", { class: "hit", x: 0, y: y - rowH / 2, width: W, height: rowH });
    withTip(hit, () => {
      const list = MODELS.map((m) => rec(m, ch)).sort((a, b) => b.credit - a.credit);
      return tipRows(
        `${ch}${tr ? ` · true share ${f.pct(tr.credit)}` : ""}`,
        list.map((r) => [r.model_label, `${f.pct(r.credit)}${tr ? `  ${f.pts(r.error_pp)}` : ""}`, r.model === state.model])
      );
    });
    g.append(hit);
    svg.append(g);
  });
  el.replaceChildren(svg);

  const dot = (cls, r) => s("svg", { viewBox: "-8 -8 16 16" }, s("circle", { class: cls, r }));
  $("#calibration-legend").replaceChildren(
    h("span", {}, dot("dot-pick", 6), label(state.model)),
    hasTruth() ? h("span", {}, s("svg", { viewBox: "-8 -10 16 20" }, truthTick(0, 0, 8)), "Ground truth") : null,
    h("span", {}, dot("dot-other", 4), "The other six models")
  );

  // Table view for screen readers and anyone who prefers numbers.
  const cols = [...(hasTruth() ? ["ground_truth"] : []), ...MODELS];
  $("#calibration-table").replaceChildren(
    h(
      "table",
      {},
      h("thead", {}, h("tr", {}, h("th", {}, "Channel"), cols.map((m) => h("th", { class: m === "ground_truth" ? "truth-col" : null }, label(m))))),
      h(
        "tbody",
        {},
        channels.map((ch) =>
          h("tr", {}, h("td", {}, ch), cols.map((m) => h("td", { class: m === "ground_truth" ? "truth-col" : null }, f.pct(rec(m, ch).credit))))
        )
      )
    )
  );

  // The sentence above the chart says what the selected model gets most wrong.
  const finding = $("#accuracy-finding");
  if (!hasTruth()) {
    finding.textContent = "No ground truth on real data; compare the models with each other";
    return;
  }
  const acc = D.accuracy.find((a) => a.model === state.model);
  const worst = rec(state.model, acc.worst_channel);
  finding.innerHTML =
    `<strong>${esc(label(state.model))}</strong> gives ${esc(worst.channel)} ${f.pct(worst.credit)} of the credit, against a true share of ` +
    `${f.pct(worst.true_credit)}. Across all channels it is off by ${acc.mean_abs_error_pp.toFixed(1)} points on average, ` +
    `${ordinal(acc.accuracy_rank)} closest of seven.`;
}

// ---------- accuracy ranking ----------
function renderAccuracy() {
  const list = $("#accuracy-list");
  if (!hasTruth()) {
    list.replaceChildren(h("li", { class: "caption" }, "Only available on synthetic data"));
    return;
  }
  const maxErr = Math.max(...D.accuracy.map((a) => a.mean_abs_error_pp));
  list.replaceChildren(
    ...D.accuracy.map((a) =>
      h(
        "li",
        {},
        h(
          "button",
          { type: "button", "aria-pressed": String(a.model === state.model), onclick: () => setModel(a.model) },
          h("span", { class: "rank" }, String(a.accuracy_rank)),
          h("span", {}, a.model_label),
          h("span", { class: "num" }, `${a.mean_abs_error_pp.toFixed(1)} pts`),
          h("span", { class: "bar", "aria-hidden": "true" }, h("i", { style: `width:${(a.mean_abs_error_pp / maxErr) * 100}%` }))
        )
      )
    ),
    h("li", { class: "rank-note" }, "Heuristic models split credit by a fixed rule. Data-driven models learn from converting and non-converting journeys alike.")
  );
}

// ---------- channel returns (ROAS) ----------
function renderRoas() {
  const channels = rowsFor(hasTruth() ? "ground_truth" : "last_touch")
    .sort((a, b) => b.spend_usd - a.spend_usd)
    .map((r) => r.channel);
  const vals = D.channels.filter((r) => r.roas > 0).map((r) => r.roas);
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...vals))));
  const hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...vals))));
  const pos = (v) => `${(Math.log10(Math.max(v || lo, lo) / lo) / Math.log10(hi / lo)) * 92 + 4}%`;
  const ticks = [];
  for (let t = lo; t <= hi + 1e-9; t *= 10) ticks.push(t);

  const axis = s("svg", { height: 32 });
  const narrow = matchMedia("(max-width: 860px)").matches;
  ticks.forEach((t, i) => {
    const edge = i === 0 || i === ticks.length - 1;
    if (narrow && !edge && t !== 1) return; // phones: label the ends and break-even only
    axis.append(s("text", { x: pos(t), y: 20, "text-anchor": i === 0 ? "start" : i === ticks.length - 1 ? "end" : "middle" }, `${t}×`));
  });
  const cells = [
    h("div", { class: "head" }, "Channel"),
    h("div", { class: "head num hide-sm" }, "Spend"),
    h("div", { class: "head bar-cell" }, axis),
    h("div", { class: "head num" }, label(state.model)),
    h("div", { class: "head num" }, hasTruth() ? "True" : ""),
    h("div", { class: "head hide-sm" }, "Gap"),
  ];

  let worst = null;
  for (const ch of channels) {
    const m = rec(state.model, ch);
    const t = hasTruth() ? truth(ch) : null;
    const bar = s("svg", { role: "img", "aria-label": `${ch}: ${f.x(m.roas)} under ${label(state.model)}${t ? `, ${f.x(t.roas)} true` : ""}` });
    for (const tk of ticks) bar.append(s("line", { class: "grid-line", x1: pos(tk), x2: pos(tk), y1: 8, y2: 36 }));
    bar.append(s("line", { class: "grid-line", x1: pos(1), x2: pos(1), y1: 4, y2: 40, "stroke-dasharray": "2 3" }));
    if (t) {
      bar.append(s("line", { class: "gap-line", x1: pos(t.roas), x2: pos(m.roas), y1: 22, y2: 22 }));
      bar.append(s("svg", { x: pos(t.roas), y: 22, overflow: "visible" }, truthTick(0, 0, 8)));
    }
    bar.append(s("circle", { class: "dot-pick", cx: pos(m.roas), cy: 22, r: 6 }));
    withTip(bar, tipRows(ch, [
      [label(state.model), f.x(m.roas), true],
      ...(t ? [["True", f.x(t.roas)]] : []),
      ["Spend", f.usd(m.spend_usd)],
      ["Attributed revenue", f.usd(m.attributed_revenue_usd)],
    ]));

    let verdict = "";
    if (t && t.roas > 0) {
      const ratio = (m.roas || 0) / t.roas;
      if (!worst || Math.abs(Math.log(Math.max(ratio, 1e-3))) > Math.abs(Math.log(Math.max(worst.ratio, 1e-3)))) worst = { ch, m, t, ratio };
      verdict = ratio >= 1.15 ? `overstated ${ratio.toFixed(1)}×` : ratio <= 1 / 1.15 ? `understated ${(1 / Math.max(ratio, 1e-3)).toFixed(1)}×` : "close";
    }
    cells.push(
      h("div", {}, ch),
      h("div", { class: "num hide-sm" }, f.usd(m.spend_usd)),
      h("div", { class: "bar-cell" }, bar),
      h("div", { class: "num pick" }, f.x(m.roas)),
      h("div", { class: "num" }, t ? f.x(t.roas) : ""),
      h("div", { class: "verdict hide-sm" }, verdict)
    );
  }
  $("#roas-table").replaceChildren(...cells);

  const dot = s("svg", { viewBox: "-8 -8 16 16" }, s("circle", { class: "dot-pick", r: 6 }));
  $("#roas-legend").replaceChildren(
    h("span", {}, dot, `ROAS under ${label(state.model)}`),
    hasTruth() ? h("span", {}, s("svg", { viewBox: "-8 -10 16 20" }, truthTick(0, 0, 8)), "True ROAS") : null,
    h("span", {}, s("svg", { viewBox: "0 -8 16 16" }, s("line", { class: "grid-line", x1: 8, x2: 8, y1: -8, y2: 8, "stroke-dasharray": "2 3" })), "Break-even, 1×"),
    h("span", { class: "caption", style: "margin:0" }, "Log scale")
  );

  $("#roas-finding").innerHTML = worst
    ? `Under <strong>${esc(label(state.model))}</strong>, ${esc(worst.ch)} looks like it returns ${f.x(worst.m.roas)} on spend. ` +
      `It actually returns ${f.x(worst.t.roas)}. Budget moved on the first number would go the wrong way.`
    : "Return on ad spend per channel under the selected model";
}

// ---------- spend and revenue trend ----------
function rolling(values, n = 7) {
  return values.map((_, i) => {
    const win = values.slice(Math.max(0, i - n + 1), i + 1);
    return win.reduce((a, b) => a + b, 0) / win.length;
  });
}

function niceMax(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}

function renderTrend() {
  const el = $("#trend-chart");
  const W = el.clientWidth || 720;
  const H = 300;
  const L = 52, R = 72, T = 12, B = 28;
  const days = D.daily;
  const spend = rolling(days.map((d) => d.spend_usd));
  const revenue = rolling(days.map((d) => d.revenue_usd));
  const yMax = niceMax(Math.max(...revenue, ...spend) * 1.05);
  const x = (i) => L + (i / (days.length - 1)) * (W - L - R);
  const y = (v) => T + (1 - v / yMax) * (H - T - B);

  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": "Daily spend and revenue, 7-day average" });
  for (let i = 0; i <= 4; i++) {
    const v = (yMax / 4) * i;
    svg.append(s("line", { class: "grid-line", x1: L, x2: W - R, y1: y(v), y2: y(v) }), s("text", { x: L - 8, y: y(v) + 4, "text-anchor": "end" }, f.usd(v)));
  }
  days.forEach((d, i) => {
    if (d.date.slice(8, 10) === "01") svg.append(s("text", { x: x(i), y: H - 8, "text-anchor": "middle" }, f.date(d.date, { month: "short" })));
  });
  const path = (vals) => vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("");
  svg.append(
    s("path", { d: path(spend), fill: "none", stroke: "var(--text-3)", "stroke-width": 2, "stroke-linejoin": "round" }),
    s("path", { d: path(revenue), fill: "none", stroke: "var(--accent)", "stroke-width": 2, "stroke-linejoin": "round" }),
    s("text", { class: "value-strong", x: W - R + 8, y: y(revenue.at(-1)) + 4 }, "Revenue"),
    s("text", { class: "value", x: W - R + 8, y: y(spend.at(-1)) + 4 }, "Spend")
  );

  const cross = s("line", { class: "grid-line", y1: T, y2: H - B, opacity: 0 });
  const dRev = s("circle", { class: "dot-pick", r: 4, opacity: 0 });
  const dSpend = s("circle", { class: "dot-other", r: 4, opacity: 0 });
  const overlay = s("rect", { class: "hit", x: L, y: T, width: W - L - R, height: H - T - B });
  withTip(overlay, (e) => {
    const box = svg.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    const i = Math.max(0, Math.min(days.length - 1, Math.round(((px - L) / (W - L - R)) * (days.length - 1))));
    for (const [elm, attrs] of [[cross, { x1: x(i), x2: x(i), opacity: 1 }], [dRev, { cx: x(i), cy: y(revenue[i]), opacity: 1 }], [dSpend, { cx: x(i), cy: y(spend[i]), opacity: 1 }]])
      for (const [k, v] of Object.entries(attrs)) elm.setAttribute(k, v);
    const d = days[i];
    return tipRows(f.date(d.date, { weekday: "short", month: "short", day: "numeric" }), [
      ["Revenue", `${f.usd(d.revenue_usd)}  (7d avg ${f.usd(revenue[i])})`, true],
      ["Spend", `${f.usd(d.spend_usd)}  (7d avg ${f.usd(spend[i])})`],
      ["Conversions", f.int(d.conversions)],
    ]);
  });
  overlay.addEventListener("pointerleave", () => [cross, dRev, dSpend].forEach((e) => e.setAttribute("opacity", 0)));
  svg.append(cross, dSpend, dRev, overlay);
  el.replaceChildren(svg);

  const line = (stroke) => s("svg", { viewBox: "0 -8 16 16" }, s("line", { x1: 0, x2: 16, y1: 0, y2: 0, stroke, "stroke-width": 2 }));
  $("#trend-legend").replaceChildren(
    h("span", {}, line("var(--accent)"), "Revenue"),
    h("span", {}, line("var(--text-3)"), "Spend"),
    h("span", { class: "caption", style: "margin:0" }, "7-day average")
  );

  const sum = (arr, k) => arr.reduce((a, d) => a + d[k], 0);
  const last = days.slice(-30), prev = days.slice(-60, -30);
  const change = sum(last, "revenue_usd") / sum(prev, "revenue_usd") - 1;
  $("#trend-finding").textContent =
    `${f.usd(sum(last, "revenue_usd"))} revenue on ${f.usd(sum(last, "spend_usd"))} spend over the last 30 days, ` +
    `${change >= 0 ? "+" : MINUS}${Math.abs(change * 100).toFixed(0)}% revenue vs the 30 days before`;
}

// ---------- journeys ----------
function renderJourneys() {
  const maxRate = Math.max(...D.paths.map((p) => p.conversion_rate));
  $("#paths").replaceChildren(
    h("div", { class: "path-row head" }, h("span", {}, "Path"), h("span", { class: "num" }, "Users"), h("span", {}, "Conversion rate")),
    ...D.paths.map((p) => {
      const steps = p.path.split(" > ");
      const row = h(
        "div",
        { class: "path-row" },
        h("div", { class: "path-steps" }, steps.flatMap((st, i) => [i ? h("span", { class: "sep", "aria-hidden": "true" }, "›") : null, h("span", { class: "chip" }, st)])),
        h("span", { class: "num" }, f.int(p.users)),
        h("div", { class: "rate" }, h("div", { class: "bar" }, h("i", { style: `width:${(p.conversion_rate / maxRate) * 100}%` })), h("span", {}, f.pct(p.conversion_rate)))
      );
      return withTip(row, tipRows(p.path, [
        ["Users", f.int(p.users)],
        ["Conversions", f.int(p.conversions)],
        ["Conversion rate", f.pct(p.conversion_rate, 2), true],
        ["Avg impressions", f.dec(p.avg_touches)],
      ]));
    })
  );

  const lens = D.path_lengths;
  const conv = lens.reduce((a, r) => a + r.conversions, 0);
  const multi = lens.filter((r) => r.touches >= 2).reduce((a, r) => a + r.conversions, 0) / conv;
  const one = lens.find((r) => r.touches === 1);
  const top = lens.filter((r) => r.touches >= 5).reduce((a, r) => [a[0] + r.conversions, a[1] + r.users], [0, 0]);
  $("#journey-finding").textContent =
    `${f.pct(multi, 0)} of conversions came after two or more impressions. Users who saw five or more converted at ` +
    `${f.pct(top[0] / top[1])}, against ${f.pct(one.conversion_rate)} after a single impression`;

  const el = $("#lengths");
  const W = el.clientWidth || 320;
  const H = 220, T = 20, B = 24, L = 4, R = 4;
  const maxR = Math.max(...lens.map((r) => r.conversion_rate));
  const bw = (W - L - R) / lens.length;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, height: H, role: "img", "aria-label": "Conversion rate by number of impressions seen" });
  svg.append(s("line", { class: "grid-line", x1: L, x2: W - R, y1: H - B, y2: H - B }));
  lens.forEach((r, i) => {
    const bh = (r.conversion_rate / maxR) * (H - T - B);
    const x0 = L + i * bw + 2;
    const w = Math.max(2, bw - 4);
    const y0 = H - B - bh;
    const rad = Math.min(4, w / 2, bh);
    svg.append(
      withTip(
        s("path", {
          d: `M${x0} ${H - B}V${y0 + rad}Q${x0} ${y0} ${x0 + rad} ${y0}H${x0 + w - rad}Q${x0 + w} ${y0} ${x0 + w} ${y0 + rad}V${H - B}Z`,
          fill: "var(--mark)",
        }),
        tipRows(`${r.touches}${r.is_capped ? " or more" : ""} impression${r.touches > 1 ? "s" : ""}`, [
          ["Users", f.int(r.users)],
          ["Conversions", f.int(r.conversions)],
          ["Conversion rate", f.pct(r.conversion_rate, 2), true],
        ])
      ),
      s("text", { x: x0 + w / 2, y: H - 6, "text-anchor": "middle" }, `${r.touches}${r.is_capped ? "+" : ""}`)
    );
    if (i === 0 || i === lens.length - 1) svg.append(s("text", { class: "value", x: x0 + w / 2, y: y0 - 6, "text-anchor": "middle" }, f.pct(r.conversion_rate)));
  });
  el.replaceChildren(svg);
}

// ---------- campaigns ----------
const CAMPAIGN_COLS = [
  { key: "campaign_name", label: "Campaign", render: (r) => [r.campaign_name.split(" · ")[1] ?? r.campaign_name, h("span", { class: "sub" }, r.advertiser_name)], cls: "name" },
  { key: "channel", label: "Channel" },
  { key: "spend_usd", label: "Spend", num: true, render: (r) => f.usd(r.spend_usd) },
  { key: "impressions", label: "Impressions", num: true, render: (r) => f.int(r.impressions) },
  { key: "ctr", label: "CTR", num: true, render: (r) => f.pct(r.ctr, 2) },
  { key: "conversions", label: "Conversions", num: true, render: (r) => f.dec(r.conversions) },
  { key: "revenue_usd", label: "Revenue", num: true, render: (r) => f.usd(r.revenue_usd) },
  { key: "roas", label: "ROAS", num: true, render: (r) => f.x(r.roas) },
  { key: "cpa_usd", label: "CPA", num: true, render: (r) => f.usd2(r.cpa_usd) },
];

function renderCampaigns() {
  const select = $("#campaign-model");
  if (!select.options.length) {
    select.append(...TOUCHPOINT_MODELS.map((m) => h("option", { value: m }, label(m))));
    select.addEventListener("change", () => {
      state.campaignModel = select.value;
      renderCampaigns();
    });
  }
  select.value = state.campaignModel;

  const { key, dir } = state.sort;
  const rows = D.campaigns
    .filter((r) => r.model === state.campaignModel)
    .sort((a, b) => {
      const av = a[key] ?? -Infinity, bv = b[key] ?? -Infinity;
      return (typeof av === "string" ? av.localeCompare(bv) : av - bv) * dir;
    });

  const head = h(
    "tr",
    {},
    CAMPAIGN_COLS.map((c) =>
      h(
        "th",
        { class: c.num ? "num" : null, "aria-sort": c.key === key ? (dir > 0 ? "ascending" : "descending") : null, scope: "col" },
        h(
          "button",
          {
            type: "button",
            onclick: () => {
              state.sort = { key: c.key, dir: c.key === key ? -dir : c.num ? -1 : 1 };
              renderCampaigns();
            },
          },
          c.label,
          c.key === key ? (dir > 0 ? " ↑" : " ↓") : ""
        )
      )
    )
  );
  const body = rows.map((r) =>
    h("tr", {}, CAMPAIGN_COLS.map((c) => h("td", { class: [c.num ? "num" : "", c.cls ?? "", c.key === "roas" && r.roas < 1 ? "roas-low" : ""].join(" ").trim() || null }, c.render ? c.render(r) : r[c.key])))
  );
  $("#campaign-table").replaceChildren(h("thead", {}, head), h("tbody", {}, body));
}

// ---------- pipeline health ----------
function renderPipeline() {
  const { ingestion = [], quality, dbt = {} } = D.pipeline;
  const audit = Object.fromEntries(ingestion.map((r) => [r.entity, r]));
  const landed = ingestion.reduce((a, r) => a + r.rows_loaded, 0);
  const dups = ingestion.reduce((a, r) => a + r.duplicates_dropped, 0);
  const qr = quality?.results ?? [];
  const qFail = qr.filter((r) => !r.passed && r.severity === "error").length;
  const qWarn = qr.filter((r) => !r.passed && r.severity === "warn").length;
  const tests = dbt.tests ?? [];
  const models = dbt.models ?? [];
  const failedTests = tests.filter((t) => t.status !== "pass").length;
  const pyModels = models.filter((m) => m.language === "python").length;

  const stages = [
    ["Generate", "make data", "ok", `Simulated ${f.int(D.totals.users_reached)} users' journeys with planted duplicates and late conversions`],
    ["Ingest", "python -m src.ingestion", "ok",
      `Landed ${f.int(landed)} rows in ${f.int(audit.impressions?.partitions ?? 0)} daily partitions and set aside ${f.int(dups)} duplicates`],
    ["Quality gate", "python -m src.utils.quality_checks", qFail ? "fail" : qWarn ? "warn" : "ok",
      `${qr.length - qFail - qWarn} of ${qr.length} checks passed${qWarn ? `, ${qWarn} warning${qWarn > 1 ? "s" : ""}` : ""}${qFail ? `, ${qFail} failed` : ""}`],
    ["Transform", "dbt build", failedTests ? "fail" : "ok",
      `${models.length} models (${pyModels} in Python) and ${tests.length} tests on DuckDB in ${dbt.elapsed_seconds}s`],
    ["Export", "python -m src.export", "ok", `Wrote this page's data on ${f.date(D.meta.generated_at, { month: "short", day: "numeric", year: "numeric" })}`],
  ];
  $("#stages").replaceChildren(
    ...stages.map(([name, cmd, status, text]) =>
      h("li", { class: "stage" }, h("div", { class: "stage-name" }, h("span", { class: `status-dot ${status === "ok" ? "" : status}`, "aria-label": status }), name), h("code", {}, cmd), h("p", {}, text))
    )
  );

  const dotFor = (st) => h("span", { class: `status-dot ${st === "pass" ? "" : st === "warn" ? "warn" : "fail"}`, "aria-label": st });
  const singular = tests.filter((t) => t.kind === "singular");
  const generic = tests.filter((t) => t.kind === "generic");
  $("#dbt-caption").textContent = `${tests.length - failedTests} of ${tests.length} passed · dbt ${dbt.dbt_version ?? ""}`;
  $("#dbt-tests").replaceChildren(
    ...singular.map((t) =>
      h("li", {}, dotFor(t.status), h("span", { class: "what" }, t.name.replace(/^assert_/, "").replaceAll("_", " ")), h("span", { class: "tag" }, t.status), t.description ? h("span", { class: "detail" }, t.description.replace(/\.$/, "")) : null)
    ),
    h(
      "li",
      {},
      dotFor(generic.every((t) => t.status === "pass") ? "pass" : "fail"),
      h(
        "details",
        {},
        h("summary", {}, `${generic.length} schema tests: unique, not null, accepted values, relationships`),
        h("div", { class: "generic-list" }, generic.map((t) => h("div", {}, t.name)))
      )
    )
  );

  $("#quality-caption").textContent = quality
    ? `${qr.filter((r) => r.passed).length} of ${qr.length} passed on ${quality.partition_date ? `partition ${quality.partition_date}` : "every partition"}. Warnings are reported, errors stop the run`
    : "No quality report found";
  const rank = (r) => (r.passed ? 2 : r.severity === "warn" ? 1 : 0);
  $("#quality-checks").replaceChildren(
    ...qr
      .filter((r) => r.check !== "schema" && r.check !== "rows present")
      .sort((a, b) => rank(a) - rank(b))
      .map((r) =>
        withTip(
          h(
            "li",
            { class: "compact" },
            dotFor(r.passed ? "pass" : r.severity === "warn" ? "warn" : "fail"),
            h("span", { class: "what" }, `${r.entity} · ${r.check}`),
            h("span", { class: "tag" }, r.observed.replace(/ \(.*\)$/, ""))
          ),
          tipRows(`${r.entity} · ${r.check}`, [["Observed", r.observed, true], ["Expected", r.expected], ["Severity", r.severity]])
        )
      )
  );
}

// ---------- Day / Night ----------
function themeToggle() {
  const buttons = [...document.querySelectorAll("[data-theme-choice]")];
  const sync = () => {
    const night = document.documentElement.dataset.theme === "night";
    buttons.forEach((b) => b.setAttribute("aria-pressed", String((b.dataset.themeChoice === "night") === night)));
  };
  buttons.forEach((b) =>
    b.addEventListener("click", () => {
      const choice = b.dataset.themeChoice;
      if (choice === "night") document.documentElement.dataset.theme = "night";
      else delete document.documentElement.dataset.theme;
      try { localStorage.setItem("attribution.theme", choice); } catch { /* storage blocked: the choice lasts for this visit */ }
      sync();
    })
  );
  sync();
}

// ---------- page ----------
function spy() {
  const links = [...document.querySelectorAll(".nav a")];
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${e.target.id}`));
      }
    },
    { rootMargin: "-30% 0px -60% 0px" }
  );
  document.querySelectorAll(".section").forEach((sec) => io.observe(sec));
}

function renderCharts() {
  renderCalibration();
  renderTrend();
  renderJourneys();
}

async function main() {
  const res = await fetch("data/dashboard.json", { cache: "no-cache" });
  D = await res.json();
  renderHeader();
  renderPicker();
  renderAccuracy();
  renderCharts();
  renderRoas();
  renderCampaigns();
  renderPipeline();
  themeToggle();
  spy();
  let t;
  new ResizeObserver(() => {
    clearTimeout(t);
    t = setTimeout(renderCharts, 120);
  }).observe($(".content"));
}

main().catch((err) => {
  $("#stats").replaceChildren(h("p", { class: "finding" }, `Could not load data/dashboard.json: ${err.message}. Run make pipeline.`));
  console.error(err);
});
