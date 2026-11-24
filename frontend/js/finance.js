/* 💰 Financeiro (só a clínica): resumo do ano, sessões a receber, pacotes, despesas e terapias/preços.
 * Usa as funções do painel expostas em window.AjnaAdmin (admin.js). Valores em centavos na API.
 */
(() => {
  "use strict";
  const A = () => window.AjnaAdmin;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (v) => A().esc(v);
  const brl = (c) => (Number(c || 0) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  const toCents = (txt) => {
    const t = String(txt ?? "").trim().replace(/[R$\s]/g, "");
    if (!t) return null;
    const n = Number(t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t);
    return Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : NaN;
  };
  const centsToInput = (c) => (c || c === 0 ? (c / 100).toFixed(2).replace(".", ",") : "");
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const dateBR = (s) => (s ? s.slice(0, 10).split("-").reverse().join("/") : "");
  const MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
  const FIN_STATUS = {
    paid: ["Pago", "done"], partial: ["Pago em parte", "requested"], pending: ["A receber", "cancelled"],
    package: ["Pacote", "scheduled"], upcoming: ["Agendada", ""], no_price: ["Sem valor", ""], cancelled: ["Cancelada", ""],
  };

  const st = { tab: "summary", year: new Date().getFullYear(), month: new Date(), opts: null, services: [], patients: [] };

  async function boot() {
    if (!st.opts) st.opts = await A().api("/api/admin/finance/options");
    st.services = (await A().api("/api/admin/services")).items;
  }

  const monthRange = () => {
    const y = st.month.getFullYear(), m = st.month.getMonth();
    return [iso(new Date(y, m, 1)), iso(new Date(y, m + 1, 0))];
  };
  const monthLabel = () => {
    const s = st.month.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
    return s.charAt(0).toUpperCase() + s.slice(1);
  };

  async function load() {
    await boot();
    $$("[data-fin-tab]").forEach((b) => b.classList.toggle("is-active", b.dataset.finTab === st.tab));
    const yearTab = st.tab === "summary";
    const noPeriod = ["services", "packages", "report"].includes(st.tab);
    $("#fin-period").hidden = noPeriod;
    $("#fin-label").textContent = yearTab ? String(st.year) : monthLabel();
    const box = $("#fin-body");
    box.innerHTML = '<p class="adm-muted">Carregando…</p>';
    const render = { summary: renderSummary, sessions: renderSessions, packages: renderPackages,
      expenses: renderExpenses, services: renderServices, report: renderReport }[st.tab];
    box.innerHTML = await render();
  }

  // ---------------------------------------------------------------- resumo (ano)
  async function renderSummary() {
    const s = await A().api(`/api/admin/finance/summary?year=${st.year}`);
    st.summary = s;
    const list = (obj, labels = {}) => Object.entries(obj).sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `<li><span>${esc(labels[k] || k)}</span><b>${brl(v)}</b></li>`).join("") || '<li class="adm-muted">Nada no período.</li>';
    const rows = s.months.map((m, i) => `<tr><td>${MONTHS[i]}</td><td class="fin-in">${brl(m.income_cents)}</td>
      <td class="fin-out">${brl(m.expense_cents)}</td><td class="${m.balance_cents < 0 ? "fin-out" : "fin-in"}">${brl(m.balance_cents)}</td></tr>`).join("");
    return `
      <div class="adm-stats fin-stats">
        <article class="adm-stat"><span>Entradas em ${s.year}</span><strong class="fin-in">${brl(s.income_cents)}</strong></article>
        <article class="adm-stat"><span>Despesas em ${s.year}</span><strong class="fin-out">${brl(s.expense_cents)}</strong></article>
        <article class="adm-stat"><span>Saldo do ano</span><strong class="${s.balance_cents < 0 ? "fin-out" : "fin-in"}">${brl(s.balance_cents)}</strong></article>
        <article class="adm-stat fin-stat--social"><span>🤝 Ambulatório Social em ${s.year}</span><strong>${s.social.sessions} sessão(ões)</strong>
          <small>${s.social.patients} paciente(s) · ${brl(s.social.income_cents)} recebidos</small></article>
        <article class="adm-stat fin-stat--link" data-fin-goto="sessions"><span>A receber (${s.receivable_count} sessão(ões))</span><strong class="fin-warn">${brl(s.receivable_cents)}</strong></article>
      </div>
      <div class="adm-grid">
        <section class="adm-card">
          <div class="adm-card__head"><h2 id="fin-chart-title">${CHARTS[st.chart] || CHARTS.bars}</h2></div>
          <div class="fin-chart-picker" role="tablist" aria-label="Escolha o gráfico">${Object.entries(CHARTS).map(([k, v]) =>
            `<button class="adm-btn adm-btn--sm ${k === st.chart ? "is-active" : ""}" data-fin-chart="${k}" type="button">${v}</button>`).join("")}</div>
          <div id="fin-chart-box">${chartHtml(s)}</div>
          <div class="fin-table-wrap"><table class="fin-table"><thead><tr><th>Mês</th><th>Entradas</th><th>Despesas</th><th>Saldo</th></tr></thead><tbody>${rows}</tbody></table></div>
        </section>
        <div class="fin-side">
          <section class="adm-card"><div class="adm-card__head"><h2>Recebido por forma</h2></div><ul class="fin-list">${list(s.by_method, st.opts.methods)}</ul></section>
          <section class="adm-card"><div class="adm-card__head"><h2>Despesas por categoria</h2></div><ul class="fin-list">${list(s.by_category)}</ul></section>
        </div>
      </div>`;
  }

  // ---------------------------------------------------------------- gráficos (SVG, sem bibliotecas)
  const PALETTE = ["#7800b4", "#2f9e5b", "#e08a1e", "#d9566f", "#2a7fd4", "#14a3a3", "#bd72e2", "#8a6d3b", "#5b5b7a", "#c2185b"];
  const CHARTS = {
    bars: "📊 Entradas x despesas (mês a mês)",
    balance: "📈 Saldo acumulado no ano",
    category: "🍩 Despesas por categoria",
    method: "🍩 Recebido por forma de pagamento",
    service: "🍩 Receita por terapia",
    social: "🍩 Particular x Ambulatório Social",
    net: "📊 Resultado de cada mês (lucro / prejuízo)",
  };
  st.chart = localStorage.getItem("ajna-fin-chart") || "bars";

  const short = (c) => {
    const v = c / 100;
    return v >= 1000 ? `R$ ${(v / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil` : `R$ ${v.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}`;
  };

  function svgBars(series, { colors, labels, signed = false }) {
    const W = 640, H = 240, P = { l: 58, r: 10, t: 12, b: 26 };
    const vals = series.flat();
    const max = Math.max(1, ...vals.map(Math.abs));
    const min = signed ? -max : 0;
    const y = (v) => P.t + (H - P.t - P.b) * (1 - (v - min) / (max - min));
    const n = labels.length, slot = (W - P.l - P.r) / n, bw = Math.min(22, (slot - 8) / series.length);
    const grid = [0, .25, .5, .75, 1].map((f) => min + (max - min) * f).map((v) =>
      `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" class="ch-grid"/><text x="${P.l - 6}" y="${y(v) + 4}" class="ch-ax" text-anchor="end">${short(v)}</text>`).join("");
    const bars = labels.map((lab, i) => series.map((s, k) => {
      const v = s[i], x = P.l + slot * i + (slot - bw * series.length) / 2 + bw * k;
      const top = Math.min(y(v), y(0)), h = Math.max(1, Math.abs(y(v) - y(0)));
      const color = typeof colors[k] === "function" ? colors[k](v) : colors[k];
      return `<rect x="${x}" y="${top}" width="${bw - 2}" height="${h}" rx="3" fill="${color}"><title>${lab}: ${brl(v)}</title></rect>`;
    }).join("") + `<text x="${P.l + slot * i + slot / 2}" y="${H - 8}" class="ch-ax" text-anchor="middle">${lab}</text>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}" class="fin-svg" role="img">${grid}<line x1="${P.l}" x2="${W - P.r}" y1="${y(0)}" y2="${y(0)}" class="ch-zero"/>${bars}</svg>`;
  }

  function svgLine(values, labels) {
    const W = 640, H = 240, P = { l: 58, r: 14, t: 14, b: 26 };
    const max = Math.max(1, ...values), min = Math.min(0, ...values);
    const x = (i) => P.l + ((W - P.l - P.r) / (labels.length - 1)) * i;
    const y = (v) => P.t + (H - P.t - P.b) * (1 - (v - min) / (max - min || 1));
    const pts = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
    const grid = [0, .25, .5, .75, 1].map((f) => min + (max - min) * f).map((v) =>
      `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" class="ch-grid"/><text x="${P.l - 6}" y="${y(v) + 4}" class="ch-ax" text-anchor="end">${short(v)}</text>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}" class="fin-svg" role="img">${grid}
      <line x1="${P.l}" x2="${W - P.r}" y1="${y(0)}" y2="${y(0)}" class="ch-zero"/>
      <polygon points="${x(0)},${y(0)} ${pts} ${x(values.length - 1)},${y(0)}" fill="rgba(120,0,180,.10)"/>
      <polyline points="${pts}" fill="none" stroke="#7800b4" stroke-width="3" stroke-linejoin="round"/>
      ${values.map((v, i) => `<circle cx="${x(i)}" cy="${y(v)}" r="4.5" fill="${v < 0 ? "#d9566f" : "#7800b4"}"><title>${labels[i]}: ${brl(v)}</title></circle>
        <text x="${x(i)}" y="${H - 8}" class="ch-ax" text-anchor="middle">${labels[i]}</text>`).join("")}</svg>`;
  }

  function svgDonut(entries) {
    const total = entries.reduce((t, [, v]) => t + v, 0);
    if (!total) return '<p class="adm-empty">Nada lançado neste ano ainda.</p>';
    const R = 80, r = 50, C = 100;
    let a0 = -Math.PI / 2;
    const arcs = entries.map(([label, v], i) => {
      const a1 = a0 + (v / total) * Math.PI * 2;
      const big = a1 - a0 > Math.PI ? 1 : 0;
      const p = (a, rad) => `${C + rad * Math.cos(a)},${C + rad * Math.sin(a)}`;
      const d = entries.length === 1
        ? `M ${C} ${C - R} A ${R} ${R} 0 1 1 ${C - .01} ${C - R} L ${C - .01} ${C - r} A ${r} ${r} 0 1 0 ${C} ${C - r} Z`
        : `M ${p(a0, R)} A ${R} ${R} 0 ${big} 1 ${p(a1, R)} L ${p(a1, r)} A ${r} ${r} 0 ${big} 0 ${p(a0, r)} Z`;
      a0 = a1;
      return `<path d="${d}" fill="${PALETTE[i % PALETTE.length]}"><title>${esc(label)}: ${brl(v)}</title></path>`;
    }).join("");
    const legend = entries.map(([label, v], i) => `<li><i style="background:${PALETTE[i % PALETTE.length]}"></i>
      <span>${esc(label)}</span><b>${brl(v)}</b><em>${Math.round((v / total) * 100)}%</em></li>`).join("");
    return `<div class="fin-donut"><svg viewBox="0 0 200 200" role="img">${arcs}
      <text x="100" y="96" text-anchor="middle" class="ch-total-l">Total</text><text x="100" y="116" text-anchor="middle" class="ch-total">${short(total)}</text></svg>
      <ul class="fin-donut__legend">${legend}</ul></div>`;
  }

  function chartHtml(s) {
    const labels = MONTHS;
    const sorted = (obj, names = {}) => Object.entries(obj).map(([k, v]) => [names[k] || k, v]).sort((a, b) => b[1] - a[1]);
    switch (st.chart) {
      case "balance": {
        let acc = 0;
        return svgLine(s.months.map((m) => (acc += m.balance_cents)), labels);
      }
      case "category": return svgDonut(sorted(s.by_category));
      case "method": return svgDonut(sorted(s.by_method, st.opts.methods));
      case "service": return svgDonut(sorted(s.by_service));
      case "social": return svgDonut([["Particular", s.social_split.private], ["🤝 Ambulatório Social", s.social_split.social]].filter(([, v]) => v));
      case "net": return svgBars([s.months.map((m) => m.balance_cents)], { labels, signed: true, colors: [(v) => (v < 0 ? "#d9566f" : "#2f9e5b")] });
      default: return `<span class="fin-legend"><i class="fin-bar__in"></i> Entradas <i class="fin-bar__out"></i> Despesas</span>` +
        svgBars([s.months.map((m) => m.income_cents), s.months.map((m) => m.expense_cents)], { labels, colors: ["#2f9e5b", "#d9566f"] });
    }
  }

  // ---------------------------------------------------------------- relatórios (filtros + Excel/PDF)
  const yStart = () => `${new Date().getFullYear()}-01-01`;
  st.rep = { from: yStart(), to: iso(new Date()), kind: "all", method: "", category: "", service_id: "", patient_id: "", origin: "", social: "" };
  const KIND = { all: "Entradas e despesas", income: "Só entradas", expense: "Só despesas" };

  function repQuery() {
    const q = new URLSearchParams();
    Object.entries(st.rep).forEach(([k, v]) => { if (v) q.set(k, v); });
    return q.toString();
  }

  function repFiltersText() {
    const r = st.rep, out = [`Período: ${dateBR(r.from)} a ${dateBR(r.to)}`, KIND[r.kind]];
    if (r.method) out.push(`Forma: ${st.opts.methods[r.method]}`);
    if (r.category) out.push(`Categoria: ${r.category}`);
    if (r.service_id) out.push(`Terapia: ${st.services.find((s) => s.id == r.service_id)?.name || ""}`);
    if (r.patient_id) out.push(`Cliente: ${st.patients.find((p) => p.id == r.patient_id)?.name || ""}`);
    if (r.origin) out.push(`Origem: ${r.origin}`);
    if (r.social) out.push("Só Ambulatório Social");
    return out.join(" · ");
  }

  async function renderReport() {
    if (!st.patients.length) st.patients = await A().patients();
    const r = st.rep;
    const data = await A().api(`/api/admin/finance/report?${repQuery()}`);
    st.repData = data;
    const sel = (name, options, empty = "Todas") => `<select name="${name}"><option value="">${empty}</option>${options
      .map(([v, l]) => `<option value="${esc(v)}" ${String(r[name]) === String(v) ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;
    const rows = data.items.map((x) => `<tr>
      <td>${dateBR(x.date)}</td>
      <td><span class="adm-badge ${x.type === "income" ? "adm-badge--done" : "adm-badge--cancelled"}">${x.type === "income" ? "Entrada" : "Despesa"}</span></td>
      <td>${esc(x.type === "income" ? x.patient || "—" : x.category)}</td>
      <td>${x.social ? "🤝 " : ""}${esc(x.service || (x.type === "income" ? x.origin : ""))}${x.description ? `<small>${esc(x.description)}</small>` : ""}</td>
      <td>${esc(x.type === "income" ? x.origin : "—")}</td>
      <td>${esc(st.opts.methods[x.method] || "—")}</td>
      <td class="num ${x.type === "income" ? "fin-in" : "fin-out"}">${x.type === "expense" ? "−" : ""}${brl(x.amount_cents)}</td></tr>`).join("");
    return `
      <section class="adm-card">
        <div class="adm-card__head"><h2>📄 Relatório financeiro</h2></div>
        <form class="fin-filters" id="fin-rep-form">
          <label>De<input type="date" name="from" value="${r.from}" required></label>
          <label>Até<input type="date" name="to" value="${r.to}" required></label>
          <label>Tipo${sel("kind", Object.entries(KIND).slice(1), "Entradas e despesas")}</label>
          <label>Forma de pagamento${sel("method", Object.entries(st.opts.methods))}</label>
          <label>Categoria (despesa)${sel("category", st.opts.expense_categories.map((c) => [c, c]))}</label>
          <label>Terapia (entrada)${sel("service_id", st.services.map((s) => [s.id, s.name]))}</label>
          <label>Cliente${sel("patient_id", st.patients.map((p) => [p.id, p.name]), "Todos")}</label>
          <label>Origem da entrada${sel("origin", [["Sessão", "Sessão"], ["Pacote", "Pacote"], ["Avulso", "Avulso"]])}</label>
          <label class="ag-check fin-filters__check"><input type="checkbox" name="social" value="1" ${r.social ? "checked" : ""}> 🤝 Só Ambulatório Social</label>
          <div class="fin-filters__quick">
            <span class="adm-muted">Atalhos:</span>
            <button class="adm-btn adm-btn--sm" data-rep-range="month" type="button">Este mês</button>
            <button class="adm-btn adm-btn--sm" data-rep-range="last" type="button">Mês passado</button>
            <button class="adm-btn adm-btn--sm" data-rep-range="year" type="button">Este ano</button>
            <button class="adm-btn adm-btn--sm" data-rep-range="clear" type="button">Limpar filtros</button>
          </div>
          <div class="fin-filters__actions">
            <button class="adm-btn adm-btn--primary" type="submit">🔎 Aplicar filtros</button>
            <button class="adm-btn" data-rep-export="csv" type="button">⬇️ Baixar planilha (Excel)</button>
            <button class="adm-btn" data-rep-export="pdf" type="button">🖨️ Imprimir / PDF</button>
          </div>
        </form>
      </section>
      <div class="adm-stats fin-stats">
        <article class="adm-stat"><span>Entradas</span><strong class="fin-in">${brl(data.income_cents)}</strong></article>
        <article class="adm-stat"><span>Despesas</span><strong class="fin-out">${brl(data.expense_cents)}</strong></article>
        <article class="adm-stat"><span>Saldo do período</span><strong class="${data.balance_cents < 0 ? "fin-out" : "fin-in"}">${brl(data.balance_cents)}</strong></article>
        <article class="adm-stat"><span>Lançamentos</span><strong>${data.items.length}</strong></article>
      </div>
      <section class="adm-card">
        <p class="adm-muted fin-help">${esc(repFiltersText())}</p>
        <div class="fin-table-wrap"><table class="fin-table fin-table--rep">
          <thead><tr><th>Data</th><th>Tipo</th><th>Cliente / categoria</th><th>Terapia / descrição</th><th>Origem</th><th>Forma</th><th class="num">Valor</th></tr></thead>
          <tbody>${rows || '<tr><td colspan="7" class="adm-muted">Nada encontrado com esses filtros.</td></tr>'}</tbody>
        </table></div>
      </section>`;
  }

  function exportReport(kind) {
    const d = st.repData;
    if (!d) return;
    const lines = d.items.map((x) => [
      dateBR(x.date), x.type === "income" ? "Entrada" : "Despesa",
      x.type === "income" ? x.patient || "" : x.category, x.service || "", x.type === "income" ? x.origin : "",
      st.opts.methods[x.method] || "", x.social ? "Sim" : "", x.description || "",
      ((x.type === "expense" ? -1 : 1) * x.amount_cents / 100).toFixed(2).replace(".", ","),
    ]);
    if (kind === "csv") {
      window.AjnaPrint.csv(`ajna-financeiro_${st.rep.from}_a_${st.rep.to}.csv`, [
        ["Relatório financeiro — Ajna Terapias"], [repFiltersText()], [],
        ["Data", "Tipo", "Cliente / categoria", "Terapia", "Origem", "Forma de pagamento", "Ambulatório Social", "Descrição", "Valor (R$)"],
        ...lines, [],
        ["", "", "", "", "", "", "", "Total de entradas", (d.income_cents / 100).toFixed(2).replace(".", ",")],
        ["", "", "", "", "", "", "", "Total de despesas", (-d.expense_cents / 100).toFixed(2).replace(".", ",")],
        ["", "", "", "", "", "", "", "Saldo", (d.balance_cents / 100).toFixed(2).replace(".", ",")],
      ]);
      return;
    }
    // agrupamentos para o PDF
    const group = (pick, type) => {
      const m = {};
      d.items.filter((x) => x.type === type).forEach((x) => { const k = pick(x) || "—"; m[k] = (m[k] || 0) + x.amount_cents; });
      return Object.entries(m).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${brl(v)}</td></tr>`).join("");
    };
    const E = window.AjnaPrint.esc;
    window.AjnaPrint.open({
      title: "Relatório financeiro",
      subtitle: `${dateBR(st.rep.from)} a ${dateBR(st.rep.to)}`,
      html: `<p class="filters">${E(repFiltersText())}</p>
        <div class="totals"><div><span>Entradas</span><b class="in">${brl(d.income_cents)}</b></div>
          <div><span>Despesas</span><b class="out">${brl(d.expense_cents)}</b></div>
          <div><span>Saldo</span><b class="${d.balance_cents < 0 ? "out" : "in"}">${brl(d.balance_cents)}</b></div>
          <div><span>Lançamentos</span><b>${d.items.length}</b></div></div>
        ${d.income_cents ? `<h2>Entradas por terapia</h2><table>${group((x) => x.service || "Avulso / sem terapia", "income")}</table>
          <h2>Entradas por forma de pagamento</h2><table>${group((x) => st.opts.methods[x.method], "income")}</table>` : ""}
        ${d.expense_cents ? `<h2>Despesas por categoria</h2><table>${group((x) => x.category, "expense")}</table>` : ""}
        <h2>Lançamentos</h2>
        <table><thead><tr><th>Data</th><th>Tipo</th><th>Cliente / categoria</th><th>Terapia</th><th>Origem</th><th>Forma</th><th class="num">Valor</th></tr></thead>
        <tbody>${d.items.map((x) => `<tr><td>${dateBR(x.date)}</td><td>${x.type === "income" ? "Entrada" : "Despesa"}</td>
          <td>${E(x.type === "income" ? x.patient || "—" : x.category)}${x.description ? `<br><span class="muted">${E(x.description)}</span>` : ""}</td>
          <td>${x.social ? "🤝 " : ""}${E(x.service || "")}</td><td>${E(x.type === "income" ? x.origin : "")}</td>
          <td>${E(st.opts.methods[x.method] || "—")}</td>
          <td class="num ${x.type === "income" ? "in" : "out"}">${x.type === "expense" ? "−" : ""}${brl(x.amount_cents)}</td></tr>`).join("")
          || '<tr><td colspan="7" class="muted">Nada encontrado.</td></tr>'}</tbody></table>`,
    });
  }

  document.addEventListener("submit", (e) => {
    if (e.target.id !== "fin-rep-form") return;
    e.preventDefault();
    const f = new FormData(e.target);
    Object.keys(st.rep).forEach((k) => { st.rep[k] = f.get(k) || ""; });
    if (!st.rep.kind) st.rep.kind = "all";
    if (st.rep.from > st.rep.to) return A().toast("A data inicial precisa ser antes da final.", true);
    load();
  });
  document.addEventListener("click", (e) => {
    const q = e.target.closest("[data-rep-range]");
    if (q) {
      const now = new Date(), y = now.getFullYear(), m = now.getMonth();
      const r = q.dataset.repRange;
      if (r === "clear") st.rep = { ...st.rep, kind: "all", method: "", category: "", service_id: "", patient_id: "", origin: "", social: "" };
      else {
        const [a, b] = r === "month" ? [new Date(y, m, 1), new Date(y, m + 1, 0)]
          : r === "last" ? [new Date(y, m - 1, 1), new Date(y, m, 0)] : [new Date(y, 0, 1), new Date(y, 11, 31)];
        st.rep.from = iso(a);
        st.rep.to = iso(b);
      }
      return void load();
    }
    const x = e.target.closest("[data-rep-export]");
    if (x) exportReport(x.dataset.repExport);
    const c = e.target.closest("[data-fin-chart]");
    if (c) {
      st.chart = c.dataset.finChart;
      localStorage.setItem("ajna-fin-chart", st.chart);
      $$("[data-fin-chart]").forEach((b) => b.classList.toggle("is-active", b === c));
      $("#fin-chart-box").innerHTML = chartHtml(st.summary);
      $("#fin-chart-title").textContent = CHARTS[st.chart];
    }
  });

  // ---------------------------------------------------------------- sessões do mês + a receber
  async function renderSessions() {
    const [from, to] = monthRange();
    const [{ items }, rec, pays] = await Promise.all([
      A().api(`/api/admin/finance/sessions?from=${from}&to=${to}`),
      A().api("/api/admin/finance/receivable"),
      A().api(`/api/admin/finance/payments?from=${from}&to=${to}`),
    ]);
    st.sessions = [...items, ...rec.items];
    const row = (s, showDate = true) => {
      const [label, cls] = FIN_STATUS[s.finance_status] || ["", ""];
      return `<div class="fin-row">
        <span class="fin-row__when">${showDate ? dateBR(s.date) + " · " : ""}${esc(s.start)}</span>
        <span class="fin-row__who"><b>${esc(s.patient_name)}</b><small>${s.social ? "🤝 " : ""}${esc(s.service_name || "Sem terapia definida")}</small></span>
        <span class="fin-row__val">${s.price_cents ? brl(s.price_cents) : "—"}${s.paid_cents && s.finance_status !== "paid" ? `<small>pago ${brl(s.paid_cents)}</small>` : ""}</span>
        <span class="adm-badge ${cls ? `adm-badge--${cls}` : ""}">${label}</span>
        <span class="fin-row__act">
          ${["pending", "partial", "upcoming"].includes(s.finance_status) ? `<button class="adm-btn adm-btn--sm ${s.finance_status === "upcoming" ? "" : "adm-btn--confirm"}" data-fin-pay="${s.id}" type="button">💰 Receber ${brl(s.due_cents)}</button>` : ""}
          ${["no_price", "pending", "partial", "upcoming"].includes(s.finance_status) ? `<button class="adm-btn adm-btn--sm" data-fin-price="${s.id}" type="button">Terapia/valor</button>` : ""}
        </span>
      </div>`;
    };
    const monthTotal = items.filter((s) => s.status !== "cancelled" && !s.package_id).reduce((t, s) => t + (s.price_cents || 0), 0);
    const recvd = pays.items.reduce((t, p) => t + p.amount_cents, 0);
    return `
      <div class="adm-stats fin-stats">
        <article class="adm-stat"><span>Recebido no mês</span><strong class="fin-in">${brl(recvd)}</strong></article>
        <article class="adm-stat"><span>Valor das sessões do mês</span><strong>${brl(monthTotal)}</strong></article>
        <article class="adm-stat"><span>Total a receber (todas)</span><strong class="fin-warn">${brl(rec.total_cents)}</strong></article>
      </div>
      ${rec.items.length ? `<section class="adm-card fin-due"><div class="adm-card__head"><h2>⏳ Sessões realizadas a receber</h2></div>
        <div class="fin-rows">${rec.items.map((s) => row(s)).join("")}</div></section>` : ""}
      <section class="adm-card"><div class="adm-card__head"><h2>Sessões de ${esc(monthLabel())}</h2>
        <button class="adm-btn adm-btn--primary" data-fin-new="payment" type="button">＋ Registrar recebimento</button></div>
        <div class="fin-rows">${items.map((s) => row(s)).join("") || '<p class="adm-empty">Nenhuma sessão neste mês.</p>'}</div></section>
      <section class="adm-card"><div class="adm-card__head"><h2>Recebimentos de ${esc(monthLabel())}</h2></div>
        <div class="fin-rows">${pays.items.map((p) => `<div class="fin-row">
          <span class="fin-row__when">${dateBR(p.date)}</span>
          <span class="fin-row__who"><b>${esc(p.patient_name || "—")}</b><small>${esc(p.description || (p.package_id ? "Pacote" : p.appointment_id ? "Sessão" : "Avulso"))}</small></span>
          <span class="fin-row__val fin-in">${brl(p.amount_cents)}</span>
          <span class="adm-badge">${esc(st.opts.methods[p.method] || p.method)}</span>
          <span class="fin-row__act"><button class="adm-btn adm-btn--sm" data-fin-del="payments/${p.id}" type="button">Excluir</button></span>
        </div>`).join("") || '<p class="adm-empty">Nenhum recebimento neste mês.</p>'}</div></section>`;
  }

  // ---------------------------------------------------------------- pacotes
  async function renderPackages() {
    const { items } = await A().api("/api/admin/finance/packages");
    return `<section class="adm-card"><div class="adm-card__head"><h2>Pacotes de sessões</h2>
        <button class="adm-btn adm-btn--primary" data-fin-new="package" type="button">＋ Novo pacote</button></div>
      <p class="adm-muted fin-help">Quando uma sessão do cliente é marcada como <b>realizada</b>, ela é descontada automaticamente do pacote
        (da mesma terapia, ou de um pacote sem terapia definida). Cancelar a sessão devolve a sessão ao pacote.</p>
      <div class="fin-rows">${items.map((k) => {
        const left = k.sessions_total - k.sessions_used;
        const pct = Math.min(100, (k.sessions_used / k.sessions_total) * 100);
        return `<div class="fin-row fin-pack">
          <span class="fin-row__who"><b>${esc(k.patient_name)}</b><small>${esc(k.service_name || "Qualquer terapia")} · desde ${dateBR(k.created_at)}${k.notes ? ` · ${esc(k.notes)}` : ""}</small></span>
          <span class="fin-pack__bar"><i style="width:${pct}%"></i><small>${k.sessions_used} de ${k.sessions_total} usadas · ${left > 0 ? `<b>${left} restante(s)</b>` : "<b>concluído</b>"}</small></span>
          <span class="fin-row__val">${brl(k.price_cents)}${k.paid_cents < k.price_cents ? `<small class="fin-warn">falta ${brl(k.price_cents - k.paid_cents)}</small>` : '<small class="fin-in">pago</small>'}</span>
          <span class="fin-row__act">
            ${k.paid_cents < k.price_cents ? `<button class="adm-btn adm-btn--sm adm-btn--confirm" data-fin-paypack="${k.id}" data-amount="${k.price_cents - k.paid_cents}" data-patient="${k.patient_user_id}" type="button">💰 Receber</button>` : ""}
            ${!k.sessions_used ? `<button class="adm-btn adm-btn--sm" data-fin-del="packages/${k.id}" type="button">Excluir</button>` : ""}
          </span>
        </div>`;
      }).join("") || '<p class="adm-empty">Nenhum pacote vendido ainda.</p>'}</div></section>`;
  }

  // ---------------------------------------------------------------- despesas
  async function renderExpenses() {
    const [from, to] = monthRange();
    const { items } = await A().api(`/api/admin/finance/expenses?from=${from}&to=${to}`);
    const total = items.reduce((t, e) => t + e.amount_cents, 0);
    return `<div class="adm-stats fin-stats"><article class="adm-stat"><span>Despesas de ${esc(monthLabel())}</span><strong class="fin-out">${brl(total)}</strong></article></div>
      <section class="adm-card"><div class="adm-card__head"><h2>Despesas</h2>
        <button class="adm-btn adm-btn--primary" data-fin-new="expense" type="button">＋ Nova despesa</button></div>
      <div class="fin-rows">${items.map((e) => `<div class="fin-row">
        <span class="fin-row__when">${dateBR(e.date)}</span>
        <span class="fin-row__who"><b>${esc(e.category)}</b><small>${esc(e.description || "")}</small></span>
        <span class="fin-row__val fin-out">${brl(e.amount_cents)}</span>
        <span class="adm-badge">${esc(st.opts.methods[e.method] || "—")}</span>
        <span class="fin-row__act"><button class="adm-btn adm-btn--sm" data-fin-del="expenses/${e.id}" type="button">Excluir</button></span>
      </div>`).join("") || '<p class="adm-empty">Nenhuma despesa neste mês.</p>'}</div></section>`;
  }

  // ---------------------------------------------------------------- terapias e preços
  async function renderServices() {
    return `<section class="adm-card"><div class="adm-card__head"><h2>Terapias e preços</h2>
        <button class="adm-btn adm-btn--primary" data-fin-new="service" type="button">＋ Nova terapia</button></div>
      <p class="adm-muted fin-help">O preço da terapia é sugerido ao agendar. Dá para mudar o valor de uma sessão específica.</p>
      <div class="fin-rows">${st.services.map((s) => `<div class="fin-row ${s.active ? "" : "is-off"}">
        <span class="fin-row__who"><b>${s.social ? "🤝 " : ""}${esc(s.name)}</b><small>${s.active ? "Ativa" : "Desativada"}${s.social ? " · Ambulatório Social" : ""}</small></span>
        <span class="fin-row__val">${s.price_cents ? brl(s.price_cents) : '<span class="fin-warn">definir preço</span>'}</span>
        <span class="fin-row__act">
          <button class="adm-btn adm-btn--sm" data-fin-edit-service="${s.id}" type="button">Editar</button>
          <button class="adm-btn adm-btn--sm" data-fin-toggle-service="${s.id}" type="button">${s.active ? "Desativar" : "Ativar"}</button>
        </span>
      </div>`).join("")}</div></section>`;
  }

  // ---------------------------------------------------------------- janelas (formulários)
  const modal = () => $("#fin-modal");
  async function patientsOptions(selected) {
    if (!st.patients.length) st.patients = await A().patients();
    return '<option value="">Escolha…</option>' + st.patients.filter((p) => p.active || p.id == selected)
      .map((p) => `<option value="${p.id}" ${p.id == selected ? "selected" : ""}>${esc(p.name)}</option>`).join("");
  }
  const methodOptions = (sel = "pix", empty = false) => (empty ? '<option value="">—</option>' : "") +
    Object.entries(st.opts.methods).map(([k, v]) => `<option value="${k}" ${k === sel ? "selected" : ""}>${esc(v)}</option>`).join("");
  const serviceOptions = (sel, empty = "Escolha…") => `<option value="">${empty}</option>` +
    st.services.filter((s) => s.active || s.id == sel).map((s) => `<option value="${s.id}" data-price="${s.price_cents}" ${s.id == sel ? "selected" : ""}>${s.social ? "🤝 " : ""}${esc(s.name)}</option>`).join("");

  function openForm(title, fields, onSave) {
    const m = modal();
    $("#fin-modal-title").textContent = title;
    $("#fin-fields").innerHTML = fields;
    $(".adm-form__error", m).textContent = "";
    st.onSave = onSave;
    m.showModal();
    $("input, select", $("#fin-fields"))?.focus();
  }
  const money = (name, label, value) =>
    `<label>${label}<span class="fin-money"><em>R$</em><input name="${name}" inputmode="decimal" placeholder="0,00" value="${centsToInput(value)}" required></span></label>`;
  const today = () => iso(new Date());

  async function openPayment(session) {
    const fields = session
      ? `<p class="fin-form-info"><b>${esc(session.patient_name)}</b> · ${dateBR(session.date)} ${esc(session.start)} · ${esc(session.service_name || "Sessão")}</p>`
      : `<label>Cliente <span class="adm-muted">(opcional)</span><select name="patient_user_id">${await patientsOptions()}</select></label>
         <label>Descrição<input name="description" maxlength="200" placeholder="Ex.: sessão avulsa, produto…"></label>`;
    openForm("💰 Registrar recebimento", `${fields}
      <div class="adm-form__row">${money("amount", "Valor", session?.due_cents)}
        <label>Data<input name="date" type="date" value="${today()}" required></label></div>
      <label>Forma de pagamento<select name="method">${methodOptions()}</select></label>`, async (d) => {
      const amount = toCents(d.amount);
      if (!amount) throw new Error("Informe o valor recebido.");
      await A().api("/api/admin/finance/payments", { method: "POST", body: {
        appointment_id: session?.id, patient_user_id: d.patient_user_id || undefined, amount_cents: amount,
        method: d.method, date: d.date, description: d.description } });
      A().toast("Recebimento registrado.");
    });
  }

  function openSessionPrice(session) {
    openForm("Terapia e valor da sessão", `<p class="fin-form-info"><b>${esc(session.patient_name)}</b> · ${dateBR(session.date)} ${esc(session.start)}</p>
      <label>Terapia<select name="service_id" data-fin-service>${serviceOptions(session.service_id, "Sem terapia")}</select></label>
      ${money("price", "Valor da sessão", session.price_cents)}`, async (d) => {
      const price = toCents(d.price);
      if (price === null || Number.isNaN(price)) throw new Error("Valor inválido.");
      await A().api(`/api/admin/appointments/${session.id}`, { method: "PATCH", body: { service_id: d.service_id || null, price_cents: price } });
      A().toast("Sessão atualizada.");
    });
  }

  async function openPackage() {
    openForm("📦 Novo pacote de sessões", `
      <label>Cliente<select name="patient_user_id" required>${await patientsOptions()}</select></label>
      <label>Terapia<select name="service_id" data-fin-pkg>${serviceOptions("", "Qualquer terapia")}</select></label>
      <div class="adm-form__row"><label>Sessões<input name="sessions_total" type="number" min="1" max="200" value="10" required data-fin-pkg></label>
        ${money("price", "Valor do pacote", "")}</div>
      <p class="adm-muted fin-help" data-fin-pkg-hint hidden></p>
      <label>Já recebeu?<select name="paid_method"><option value="">Ainda não (registrar depois)</option>${methodOptions("")}</select></label>
      <label>Observação<input name="notes" maxlength="200"></label>`, async (d) => {
      const price = toCents(d.price);
      if (price === null || Number.isNaN(price)) throw new Error("Informe o valor do pacote.");
      await A().api("/api/admin/finance/packages", { method: "POST", body: {
        patient_user_id: d.patient_user_id, service_id: d.service_id || null, sessions_total: Number(d.sessions_total),
        price_cents: price, paid_method: d.paid_method || null, notes: d.notes } });
      A().toast("Pacote criado.");
    });
  }

  function openExpense() {
    openForm("🧾 Nova despesa", `
      <div class="adm-form__row">${money("amount", "Valor", "")}<label>Data<input name="date" type="date" value="${today()}" required></label></div>
      <label>Categoria<select name="category" required>${st.opts.expense_categories.map((c) => `<option>${esc(c)}</option>`).join("")}</select></label>
      <label>Descrição<input name="description" maxlength="200" placeholder="Ex.: caixa de agulhas 0,25×30"></label>
      <label>Forma de pagamento<select name="method">${methodOptions("", true)}</select></label>`, async (d) => {
      const amount = toCents(d.amount);
      if (!amount) throw new Error("Informe o valor da despesa.");
      await A().api("/api/admin/finance/expenses", { method: "POST", body: {
        amount_cents: amount, date: d.date, category: d.category, description: d.description, method: d.method || null } });
      A().toast("Despesa registrada.");
    });
  }

  function openService(s = {}) {
    openForm(s.id ? "Editar terapia" : "Nova terapia", `
      <label>Nome<input name="name" maxlength="80" required value="${esc(s.name || "")}"></label>
      ${money("price", "Preço da sessão", s.price_cents ?? "")}
      <label class="ag-check"><input type="checkbox" name="social" ${s.social ? "checked" : ""}> 🤝 Faz parte do Ambulatório Social</label>`, async (d) => {
      const price = toCents(d.price);
      if (price === null || Number.isNaN(price)) throw new Error("Preço inválido.");
      await A().api(s.id ? `/api/admin/services/${s.id}` : "/api/admin/services",
        { method: s.id ? "PATCH" : "POST", body: { name: d.name, price_cents: price, social: Boolean(d.social) } });
      A().toast("Terapia salva.");
    });
  }

  // ---------------------------------------------------------------- eventos
  document.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-fin-tab],[data-fin-goto],[data-fin-new],[data-fin-pay],[data-fin-price],[data-fin-paypack],[data-fin-del],[data-fin-edit-service],[data-fin-toggle-service],[data-fin-step]");
    if (!t) return;
    try {
      if (t.dataset.finTab || t.dataset.finGoto) { st.tab = t.dataset.finTab || t.dataset.finGoto; return void load(); }
      if (t.dataset.finStep) {
        const d = Number(t.dataset.finStep);
        if (st.tab === "summary") st.year += d;
        else st.month = new Date(st.month.getFullYear(), st.month.getMonth() + d, 1);
        return void load();
      }
      const kind = t.dataset.finNew;
      if (kind === "payment") return void openPayment();
      if (kind === "package") return void openPackage();
      if (kind === "expense") return void openExpense();
      if (kind === "service") return void openService();
      if (t.dataset.finPay) return void openPayment(st.sessions.find((s) => s.id == t.dataset.finPay));
      if (t.dataset.finPrice) return void openSessionPrice(st.sessions.find((s) => s.id == t.dataset.finPrice));
      if (t.dataset.finPaypack) {
        openForm("💰 Receber pacote", `${money("amount", "Valor", Number(t.dataset.amount))}
          <div class="adm-form__row"><label>Data<input name="date" type="date" value="${today()}" required></label>
          <label>Forma<select name="method">${methodOptions()}</select></label></div>`, async (d) => {
          const amount = toCents(d.amount);
          if (!amount) throw new Error("Informe o valor.");
          await A().api("/api/admin/finance/payments", { method: "POST", body: {
            package_id: t.dataset.finPaypack, amount_cents: amount, method: d.method, date: d.date, description: "Pagamento de pacote" } });
          A().toast("Recebimento registrado.");
        });
        return;
      }
      if (t.dataset.finEditService) return void openService(st.services.find((s) => s.id == t.dataset.finEditService));
      if (t.dataset.finToggleService) {
        const s = st.services.find((x) => x.id == t.dataset.finToggleService);
        await A().api(`/api/admin/services/${s.id}`, { method: "PATCH", body: { active: !s.active } });
        return void load();
      }
      if (t.dataset.finDel) {
        if (!(await A().confirmAction("Excluir?", "Isso não pode ser desfeito.", "Excluir"))) return;
        await A().api(`/api/admin/finance/${t.dataset.finDel}`, { method: "DELETE" });
        A().toast("Excluído.");
        return void load();
      }
    } catch (err) { A().toast(err.message, true); }
  });

  // terapia escolhida -> sugere o preço
  document.addEventListener("change", (e) => {
    const sel = e.target.closest("[data-fin-service]");
    if (!sel) return;
    const price = Number(sel.selectedOptions[0]?.dataset.price || 0);
    const input = sel.form?.elements.price;
    if (input && price) input.value = centsToInput(price);
  });

  // Pacote: terapia × sessões -> sugere o valor. Dá para editar (desconto, preço especial);
  // depois de editado à mão, trocar a terapia ou o nº de sessões não apaga o valor digitado.
  function suggestPackage(f) {
    const sel = f.elements.service_id;
    const unit = Number(sel.selectedOptions[0]?.dataset.price || 0);
    const n = Math.max(0, Number(f.elements.sessions_total.value) || 0);
    const hint = $("[data-fin-pkg-hint]", f);
    if (!unit || !n) { if (hint) hint.hidden = true; return; }
    if (!f.elements.price.dataset.edited) f.elements.price.value = centsToInput(unit * n);
    if (hint) {
      hint.hidden = false;
      hint.innerHTML = `Sugestão: ${n} × ${brl(unit)} = <b>${brl(unit * n)}</b>. Pode mudar o valor (desconto, preço especial).`;
    }
  }
  document.addEventListener("change", (e) => { if (e.target.matches?.("[data-fin-pkg]")) suggestPackage(e.target.form); });
  document.addEventListener("input", (e) => {
    if (e.target.matches?.("input[data-fin-pkg]")) suggestPackage(e.target.form);
    else if (e.target.name === "price" && e.target.form?.elements.sessions_total) e.target.dataset.edited = e.target.value ? "1" : "";
  });

  const form = () => $("#fin-form");
  window.addEventListener("load", () => {
    form()?.addEventListener("submit", async (ev) => {
      if (ev.submitter?.value === "cancel") return;
      ev.preventDefault();
      const err = $(".adm-form__error", form());
      err.textContent = "";
      ev.submitter.disabled = true;
      try {
        await st.onSave(Object.fromEntries(new FormData(form())));
        modal().close();
        st.services = [];
        st.opts = null;
        load();
      } catch (e2) { err.textContent = e2.message; } finally { ev.submitter.disabled = false; }
    });
  });

  window.AjnaFinance = { load };
})();
