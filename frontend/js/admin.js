/* Painel do administrador: visão geral, agenda e clientes. */
(() => {
  "use strict";

  // ---------------------------------------------------------------- utilidades
  let csrfToken = "";
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  async function api(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      options = { ...options, body: JSON.stringify(options.body) };
    }
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
    const res = await fetch(url, { credentials: "same-origin", ...options, headers });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (res.status === 401) { location.replace("/login"); throw new Error("Sessão expirada."); }
    if (!res.ok) throw Object.assign(new Error(data?.error || "Não foi possível concluir a ação."), { data });
    return data;
  }

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  // foto do cliente (se ele enviou) ou as iniciais
  const clientAvatar = (p, cls = "adm-client__avatar") => window.AjnaShell
    ? window.AjnaShell.avatarHtml(p.name, p.avatar, cls)
    : `<span class="${cls}" aria-hidden="true">${esc(initials(p.name))}</span>`;
  const initials = (name) => (name || "?").trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

  // Datas sempre no fuso do computador (evita "pular" um dia por causa do UTC).
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const fromIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const startOfWeek = (d) => addDays(d, -((d.getDay() + 6) % 7)); // segunda-feira
  const fmt = (d, opts) => d.toLocaleDateString("pt-BR", opts);
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  const STATUS = { requested: "Pedido do cliente", scheduled: "Confirmada", done: "Realizada", cancelled: "Cancelada" };

  let toastTimer;
  function toast(message, isError = false) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.toggle("is-error", isError);
    el.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("is-visible"), 3200);
  }

  function confirmAction(title, text, okLabel = "Confirmar") {
    const modal = $("#confirm-modal");
    $("#confirm-title").textContent = title;
    $("#confirm-text").textContent = text;
    $("#confirm-ok").textContent = okLabel;
    modal.showModal();
    return new Promise((resolve) => modal.addEventListener("close", () => resolve(modal.returnValue === "ok"), { once: true }));
  }

  /** Liga um <dialog> com formulário: "Cancelar" fecha; "Salvar" chama onSave e fecha se der certo. */
  function bindForm(modal, onSave) {
    const form = $("form", modal);
    const error = $(".adm-form__error", form);
    form.addEventListener("submit", async (event) => {
      if (event.submitter?.value === "cancel") return;
      event.preventDefault();
      error.textContent = "";
      const button = event.submitter;
      button.disabled = true;
      try {
        await onSave(Object.fromEntries(new FormData(form)));
        modal.close();
      } catch (err) {
        error.textContent = err.message;
      } finally {
        button.disabled = false;
      }
    });
  }

  // ---------------------------------------------------------------- estado
  const state = { patients: [], view: "overview" };

  // ---------------------------------------------------------------- navegação
  const TITLES = { overview: "Visão geral", agenda: "Agenda", clients: "Clientes", patient: "Ficha do paciente", points: "Mapa de pontos", finance: "Financeiro" };

  // "#paciente-12" abre a ficha do paciente 12.
  function show(view) {
    let key = view;
    const m = /^paciente-(\d+)$/.exec(view || "");
    if (m) { key = "patient"; state.patientId = Number(m[1]); }
    if (!TITLES[key] || (key === "patient" && !m)) { key = "overview"; view = "overview"; }
    state.view = key;
    state.hash = view;
    $$(".adm-view").forEach((s) => (s.hidden = s.id !== `view-${key}`));
    const navKey = key === "patient" ? "clients" : key;
    $$(".adm-nav__item[data-view]").forEach((b) => b.classList.toggle("is-active", b.dataset.view === navKey));
    $("#view-title").textContent = TITLES[key];
    if (location.hash !== `#${view}`) history.pushState(null, "", `#${view}`);
    window.scrollTo({ top: 0 });
    refresh();
  }

  function refresh() {
    if (state.dayOpen && $("#day-modal").open) openDay(state.dayOpen).catch(() => {});
    if (state.view === "overview") return loadOverview();
    if (state.view === "agenda") return loadAgenda();
    if (state.view === "clients") return loadClients();
    if (state.view === "patient") return loadPatientFile();
    if (state.view === "points") return loadPointsView();
    if (state.view === "finance") return window.AjnaFinance?.load();
  }

  // ---------------------------------------------------------------- visão geral
  function updateRequestBadge(n) {
    const item = $('.adm-nav__item[data-view="overview"]');
    let badge = $(".adm-nav__count", item);
    if (!badge) { badge = document.createElement("span"); badge.className = "adm-nav__count"; item.append(badge); }
    badge.textContent = n;
    badge.hidden = !n;
  }

  function appointmentRow(a, withActions = true, showDate = false) {
    const when = showDate ? `${fmt(fromIso(a.date), { weekday: "short", day: "2-digit", month: "2-digit" })} · ` : "";
    const actions = !withActions ? "" : a.status === "requested" ? `
      <div class="adm-appt__actions">
        <button class="adm-btn adm-btn--sm adm-btn--confirm" data-appt-confirm="${a.id}" type="button">✓ Confirmar</button>
        <button class="adm-btn adm-btn--sm" data-appt-decline="${a.id}" type="button">Recusar</button>
      </div>` : `
      <div class="adm-appt__actions">
        ${["scheduled", "done"].includes(a.status) ? `<button class="adm-btn adm-btn--sm adm-btn--protocol" data-protocol="${a.id}" data-patient="${a.patient_user_id}" type="button">📝 ${a.has_protocol ? "Protocolo" : "Preencher protocolo"}</button>` : ""}
        ${a.status === "scheduled" ? `<button class="adm-btn adm-btn--sm" data-appt-done="${a.id}" type="button">✓ Realizada</button>` : ""}
        ${a.status !== "cancelled" ? `<button class="adm-btn adm-btn--sm" data-appt-edit="${a.id}" type="button">Remarcar</button>` : ""}
        ${a.status !== "cancelled" ? `<button class="adm-btn adm-btn--sm" data-appt-cancel="${a.id}" type="button">Cancelar</button>` : ""}
        ${a.status === "cancelled" ? `<button class="adm-btn adm-btn--sm" data-appt-delete="${a.id}" type="button">Excluir</button>` : ""}
      </div>`;
    return `
      <div class="adm-appt adm-appt--${a.status}">
        <span class="adm-appt__time">${when}${esc(a.start)}–${esc(a.end)}</span>
        <div>
          <button class="adm-appt__who adm-link" data-open-patient="${a.patient_user_id}" type="button" title="Abrir ficha">${esc(a.patient_name)}</button>
          <span class="adm-badge adm-badge--${a.status}">${STATUS[a.status] || a.status}</span>
        </div>
        ${actions}
      </div>`;
  }

  async function loadOverview() {
    const d = await api("/api/admin/dashboard");
    $("#stat-patients").textContent = d.patients;
    $("#stat-today").textContent = d.appointments_today;
    $("#stat-week").textContent = d.appointments_week;
    $("#stat-requests").textContent = d.requests.length;
    $("#requests-card").hidden = !d.requests.length;
    $("#requests-list").innerHTML = d.requests.map((a) => appointmentRow(a, true, true)).join("");
    updateRequestBadge(d.requests.length);
    $("#today-list").innerHTML = d.today.length
      ? d.today.map((a) => appointmentRow(a)).join("")
      : '<p class="adm-empty">Nenhuma consulta hoje. 🌿</p>';
  }

  // ---------------------------------------------------------------- agenda
  // Três jeitos de ver: lista (semana em blocos), semana (7 colunas lado a lado) e mês (calendário).
  const AG_VIEWS = ["list", "week", "month"];
  state.agView = AG_VIEWS.includes(localStorage.getItem("ajna-agenda-view")) ? localStorage.getItem("ajna-agenda-view") : "list";
  state.cursor = new Date();
  const WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

  function agRange() {
    if (state.agView !== "month") {
      const start = startOfWeek(state.cursor);
      return [start, addDays(start, 6)];
    }
    const start = startOfWeek(new Date(state.cursor.getFullYear(), state.cursor.getMonth(), 1));
    return [start, addDays(start, 41)]; // 6 semanas
  }

  function agLabel(start, end) {
    if (state.agView === "month") return cap(fmt(state.cursor, { month: "long", year: "numeric" }));
    const full = { day: "numeric", month: "short", year: "numeric" };
    if (start.getMonth() === end.getMonth()) return `${start.getDate()} – ${fmt(end, { day: "numeric", month: "long", year: "numeric" })}`;
    return start.getFullYear() === end.getFullYear()
      ? `${fmt(start, { day: "numeric", month: "short" })} – ${fmt(end, full)}`
      : `${fmt(start, full)} – ${fmt(end, full)}`;
  }

  const fullDay = (b) => b.start <= "00:00" && b.end >= "23:59";

  function blockRow(b, compact = false) {
    const when = fullDay(b) ? "Dia inteiro" : `${esc(b.start)}–${esc(b.end)}`;
    return `<div class="ag-block ${compact ? "ag-block--sm" : ""}" title="${esc(b.reason || "Indisponível")}">
      <span>⛔ ${when}${b.reason ? ` · ${esc(b.reason)}` : compact ? "" : " · Indisponível"}</span>
      <button class="adm-btn adm-btn--sm" data-block-del="${b.id}" type="button" title="Liberar horário">${compact ? "×" : "Liberar"}</button>
    </div>`;
  }

  function chip(a) {
    return `<button class="ag-chip ag-chip--${a.status}" data-appt-pick="${a.id}" type="button" title="${esc(a.patient_name)} · ${STATUS[a.status] || ""}">
      <b>${esc(a.start)}</b> ${esc(a.patient_name.split(" ")[0])}</button>`;
  }

  const byTime = (rows) => rows.sort((x, y) => x.t.localeCompare(y.t)).map((r) => r.h).join("");

  // Dias sem atendimento (segunda, sexta, sábado e domingo) e eventos fixos (Reiki Para Todos) vêm do servidor.
  const wd = (d) => (d.getDay() + 6) % 7; // 0 = segunda
  const isClosedDay = (d) => (state.closedWeekdays || []).includes(wd(d));
  const eventTag = (ev, big = false) =>
    `<div class="ag-event ${big ? "ag-event--big" : ""}" title="${esc(ev.description)}">${ev.icon} <b>${esc(ev.title)}</b>${big ? `<span>${esc(ev.description)}</span>` : ""}</div>`;
  const closedTag = '<div class="ag-closed">🚫 Sem atendimento</div>';

  async function fetchRange(start, end) {
    const q = `from=${iso(start)}&to=${iso(end)}`;
    const [{ items }, { items: blocks }, ev] = await Promise.all([
      api(`/api/admin/appointments?${q}`), api(`/api/admin/blocks?${q}`), api(`/api/patient/events?${q}`)]);
    state.closedWeekdays = ev.closed_weekdays;
    return { items, blocks, events: ev.items };
  }

  async function loadAgenda() {
    const [start, end] = agRange();
    $("#week-label").textContent = agLabel(start, end);
    $$("[data-ag-view]").forEach((b) => b.classList.toggle("is-active", b.dataset.agView === state.agView));
    const { items, blocks, events } = await fetchRange(start, end);
    state.weekItems = items;
    const today = iso(new Date());
    const box = $("#week-days");
    box.className = `adm-days ag-${state.agView}`;
    const dayData = (day) => {
      const key = iso(day);
      const blk = blocks.filter((b) => b.date === key);
      const closed = isClosedDay(day);
      const evs = events.filter((e) => e.date === key);
      // dia de evento (Reiki) não fica listrado de vermelho, mesmo sendo dia sem atendimento
      return { key, closed, list: items.filter((a) => a.date === key), blk, evs,
        off: (closed && !evs.length) || blk.some(fullDay) };
    };
    const openBtn = (key, label) => `<button class="ag-open" data-day-open="${key}" type="button" title="Abrir o dia">${label}</button>`;

    if (state.agView === "list") {
      box.innerHTML = Array.from({ length: 7 }, (_, i) => {
        const day = addDays(start, i);
        const { key, list, blk, evs, closed, off } = dayData(day);
        const rows = byTime([...blk.map((b) => ({ t: b.start, h: blockRow(b) })), ...list.map((a) => ({ t: a.start, h: appointmentRow(a) }))]);
        return `
        <section class="adm-card adm-day ${key === today ? "adm-day--today" : ""} ${off ? "ag-off" : ""}">
          <div class="adm-day__head">
            <h3>${openBtn(key, cap(fmt(day, { weekday: "long", day: "numeric", month: "short", year: "numeric" })))}</h3>
            ${key === today ? '<span class="adm-badge adm-badge--scheduled">Hoje</span>' : ""}
            <button class="adm-btn adm-btn--link" data-block-on="${key}" type="button" style="margin-left:auto">⛔ Indisponível</button>
            <button class="adm-btn adm-btn--link" data-new-on="${key}" type="button">＋ Agendar</button>
          </div>
          <div class="adm-list">${closed && !evs.length ? closedTag : ""}${evs.map((e) => eventTag(e)).join("")}${rows || (closed ? "" : '<p class="adm-muted">Livre</p>')}</div>
        </section>`;
      }).join("");
      return;
    }

    if (state.agView === "week") {
      box.innerHTML = `<div class="ag-weekgrid">${Array.from({ length: 7 }, (_, i) => {
        const day = addDays(start, i);
        const { key, list, blk, evs, closed, off } = dayData(day);
        const rows = byTime([...blk.map((b) => ({ t: b.start, h: blockRow(b, true) })), ...list.map((a) => ({ t: a.start, h: chip(a) }))]);
        return `<section class="ag-col ${key === today ? "is-today" : ""} ${off ? "ag-off" : ""}">
          <header data-day-open="${key}" title="Abrir o dia"><span>${WEEKDAYS[i]}</span><b>${day.getDate()}</b><small>${fmt(day, { month: "short", year: "numeric" })}</small></header>
          <div class="ag-col__items">${closed && !evs.length ? closedTag : ""}${evs.map((e) => eventTag(e)).join("")}${rows || (closed ? "" : '<p class="adm-muted">Livre</p>')}</div>
          <footer>
            <button class="adm-btn adm-btn--sm" data-day-open="${key}" type="button" title="Abrir o dia">🔍</button>
            <button class="adm-btn adm-btn--sm" data-new-on="${key}" type="button" title="Agendar">＋</button>
            <button class="adm-btn adm-btn--sm" data-block-on="${key}" type="button" title="Marcar indisponível">⛔</button>
          </footer>
        </section>`;
      }).join("")}</div>`;
      return;
    }

    // mês (calendário)
    const month = state.cursor.getMonth();
    box.innerHTML = `<div class="ag-month adm-card">
      ${WEEKDAYS.map((w) => `<div class="ag-month__wd">${w}</div>`).join("")}
      ${Array.from({ length: 42 }, (_, i) => {
        const day = addDays(start, i);
        const { key, list, blk, evs, closed, off } = dayData(day);
        const active = list.filter((a) => a.status !== "cancelled");
        const offLabel = closed && evs.length ? "" : closed ? '<span class="ag-cell__off ag-cell__off--closed">🚫 Sem atendimento</span>'
          : off ? '<span class="ag-cell__off">⛔ Indisponível</span>'
          : blk.length ? `<span class="ag-cell__off ag-cell__off--part">⛔ ${blk.length} período(s)</span>` : "";
        return `<div class="ag-cell ${day.getMonth() !== month ? "is-out" : ""} ${key === today ? "is-today" : ""} ${off ? "ag-off" : ""}" data-day-open="${key}">
          <span class="ag-cell__num">${day.getDate()}</span>
          ${offLabel}
          ${evs.map((e) => `<span class="ag-cell__event" title="${esc(e.title)}">${e.icon} ${esc(e.title)}</span>`).join("")}
          <div class="ag-cell__items">${active.slice(0, 3).map(chip).join("")}${active.length > 3 ? `<span class="ag-more">+${active.length - 3} mais</span>` : ""}</div>
          ${active.length ? `<span class="ag-cell__count">${active.length}</span>` : ""}
          <div class="ag-cell__act">
            <button data-new-on="${key}" type="button" title="Agendar">＋</button>
            <button data-block-on="${key}" type="button" title="Marcar indisponível">⛔</button>
          </div>
        </div>`;
      }).join("")}
    </div>`;
  }

  // ---------------------------------------------------------------- janela do dia (visão do dia inteiro)
  const DAY_FROM = 7, DAY_TO = 21; // horas mostradas na linha do tempo
  const toMin = (hm) => { const [h, m] = hm.split(":").map(Number); return h * 60 + m; };

  async function openDay(key) {
    state.dayOpen = key;
    const day = fromIso(key);
    const { items, blocks, events } = await fetchRange(day, day);
    state.dayItems = items;
    const closed = isClosedDay(day);
    const active = items.filter((a) => a.status !== "cancelled");
    $("#day-title").textContent = cap(fmt(day, { weekday: "long", day: "numeric", month: "long", year: "numeric" }));
    const counts = ["requested", "scheduled", "done", "cancelled"].map((s) => [s, items.filter((a) => a.status === s).length]).filter(([, n]) => n);
    $("#day-sub").innerHTML = (key === iso(new Date()) ? '<span class="adm-badge adm-badge--scheduled">Hoje</span> ' : "") +
      (items.length ? counts.map(([s, n]) => `<span class="adm-badge adm-badge--${s}">${n} ${STATUS[s].toLowerCase()}</span>`).join(" ") : "Nenhuma consulta");

    // linha do tempo
    const span = (DAY_TO - DAY_FROM) * 60;
    const pos = (s, e) => {
      const a = Math.max(toMin(s), DAY_FROM * 60), b = Math.min(toMin(e), DAY_TO * 60);
      return `top:${((a - DAY_FROM * 60) / span) * 100}%;height:${Math.max(((b - a) / span) * 100, 2.2)}%`;
    };
    const hours = Array.from({ length: DAY_TO - DAY_FROM + 1 }, (_, i) =>
      `<div class="dv-hour" style="top:${(i / (DAY_TO - DAY_FROM)) * 100}%"><span>${String(DAY_FROM + i).padStart(2, "0")}:00</span></div>`).join("");
    const blockEls = blocks.map((b) => `<div class="dv-item dv-block" style="${pos(b.start, b.end)}">
      ⛔ ${fullDay(b) ? "Dia inteiro" : `${esc(b.start)}–${esc(b.end)}`}${b.reason ? ` · ${esc(b.reason)}` : ""}
      <button class="adm-btn adm-btn--sm" data-block-del="${b.id}" type="button">Liberar</button></div>`).join("");
    // consultas que se sobrepõem ficam lado a lado
    const sorted = [...active].sort((a, b) => a.start.localeCompare(b.start));
    const lanes = [];
    const placed = sorted.map((a) => {
      let lane = lanes.findIndex((end) => end <= a.start);
      if (lane < 0) { lane = lanes.length; lanes.push(a.end); } else lanes[lane] = a.end;
      return { a, lane };
    });
    const nl = Math.max(lanes.length, 1);
    const apptEls = placed.map(({ a, lane }) => `<button class="dv-item dv-appt dv-appt--${a.status}" data-appt-pick="${a.id}" type="button"
        style="${pos(a.start, a.end)};left:calc(${(lane / nl) * 100}% + 4px);width:calc(${100 / nl}% - 8px)">
        <b>${esc(a.start)}–${esc(a.end)}</b><span>${esc(a.patient_name)}</span><small>${STATUS[a.status]}</small></button>`).join("");
    const nowLine = key === iso(new Date()) ? (() => {
      const n = new Date(), m = n.getHours() * 60 + n.getMinutes();
      return m >= DAY_FROM * 60 && m <= DAY_TO * 60 ? `<div class="dv-now" style="top:${((m - DAY_FROM * 60) / span) * 100}%"></div>` : "";
    })() : "";

    const cancelled = items.filter((a) => a.status === "cancelled");
    $("#day-body").innerHTML = `
      <div class="dv">
        <div class="dv-scroll"><div class="dv-timeline ${closed && !events.length ? "is-closed" : ""}">
          ${hours}
          <div class="dv-lane">${blockEls}${apptEls}${nowLine}</div>
        </div></div>
        <aside class="dv-side">
          ${closed ? '<div class="ag-closed">🚫 Dia sem atendimento (só há atendimento de terça a quinta). Dá para agendar só como exceção.</div>' : ""}
          ${events.map((e) => eventTag(e, true)).join("")}
          <h3 class="mp-subtitle">Consultas do dia</h3>
          <div class="adm-list">${sorted.map((a) => appointmentRow(a)).join("") || '<p class="adm-muted">Nenhuma consulta marcada.</p>'}</div>
          ${cancelled.length ? `<details class="dv-cancel"><summary>${cancelled.length} cancelada(s)</summary><div class="adm-list">${cancelled.map((a) => appointmentRow(a)).join("")}</div></details>` : ""}
        </aside>
      </div>`;
    const modal = $("#day-modal");
    if (!modal.open) modal.showModal();
    // rola a linha do tempo até a primeira consulta (ou 8h)
    const first = sorted[0] ? toMin(sorted[0].start) : 8 * 60;
    $(".dv-scroll").scrollTop = Math.max(0, ((first - DAY_FROM * 60) / 60) * 64 - 24);
  }

  $("#day-close").addEventListener("click", () => $("#day-modal").close());
  $("#day-prev").addEventListener("click", () => openDay(iso(addDays(fromIso(state.dayOpen), -1))));
  $("#day-next").addEventListener("click", () => openDay(iso(addDays(fromIso(state.dayOpen), 1))));
  $("#day-new").addEventListener("click", () => openAppointment({ date: state.dayOpen }));
  $("#day-block").addEventListener("click", () => openBlock(state.dayOpen));
  $("#day-modal").addEventListener("close", () => { state.dayOpen = null; });

  function agStep(dir) {
    const c = state.cursor;
    state.cursor = state.agView === "month" ? new Date(c.getFullYear(), c.getMonth() + dir, 1) : addDays(c, 7 * dir);
    loadAgenda();
  }
  $("#week-prev").addEventListener("click", () => agStep(-1));
  $("#week-next").addEventListener("click", () => agStep(1));
  $("#week-today").addEventListener("click", () => { state.cursor = new Date(); loadAgenda(); });
  $$("[data-ag-view]").forEach((b) => b.addEventListener("click", () => {
    state.agView = b.dataset.agView;
    localStorage.setItem("ajna-agenda-view", state.agView);
    loadAgenda();
  }));

  // Abrir o dia; consulta compacta -> janela com as ações; bloqueios.
  document.addEventListener("click", async (e) => {
    const open = e.target.closest("[data-day-open]");
    if (open && !e.target.closest("button:not([data-day-open]), [data-appt-pick]")) {
      return void openDay(open.dataset.dayOpen).catch((err) => toast(err.message, true));
    }
    const pick = e.target.closest("[data-appt-pick]");
    if (pick) {
      const a = [...(state.dayItems || []), ...(state.weekItems || [])].find((x) => x.id == pick.dataset.apptPick);
      if (!a) return;
      $("#appt-view-body").innerHTML = `<p class="adm-muted">${cap(fmt(fromIso(a.date), { weekday: "long", day: "numeric", month: "long", year: "numeric" }))}</p>
        <div class="adm-list">${appointmentRow(a)}</div>`;
      $("#appt-view-modal").showModal();
      return;
    }
    const del = e.target.closest("[data-block-del]");
    if (del) {
      if (!(await confirmAction("Liberar horário?", "O período volta a ficar disponível para agendamento.", "Liberar"))) return;
      try {
        await api(`/api/admin/blocks/${del.dataset.blockDel}`, { method: "DELETE" });
        toast("Horário liberado.");
        loadAgenda();
      } catch (err) { toast(err.message, true); }
      return;
    }
    const on = e.target.closest("[data-block-on]");
    if (on) openBlock(on.dataset.blockOn || iso(state.agView === "month" ? new Date() : state.cursor));
  });
  $("#appt-view-modal").addEventListener("click", (e) => {
    if (e.target.closest("button")) $("#appt-view-modal").close();
  });

  // Janela "marcar indisponível"
  const blockModal = $("#block-modal");
  const blockForm = $("#block-form");
  const syncAllDay = () => { $("[data-block-hours]", blockForm).hidden = blockForm.elements.all_day.checked; };
  blockForm.elements.all_day.addEventListener("change", syncAllDay);
  function openBlock(day) {
    blockForm.reset();
    $(".adm-form__error", blockForm).textContent = "";
    blockForm.elements.date.value = day;
    syncAllDay();
    blockModal.showModal();
  }
  bindForm(blockModal, async (data) => {
    const allDay = blockForm.elements.all_day.checked;
    const body = { date: data.date, date_to: data.date_to || data.date, reason: data.reason,
      start: allDay ? "00:00" : data.start, end: allDay ? "23:59" : data.end };
    const r = await api("/api/admin/blocks", { method: "POST", body });
    toast(r.appointments_inside
      ? `Marcado como indisponível. Atenção: já há ${r.appointments_inside} consulta(s) nesse período.`
      : "Marcado como indisponível.", Boolean(r.appointments_inside));
    state.cursor = fromIso(data.date);
    loadAgenda();
  });

  // Ações nas consultas (funciona na visão geral e na agenda).
  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-appt-done],[data-appt-cancel],[data-appt-delete],[data-appt-edit],[data-new-on],[data-appt-confirm],[data-appt-decline]");
    if (!btn) return;
    try {
      if (btn.dataset.apptConfirm) {
        await api(`/api/admin/appointments/${btn.dataset.apptConfirm}`, { method: "PATCH", body: { status: "scheduled" } });
        toast("Consulta confirmada.");
        return refresh();
      }
      if (btn.dataset.apptDecline) {
        if (!(await confirmAction("Recusar pedido?", "O horário volta a ficar livre e o cliente verá o pedido como cancelado.", "Recusar"))) return;
        await api(`/api/admin/appointments/${btn.dataset.apptDecline}`, { method: "PATCH", body: { status: "cancelled" } });
        toast("Pedido recusado.");
        return refresh();
      }
      if (btn.dataset.newOn) return openAppointment({ date: btn.dataset.newOn });
      if (btn.dataset.apptEdit) {
        const a = (state.weekItems || []).find((x) => x.id == btn.dataset.apptEdit)
          || (await api(`/api/admin/appointments?from=${iso(new Date())}&to=${iso(new Date())}`)).items.find((x) => x.id == btn.dataset.apptEdit);
        return openAppointment(a);
      }
      if (btn.dataset.apptDone) {
        await api(`/api/admin/appointments/${btn.dataset.apptDone}`, { method: "PATCH", body: { status: "done" } });
        toast("Consulta marcada como realizada.");
      } else if (btn.dataset.apptCancel) {
        if (!(await confirmAction("Cancelar consulta?", "O horário ficará livre na agenda.", "Cancelar consulta"))) return;
        await api(`/api/admin/appointments/${btn.dataset.apptCancel}`, { method: "PATCH", body: { status: "cancelled" } });
        toast("Consulta cancelada.");
      } else if (btn.dataset.apptDelete) {
        if (!(await confirmAction("Excluir consulta?", "Ela será apagada do histórico. Isso não pode ser desfeito.", "Excluir"))) return;
        await api(`/api/admin/appointments/${btn.dataset.apptDelete}`, { method: "DELETE" });
        toast("Consulta excluída.");
      }
      refresh();
    } catch (err) { toast(err.message, true); }
  });

  // Modal de consulta (nova ou remarcar)
  const apptModal = $("#appointment-modal");
  const apptForm = $("#appointment-form");

  async function openAppointment(a = {}) {
    if (!state.patients.length) await fetchPatients();
    const active = state.patients.filter((p) => p.active || p.id === a.patient_user_id);
    if (!active.length) return toast("Cadastre um cliente antes de agendar.", true);
    const select = apptForm.elements.patient_user_id;
    select.innerHTML = '<option value="">Escolha…</option>' +
      active.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
    apptForm.reset();
    $(".adm-form__error", apptForm).textContent = "";
    apptForm.dataset.id = a.id || "";
    select.disabled = Boolean(a.id);
    $("#appointment-modal-title").textContent = a.id ? "Remarcar consulta" : "Nova consulta";
    select.value = a.patient_user_id || "";
    apptForm.elements.date.value = a.date || iso(new Date());
    apptForm.elements.start.value = a.start || "09:00";
    apptForm.elements.end.value = a.end || "10:00";
    // financeiro: terapia e valor (o preço da terapia é sugerido)
    try { state.services = (await api("/api/admin/services")).items; } catch { state.services = []; }
    const money = (c) => (c || c === 0 ? (c / 100).toFixed(2).replace(".", ",") : "");
    apptForm.elements.service_id.innerHTML = '<option value="">Sem terapia</option>' + state.services
      .filter((s) => s.active || s.id === a.service_id)
      .map((s) => `<option value="${s.id}" data-price="${s.price_cents}">${s.social ? "🤝 " : ""}${esc(s.name)}</option>`).join("");
    apptForm.elements.service_id.value = a.service_id || "";
    apptForm.elements.price.value = money(a.price_cents ?? null);
    apptModal.showModal();
  }

  apptForm.elements.patient_user_id.addEventListener("change", (e) => {
    const p = state.patients.find((x) => x.id == e.target.value);
    const social = (state.services || []).find((s) => s.social && s.active);
    if (p?.social && social && !apptForm.elements.service_id.value) {
      apptForm.elements.service_id.value = social.id;
      apptForm.elements.price.value = (social.price_cents / 100).toFixed(2).replace(".", ",");
    }
  });

  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-social-toggle]");
    if (!b) return;
    const on = b.dataset.on !== "1";
    try {
      await api(`/api/admin/patients/${b.dataset.socialToggle}`, { method: "PATCH", body: { social: on } });
      toast(on ? "Paciente incluído no Ambulatório Social." : "Paciente retirado do Ambulatório Social.");
      refresh();
    } catch (err) { toast(err.message, true); }
  });

  apptForm.elements.service_id.addEventListener("change", (e) => {
    const price = Number(e.target.selectedOptions[0]?.dataset.price || 0);
    apptForm.elements.price.value = price ? (price / 100).toFixed(2).replace(".", ",") : "";
  });

  // Ao mudar o início, sugere 1h de duração.
  apptForm.elements.start.addEventListener("change", (e) => {
    const [h, m] = e.target.value.split(":").map(Number);
    if (Number.isFinite(h) && h < 23) apptForm.elements.end.value = `${String(h + 1).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  });

  async function sendAppointment(url, method, body) {
    try {
      return await api(url, { method, body });
    } catch (err) {
      if (!err.data?.closed_day) throw err;
      const ok = await confirmAction("Dia sem atendimento", "Só há atendimento de terça a quinta. Agendar mesmo assim, como exceção?", "Agendar mesmo assim");
      if (!ok) throw err;
      return api(url, { method, body: { ...body, force: true } });
    }
  }

  bindForm(apptModal, async (data) => {
    const id = apptForm.dataset.id;
    // valor em reais (ex.: 150,00) -> centavos
    const raw = String(data.price || "").trim();
    delete data.price;
    data.service_id = data.service_id || null;
    if (raw) {
      const n = Number(raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw);
      if (!Number.isFinite(n) || n < 0) throw new Error("Valor inválido. Use, por exemplo, 150,00.");
      data.price_cents = Math.round(n * 100);
    }
    if (id) {
      delete data.patient_user_id;
      await sendAppointment(`/api/admin/appointments/${id}`, "PATCH", data);
      toast("Consulta remarcada.");
    } else {
      await sendAppointment("/api/admin/appointments", "POST", data);
      toast("Consulta agendada.");
    }
    state.cursor = fromIso(data.date || iso(new Date()));
    refresh();
  });

  // ---------------------------------------------------------------- clientes
  async function fetchPatients() {
    state.patients = (await api("/api/admin/patients")).items;
  }

  async function loadClients() {
    await fetchPatients();
    renderClients();
  }

  function renderClients() {
    const term = $("#client-search").value.trim().toLowerCase();
    const filter = $("#client-filter").value;
    const list = state.patients.filter((p) =>
      (filter === "all" || (filter === "active" ? p.active : !p.active)) &&
      (!term || [p.name, p.email, p.phone].some((v) => (v || "").toLowerCase().includes(term))));

    $("#client-list").innerHTML = list.length ? list.map((p) => `
      <div class="adm-client">
        ${clientAvatar(p)}
        <div>
          <div class="adm-client__name">${esc(p.name)} ${p.social ? '<span class="social-badge" title="Participa do Ambulatório Social">🤝 Ambulatório Social</span>' : ""}</div>
          <div class="adm-muted" style="font-size:.82rem">${p.appointments} consulta(s)</div>
        </div>
        <div class="adm-client__contact">${esc(p.email)}${p.phone ? `<br>${esc(p.phone)}` : ""}</div>
        <span class="adm-client__badge adm-badge adm-badge--${p.active ? "active" : "inactive"}">${p.active ? "Ativo" : "Desativado"}</span>
        <div class="adm-client__actions">
          <button class="adm-btn adm-btn--sm adm-btn--protocol" data-open-patient="${p.id}" type="button">📋 Ficha</button>
          <button class="adm-btn adm-btn--sm" data-client-edit="${p.id}" type="button">Editar</button>
          <button class="adm-btn adm-btn--sm" data-client-password="${p.id}" type="button">Senha</button>
          <button class="adm-btn adm-btn--sm" data-client-toggle="${p.id}" type="button">${p.active ? "Desativar" : "Reativar"}</button>
          ${p.appointments ? "" : `<button class="adm-btn adm-btn--sm" data-client-delete="${p.id}" type="button">Excluir</button>`}
        </div>
      </div>`).join("")
      : `<p class="adm-empty">${state.patients.length ? "Nenhum cliente encontrado com esse filtro." : "Nenhum cliente cadastrado ainda. Clique em “Novo cliente”."}</p>`;
  }

  $("#client-search").addEventListener("input", renderClients);
  $("#client-filter").addEventListener("change", renderClients);

  const clientModal = $("#client-modal");
  const clientForm = $("#client-form");

  function openClient(p = null) {
    clientForm.reset();
    $(".adm-form__error", clientForm).textContent = "";
    clientForm.dataset.id = p?.id || "";
    $("#client-modal-title").textContent = p ? "Editar cliente" : "Novo cliente";
    const pwd = $('[data-only="create"]', clientForm);
    pwd.hidden = Boolean(p);
    pwd.querySelector("input").required = !p;
    if (p) {
      clientForm.elements.name.value = p.name;
      clientForm.elements.email.value = p.email;
      clientForm.elements.phone.value = p.phone || "";
    }
    clientModal.showModal();
  }

  bindForm(clientModal, async (data) => {
    const id = clientForm.dataset.id;
    if (id) {
      delete data.password;
      await api(`/api/admin/patients/${id}`, { method: "PATCH", body: data });
      toast("Dados do cliente atualizados.");
    } else {
      await api("/api/admin/patients", { method: "POST", body: data });
      toast("Acesso criado! Envie o e-mail e a senha ao cliente.");
    }
    await fetchPatients();
    refresh();
  });

  const passwordModal = $("#password-modal");
  const passwordForm = $("#password-form");
  bindForm(passwordModal, async (data) => {
    await api(`/api/admin/patients/${passwordForm.dataset.id}`, { method: "PATCH", body: { password: data.password } });
    toast("Senha atualizada. Envie a nova senha ao cliente.");
  });

  $("#client-list").addEventListener("click", async (event) => {
    const btn = event.target.closest("button");
    if (!btn) return;
    const id = Number(btn.dataset.clientEdit || btn.dataset.clientPassword || btn.dataset.clientToggle || btn.dataset.clientDelete);
    const p = state.patients.find((x) => x.id === id);
    if (!p) return;
    try {
      if (btn.dataset.clientEdit) return openClient(p);
      if (btn.dataset.clientPassword) {
        passwordForm.reset();
        $(".adm-form__error", passwordForm).textContent = "";
        passwordForm.dataset.id = p.id;
        $("#password-modal-who").textContent = `Cliente: ${p.name}`;
        return passwordModal.showModal();
      }
      if (btn.dataset.clientToggle) {
        if (p.active && !(await confirmAction("Desativar acesso?", `${p.name} não conseguirá mais entrar até ser reativado(a).`, "Desativar"))) return;
        await api(`/api/admin/patients/${p.id}`, { method: "PATCH", body: { active: !p.active } });
        toast(p.active ? "Acesso desativado." : "Acesso reativado.");
      }
      if (btn.dataset.clientDelete) {
        if (!(await confirmAction("Excluir cliente?", `${p.name} será apagado(a). Isso não pode ser desfeito.`, "Excluir"))) return;
        await api(`/api/admin/patients/${p.id}`, { method: "DELETE" });
        toast("Cliente excluído.");
      }
      loadClients();
    } catch (err) { toast(err.message, true); }
  });

  // ---------------------------------------------------------------- ficha do paciente
  // Os campos das fichas vêm do servidor (backend/app/routes/records.py): mude lá para mudar aqui.
  let FORMS = null;
  const getForms = async () => (FORMS ||= await api("/api/admin/forms"));
  const allFields = (sections) => sections.flatMap((s) => s.fields);
  const dateBR = (s) => (s ? s.slice(0, 10).split("-").reverse().join("/") : "");

  function fieldInput(f, value) {
    const name = `name="${f.key}"`;
    if (f.type === "points") return pointsInput(f, value);
    if (f.type === "long") return `<textarea ${name} rows="3">${esc(value || "")}</textarea>`;
    if (f.type === "date") return `<input type="date" ${name} value="${esc(value || "")}">`;
    if (f.type === "select") return `<select ${name}><option value="">—</option>${f.options.map((o) =>
      `<option ${o === value ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
    if (f.type === "check") return `<label class="pf-check"><input type="checkbox" ${name} ${value ? "checked" : ""}> Sim</label>`;
    if (f.type === "multi") return `<div class="pf-chips">${f.options.map((o) => `
      <label class="pf-chip"><input type="checkbox" name="${f.key}" value="${esc(o)}" ${(value || []).includes(o) ? "checked" : ""}><span>${esc(o)}</span></label>`).join("")}</div>`;
    if (f.type === "scale") return `<div class="pf-scale">${Array.from({ length: 11 }, (_, n) => `
      <label><input type="radio" ${name} value="${n}" ${String(value) === String(n) ? "checked" : ""}><span>${n}</span></label>`).join("")}</div>`;
    return `<input type="text" ${name} value="${esc(value || "")}">`;
  }

  function formHtml(sections, data = {}) {
    return sections.map((sec) => `
      <fieldset class="pf-section">
        <legend>${sec.icon} ${esc(sec.title)}</legend>
        <div class="pf-fields">${sec.fields.map((f) => `
          <div class="pf-field pf-field--${f.type === "points" ? "multi" : f.type}"><span class="pf-label">${esc(f.label)}</span>${fieldInput(f, data[f.key])}</div>`).join("")}
        </div>
      </fieldset>`).join("");
  }

  function readFields(root, sections) {
    const out = {};
    for (const f of allFields(sections)) {
      if (f.type === "points") out[f.key] = $$(`[data-points="${f.key}"] .pf-pchip`, root).map((c) => c.dataset.code);
      else if (f.type === "multi") out[f.key] = $$(`input[name="${f.key}"]:checked`, root).map((i) => i.value);
      else if (f.type === "check") out[f.key] = $(`input[name="${f.key}"]`, root).checked;
      else if (f.type === "scale") out[f.key] = $(`input[name="${f.key}"]:checked`, root)?.value ?? "";
      else out[f.key] = $(`[name="${f.key}"]`, root).value;
    }
    return out;
  }

  function showValue(f, v) {
    if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) return '<span class="adm-muted">—</span>';
    if (f.type === "points") return `<div class="pf-tags">${v.map((c) => pointChip(c, false)).join("")}</div>
      <div class="pf-doll-mini">${dollHtml(v, false)}</div>`;
    if (f.type === "multi") return `<div class="pf-tags">${v.map((x) => `<span class="pf-tag">${esc(x)}</span>`).join("")}</div>`;
    if (f.type === "check") return v ? "✅ Sim" : "Não";
    if (f.type === "date") return esc(dateBR(v));
    if (f.type === "scale") return `<span class="pf-meter"><span style="width:${Number(v) * 10}%"></span></span> <b>${esc(v)}</b>/10`;
    return esc(v).replace(/\n/g, "<br>");
  }

  function viewHtml(sections, data) {
    return sections.map((sec) => `
      <section class="adm-card pf-view-section">
        <h3>${sec.icon} ${esc(sec.title)}</h3>
        <dl class="pf-dl">${sec.fields.map((f) => `
          <div class="pf-dl__row ${f.type === "long" || f.type === "multi" ? "pf-dl__row--wide" : ""}"><dt>${esc(f.label)}</dt><dd>${showValue(f, data[f.key])}</dd></div>`).join("")}
        </dl>
      </section>`).join("");
  }

  async function loadPatientFile() {
    const [forms, file] = await Promise.all([getForms(), api(`/api/admin/patients/${state.patientId}/file`), loadPoints()]);
    state.file = file;
    const p = file.patient;
    const done = file.sessions.filter((s) => s.status === "done");
    const next = file.sessions.filter((s) => ["scheduled", "requested"].includes(s.status)).at(-1);
    $("#view-title").textContent = "Ficha do paciente";
    $("#pf-head").innerHTML = `
      ${clientAvatar(p, "adm-client__avatar pf-avatar")}
      <div class="pf-head__info">
        <h2>${esc(p.name)} <span class="adm-badge adm-badge--${p.active ? "active" : "inactive"}">${p.active ? "Ativo" : "Desativado"}</span>
          ${p.social ? '<span class="social-badge" title="Participa do Ambulatório Social">🤝 Ambulatório Social</span>' : ""}</h2>
        <p class="adm-muted">${esc(p.email)}${p.phone ? ` · ${esc(p.phone)}` : ""} · cliente desde ${dateBR(p.created_at)}</p>
      </div>
      <button class="adm-btn pf-social-btn ${p.social ? "is-on" : ""}" data-social-toggle="${p.id}" data-on="${p.social ? 1 : 0}" type="button"
        title="Projeto Ambulatório Social de Acupuntura (R$ 50,00 · 60 min)">🤝 ${p.social ? "No Ambulatório Social" : "Incluir no Ambulatório Social"}</button>
      <button class="adm-btn pf-print-btn" data-print-menu type="button">🖨️ Relatórios</button>
      <button class="adm-btn adm-btn--primary pf-3d-btn" data-patient-3d type="button">🧍 Pontos no corpo 3D</button>
      <div class="pf-head__stats">
        <div><b>${done.length}</b><span>sessões realizadas</span></div>
        <div><b>${done[0] ? dateBR(done[0].date) : "—"}</b><span>última sessão</span></div>
        <div><b>${next ? dateBR(next.date) : "—"}</b><span>próxima</span></div>
      </div>`;
    renderPersonal(forms, p.profile || {});
    renderRecord(forms, file.record);
    renderProtocols(file.sessions);
    switchTab(state.pfTab || "record");
  }

  function switchTab(tab) {
    state.pfTab = tab;
    $$("[data-pf-tab]").forEach((b) => b.classList.toggle("is-active", b.dataset.pfTab === tab));
    $("#pf-record").hidden = tab !== "record";
    $("#pf-protocols").hidden = tab !== "protocols";
    $("#pf-personal").hidden = tab !== "personal";
  }
  $$("[data-pf-tab]").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.pfTab)));

  // Dados pessoais (endereço, documentos, contato de emergência) — o cliente também edita em "Meus dados"
  function renderPersonal(forms, profile, editing = false) {
    const box = $("#pf-personal");
    const filled = Object.keys(profile).length;
    if (editing) {
      box.innerHTML = `<form class="adm-form pf-form" id="personal-form" novalidate>
          ${formHtml(forms.profile, profile)}
          <p class="adm-form__error" role="alert"></p>
          <div class="adm-form__actions pf-sticky-actions">
            <button class="adm-btn adm-btn--ghost" data-personal-cancel type="button">Cancelar</button>
            <button class="adm-btn adm-btn--primary" type="submit">Salvar dados pessoais</button>
          </div></form>`;
      const f = $("#personal-form");
      f.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          await api(`/api/admin/patients/${state.patientId}/profile`, { method: "PUT", body: { profile: readFields(f, forms.profile) } });
          toast("Dados pessoais salvos.");
          state.pfTab = "personal";
          loadPatientFile();
        } catch (err) { $(".adm-form__error", f).textContent = err.message; }
      });
      $("[data-personal-cancel]", f).addEventListener("click", () => renderPersonal(forms, profile));
      return;
    }
    box.innerHTML = `<div class="pf-toolbar">
        <span class="adm-muted">${filled ? "Preenchido pelo cliente ou pela clínica." : "O cliente ainda não preencheu os dados pessoais."}</span>
        <button class="adm-btn adm-btn--primary" data-personal-edit type="button">✎ ${filled ? "Editar" : "Preencher"} dados pessoais</button>
      </div>
      <div class="pf-view">${viewHtml(forms.profile, profile)}</div>`;
    $("[data-personal-edit]", box).addEventListener("click", () => renderPersonal(forms, profile, true));
  }

  function renderRecord(forms, record, editing = false) {
    const box = $("#pf-record");
    if (editing) {
      box.innerHTML = `
        <form class="adm-form pf-form" id="record-form" novalidate>
          ${formHtml(forms.record, record?.data || {})}
          <p class="adm-form__error" role="alert"></p>
          <div class="adm-form__actions pf-sticky-actions">
            <button class="adm-btn adm-btn--ghost" data-record-cancel type="button">Cancelar</button>
            <button class="adm-btn adm-btn--primary" type="submit">Salvar prontuário</button>
          </div>
        </form>`;
      const f = $("#record-form");
      f.addEventListener("submit", async (e) => {
        e.preventDefault();
        try {
          await api(`/api/admin/patients/${state.patientId}/record`, { method: "PUT", body: readFields(f, forms.record) });
          toast("Prontuário salvo.");
          window.scrollTo({ top: 0 });
          loadPatientFile();
        } catch (err) { $(".adm-form__error", f).textContent = err.message; }
      });
      $("[data-record-cancel]", f).addEventListener("click", () => renderRecord(forms, record));
      return;
    }
    if (!record) {
      box.innerHTML = `
        <div class="adm-card pf-empty">
          <p class="pf-empty__icon">📋</p>
          <h3>Prontuário ainda não preenchido</h3>
          <p class="adm-muted">A ficha fixa do paciente é preenchida uma vez, geralmente na primeira consulta, e pode ser editada depois.</p>
          <button class="adm-btn adm-btn--primary" data-record-edit type="button">Preencher prontuário</button>
        </div>`;
    } else {
      box.innerHTML = `
        <div class="pf-toolbar">
          <span class="adm-muted">Atualizado em ${dateBR(record.updated_at)} às ${record.updated_at.slice(11, 16)}</span>
          <button class="adm-btn adm-btn--primary" data-record-edit type="button">✎ Editar prontuário</button>
        </div>
        <div class="pf-view">${viewHtml(forms.record, record.data)}</div>`;
    }
    $("[data-record-edit]", box).addEventListener("click", () => renderRecord(forms, record, true));
  }

  function renderProtocols(sessions) {
    const list = sessions.filter((s) => ["scheduled", "done"].includes(s.status));
    const filled = list.filter((s) => s.protocol).length;
    $("#pf-count").textContent = list.length ? `(${filled}/${list.length})` : "";
    $("#pf-protocols").innerHTML = list.length ? `<div class="pf-timeline">${list.map((s) => {
      const p = s.protocol;
      const d = fromIso(s.date);
      return `
        <article class="adm-card pf-session ${p ? "" : "pf-session--pending"}">
          <div class="cli-date" aria-hidden="true"><span>${fmt(d, { month: "short" }).replace(".", "")}</span><b>${d.getDate()}</b></div>
          <div class="pf-session__body">
            <div class="pf-session__top">
              <b>${cap(fmt(d, { weekday: "long", day: "numeric", month: "long", year: "numeric" }))}</b>
              <span class="adm-muted">${esc(s.start)}–${esc(s.end)}</span>
              <span class="adm-badge adm-badge--${s.status}">${STATUS[s.status]}</span>
            </div>
            ${p ? `
              <div class="pf-tags">${(p.techniques || []).map((t) => `<span class="pf-tag">${esc(t)}</span>`).join("")}</div>
              ${(p.acupoints || []).length ? `<div class="pf-tags">${p.acupoints.map((c) => pointChip(c, false)).join("")}</div>
              <div class="pf-doll-mini" title="Pontos usados nesta sessão">${dollHtml(p.acupoints, false)}</div>` : ""}
              ${p.pain_before !== undefined || p.pain_after !== undefined
                ? `<p class="pf-pain">Intensidade: <b>${p.pain_before ?? "—"}</b> → <b>${p.pain_after ?? "—"}</b></p>` : ""}
              ${p.complaint_today ? `<p class="adm-muted pf-snippet">${esc(p.complaint_today)}</p>` : ""}`
              : '<p class="adm-muted">Protocolo ainda não preenchido.</p>'}
          </div>
          <div class="pf-session__act">
            <button class="adm-btn adm-btn--sm ${p ? "" : "adm-btn--primary"}" data-protocol="${s.id}" data-patient="${state.patientId}" type="button">
              ${p ? "Ver / editar" : "Preencher"}</button>
            ${p ? `<button class="adm-btn adm-btn--sm" data-print-patient="session" data-session="${s.id}" type="button" title="Imprimir / PDF desta consulta">🖨️ Imprimir</button>` : ""}
          </div>
        </article>`;
    }).join("")}</div>`
      : '<p class="adm-empty">Nenhuma consulta confirmada ou realizada ainda. Os protocolos aparecem aqui a cada sessão.</p>';
  }


  // ---------------------------------------------------------------- relatórios do paciente (imprimir / PDF)
  function printValue(f, v) {
    const E = window.AjnaPrint.esc;
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return '<span class="muted">—</span>';
    if (f.type === "points") return v.map((c) => {
      const p = mp.byCode[c];
      return `<span class="tag">${E(c.replace("OR-", "Orelha "))}${p?.pinyin ? ` · ${E(p.pinyin)}` : ""}${p?.name_pt ? ` (${E(p.name_pt)})` : ""}</span>`;
    }).join(" ");
    if (f.type === "multi") return v.map((x) => `<span class="tag">${E(x)}</span>`).join(" ");
    if (f.type === "check") return v ? "Sim" : "Não";
    if (f.type === "date") return E(dateBR(v));
    if (f.type === "scale") return `${E(v)} / 10`;
    return E(v);
  }

  const printSections = (sections, data) => sections.map((sec) => {
    const rows = sec.fields.map((f) => `<dt>${window.AjnaPrint.esc(f.label)}</dt><dd>${printValue(f, data[f.key])}</dd>`).join("");
    return `<h3>${sec.icon} ${window.AjnaPrint.esc(sec.title)}</h3><dl class="kv">${rows}</dl>`;
  }).join("");


  // Relatório de acompanhamento: evolução do paciente ao longo das sessões
  function followupHtml(file) {
    const E = window.AjnaPrint.esc;
    const all = [...file.sessions].sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start));
    const done = all.filter((s) => s.status === "done");
    const cancelled = all.filter((s) => s.status === "cancelled").length;
    const upcoming = all.filter((s) => ["scheduled", "requested"].includes(s.status) && s.date >= iso(new Date()));
    const num = (v) => (v === undefined || v === null || v === "" ? null : Number(v));
    if (!done.length) {
      return `<div class="sheet"><h2>📈 Relatório de acompanhamento</h2><p class="muted">O paciente ainda não tem sessões realizadas.</p></div>`;
    }
    const first = done[0].date, last = done.at(-1).date;
    const days = Math.max(30.4, (fromIso(last) - fromIso(first)) / 86400000); // menos de 1 mês conta como 1 mês
    const perMonth = done.length > 1 ? (done.length / (days / 30.4)).toFixed(1).replace(".", ",") : "—";
    const baseline = num(file.record?.data?.pain_scale);

    // intensidade da queixa por sessão
    const pains = done.map((s) => ({ s, before: num(s.protocol?.pain_before), after: num(s.protocol?.pain_after) }))
      .filter((x) => x.before !== null || x.after !== null);
    const firstBefore = pains.find((x) => x.before !== null)?.before ?? baseline;
    const lastValue = [...pains].reverse().map((x) => x.after ?? x.before).find((v) => v !== null && v !== undefined);
    const drops = pains.filter((x) => x.before !== null && x.after !== null).map((x) => x.before - x.after);
    const avgDrop = drops.length ? (drops.reduce((a, b) => a + b, 0) / drops.length).toFixed(1).replace(".", ",") : null;
    let evolution = "Sem registros de intensidade nos protocolos.";
    if (firstBefore !== null && firstBefore !== undefined && lastValue !== undefined) {
      const diff = firstBefore - lastValue;
      const pct = firstBefore ? Math.round((diff / firstBefore) * 100) : 0;
      evolution = diff > 0 ? `Melhora de <b>${diff} ponto(s)</b> (${pct}%): de ${firstBefore}/10 para ${lastValue}/10.`
        : diff < 0 ? `Piora de <b>${-diff} ponto(s)</b>: de ${firstBefore}/10 para ${lastValue}/10.`
        : `Intensidade estável em ${lastValue}/10.`;
    }

    // gráfico da intensidade (antes x depois) por sessão
    let chart = "";
    if (pains.length) {
      const W = 640, H = 200, P = { l: 30, r: 12, t: 12, b: 28 };
      const n = pains.length;
      const x = (i) => P.l + (n === 1 ? (W - P.l - P.r) / 2 : ((W - P.l - P.r) / (n - 1)) * i);
      const y = (v) => P.t + (H - P.t - P.b) * (1 - v / 10);
      const line = (key, color) => {
        const pts = pains.map((p, i) => (p[key] === null ? null : `${x(i)},${y(p[key])}`)).filter(Boolean);
        return `<polyline points="${pts.join(" ")}" fill="none" stroke="${color}" stroke-width="2.5"/>` +
          pains.map((p, i) => (p[key] === null ? "" : `<circle cx="${x(i)}" cy="${y(p[key])}" r="4" fill="${color}"/>`)).join("");
      };
      const grid = [0, 2, 4, 6, 8, 10].map((v) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" stroke="#eee5f2"/>
        <text x="${P.l - 6}" y="${y(v) + 4}" font-size="10" fill="#6c5b73" text-anchor="end">${v}</text>`).join("");
      const labels = pains.map((p, i) => `<text x="${x(i)}" y="${H - 8}" font-size="10" fill="#6c5b73" text-anchor="middle">${E(dateBR(p.s.date).slice(0, 5))}</text>`).join("");
      chart = `<h3>Intensidade da queixa por sessão (0 a 10)</h3>
        <svg viewBox="0 0 ${W} ${H}" style="width:100%;max-height:220px">${grid}${line("before", "#d9566f")}${line("after", "#2f9e5b")}${labels}</svg>
        <p class="muted"><span style="color:#d9566f">●</span> antes da sessão &nbsp; <span style="color:#2f9e5b">●</span> depois da sessão</p>`;
    }

    // técnicas e pontos mais usados
    const count = (arrs) => {
      const m = {};
      arrs.flat().forEach((k) => { m[k] = (m[k] || 0) + 1; });
      return Object.entries(m).sort((a, b) => b[1] - a[1]);
    };
    const techniques = count(done.map((s) => s.protocol?.techniques || []));
    const points = count(done.map((s) => s.protocol?.acupoints || [])).slice(0, 15);
    const pointName = (c) => {
      const p = mp.byCode[c];
      return `${E(c.replace("OR-", "Orelha "))}${p?.pinyin ? ` · ${E(p.pinyin)}` : ""}`;
    };

    const table = done.map((s, i) => {
      const pr = s.protocol || {};
      return `<tr><td>${i + 1}</td><td>${E(dateBR(s.date))}</td>
        <td>${E((pr.techniques || []).join(", ") || "—")}</td>
        <td>${(pr.acupoints || []).length || "—"}</td>
        <td class="num">${num(pr.pain_before) ?? "—"} → ${num(pr.pain_after) ?? "—"}</td>
        <td>${E(pr.complaint_today || "") || '<span class="muted">—</span>'}</td></tr>`;
    }).join("");

    // começa numa folha nova (a anamnese fica na 1ª folha, o acompanhamento na 2ª)
    return `<div class="sheet"><h2>📈 Relatório de acompanhamento</h2>
      <div class="totals">
        <div><span>Sessões realizadas</span><b>${done.length}</b></div>
        <div><span>Período</span><b style="font-size:13px">${E(dateBR(first))} a ${E(dateBR(last))}</b></div>
        <div><span>Frequência média</span><b>${perMonth}</b> <span>sessão(ões) por mês</span></div>
        <div><span>Faltas / cancelamentos</span><b>${cancelled}</b></div>
      </div>
      <h3>Evolução</h3>
      <dl class="kv">
        ${baseline !== null && baseline !== undefined ? `<dt>Intensidade na anamnese</dt><dd>${baseline}/10</dd>` : ""}
        <dt>Evolução da queixa</dt><dd>${evolution}</dd>
        ${avgDrop !== null ? `<dt>Alívio médio por sessão</dt><dd>${avgDrop} ponto(s) (antes → depois)</dd>` : ""}
        <dt>Protocolos preenchidos</dt><dd>${done.filter((s) => s.protocol).length} de ${done.length} sessões</dd>
        <dt>Próximas consultas</dt><dd>${upcoming.length ? upcoming.map((s) => `${E(dateBR(s.date))} ${E(s.start)}`).join(", ") : "Nenhuma marcada"}</dd>
      </dl>
      ${chart}
      ${techniques.length ? `<h3>Técnicas utilizadas</h3><p>${techniques.map(([t, n]) => `<span class="tag">${E(t)} · ${n}×</span>`).join(" ")}</p>` : ""}
      ${points.length ? `<h3>Pontos mais utilizados</h3><p>${points.map(([c, n]) => `<span class="tag">${pointName(c)} · ${n}×</span>`).join(" ")}</p>` : ""}
      <h3>Histórico das sessões</h3>
      <table><thead><tr><th>#</th><th>Data</th><th>Técnicas</th><th>Pontos</th><th class="num">Intensidade</th><th>Relato do paciente</th></tr></thead>
        <tbody>${table}</tbody></table></div>`;
  }

  async function printPatient(mode, sessionId) {
    const [forms, file] = await Promise.all([getForms(), api(`/api/admin/patients/${state.patientId}/file`), loadPoints()]);
    const E = window.AjnaPrint.esc;
    const p = file.patient;
    const head = `<h2>Paciente</h2><dl class="kv">
      <dt>Nome</dt><dd>${E(p.name)}${p.social ? " · 🤝 Ambulatório Social" : ""}</dd>
      <dt>E-mail</dt><dd>${E(p.email)}</dd>${p.phone ? `<dt>Telefone</dt><dd>${E(p.phone)}</dd>` : ""}
      <dt>Cliente desde</dt><dd>${E(dateBR(p.created_at))}</dd>
      <dt>Sessões realizadas</dt><dd>${file.sessions.filter((s) => s.status === "done").length}</dd></dl>
      ${Object.keys(p.profile || {}).length ? `<h2>🪪 Dados pessoais</h2>${printSections(forms.profile, p.profile)}` : ""}`;
    const anamnese = `<h2>📋 Ficha de anamnese</h2>${file.record?.data
      ? printSections(forms.record, file.record.data) + (file.record.updated_at ? `<p class="muted">Última atualização: ${E(dateBR(file.record.updated_at))}</p>` : "")
      : '<p class="muted">Ficha de anamnese ainda não preenchida.</p>'}`;
    const sessionHtml = (s) => `<div class="session"><h3>${E(cap(fmt(fromIso(s.date), { weekday: "long", day: "numeric", month: "long", year: "numeric" })))} · ${E(s.start)}–${E(s.end)}
      <span class="muted">(${E(STATUS[s.status] || s.status)})</span></h3>
      ${s.protocol ? printSections(forms.protocol, s.protocol) : '<p class="muted">Protocolo não preenchido.</p>'}</div>`;
    const sessions = file.sessions.filter((s) => ["scheduled", "done"].includes(s.status));
    let title, html;
    if (mode === "record") {
      title = "Ficha de anamnese e acompanhamento";
      html = head + anamnese + followupHtml(file);
    } else if (mode === "followup") {
      title = "Relatório de acompanhamento";
      html = head + followupHtml(file);
    } else if (mode === "session") {
      const s = file.sessions.find((x) => x.id === Number(sessionId));
      if (!s) return toast("Consulta não encontrada.", true);
      title = "Ficha da consulta";
      html = head + `<h2>📝 Consulta</h2>` + sessionHtml(s);
    } else {
      title = "Prontuário completo";
      const withProtocol = sessions.filter((s) => s.protocol);
      html = head + anamnese + followupHtml(file) + `<h2>📝 Consultas (${withProtocol.length} com protocolo)</h2>` +
        (withProtocol.map(sessionHtml).join("") || '<p class="muted">Nenhuma consulta com protocolo ainda.</p>');
    }
    window.AjnaPrint.open({ title, subtitle: p.name, html, confidential: true });
  }

  function openPrintMenu() {
    const file = state.file;
    const list = file.sessions.filter((s) => ["scheduled", "done"].includes(s.status) && s.protocol);
    $("#print-menu-sessions").innerHTML = list.length
      ? list.map((s) => `<button class="adm-btn adm-btn--sm" data-print-patient="session" data-session="${s.id}" type="button">
          📝 ${esc(dateBR(s.date))} · ${esc(s.start)}</button>`).join("")
      : '<p class="adm-muted">Nenhuma consulta com protocolo preenchido ainda.</p>';
    $("#print-menu").showModal();
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-print-menu]")) return void openPrintMenu();
    const b = e.target.closest("[data-print-patient]");
    if (!b) return;
    $("#print-menu").close();
    printPatient(b.dataset.printPatient, b.dataset.session).catch((err) => toast(err.message, true));
  });

  // Modal do protocolo (abre pela ficha, pela agenda ou pela visão geral)
  const protocolModal = $("#protocol-modal");
  const protocolForm = $("#protocol-form");

  async function openProtocol(appointmentId, patientId) {
    const [forms, file] = await Promise.all([getForms(), api(`/api/admin/patients/${patientId}/file`), loadPoints()]);
    const s = file.sessions.find((x) => x.id === Number(appointmentId));
    if (!s) return toast("Consulta não encontrada.", true);
    protocolForm.dataset.id = s.id;
    $("#protocol-title").textContent =
      `${file.patient.name} · ${cap(fmt(fromIso(s.date), { weekday: "short", day: "numeric", month: "short" }))}, ${s.start}`;
    $("#protocol-fields").innerHTML = formHtml(forms.protocol, s.protocol || {});
    $(".adm-form__error", protocolForm).textContent = "";
    protocolModal.showModal();
    protocolModal.scrollTop = 0;
  }

  protocolForm.addEventListener("submit", async (event) => {
    if (event.submitter?.value === "cancel") return;
    event.preventDefault();
    const forms = await getForms();
    try {
      await api(`/api/admin/appointments/${protocolForm.dataset.id}/protocol`, {
        method: "PUT", body: readFields(protocolForm, forms.protocol),
      });
      protocolModal.close();
      toast("Protocolo salvo.");
      refresh();
    } catch (err) { $(".adm-form__error", protocolForm).textContent = err.message; }
  });

  document.addEventListener("click", (event) => {
    const open = event.target.closest("[data-open-patient]");
    if (open) { state.pfTab = "record"; return show(`paciente-${open.dataset.openPatient}`); }
    const proto = event.target.closest("[data-protocol]");
    if (proto) openProtocol(proto.dataset.protocol, proto.dataset.patient).catch((e) => toast(e.message, true));
  });

  // ---------------------------------------------------------------- mapa de pontos (acupuntura)
  // Dados: /api/admin/acupoints (361 pontos da OMS + extras). Posições esquemáticas e editáveis.
  const SVGNS = "http://www.w3.org/2000/svg";
  const BASES = { body: { x: 0, y: 0, w: 300, h: 710 }, ear: { x: 0, y: 0, w: 240, h: 340 } };
  const baseFor = (view) => (view === "ear" ? BASES.ear : BASES.body);
  // "BASE_VB" sempre devolve a base da vista atual
  const BASE_VB = {
    get x() { return baseFor(mp.view).x; }, get y() { return baseFor(mp.view).y; },
    get w() { return baseFor(mp.view).w; }, get h() { return baseFor(mp.view).h; },
  };
  const mp = {
    loaded: false, points: [], byCode: {}, meridians: [], merById: {},
    view: "front", filter: null, selected: null, vb: { x: 0, y: 0, w: 300, h: 710 },
    usage: null, dragging: null, dragOrig: null, labels: false,
    mode: "2d", viewer: null, layer: "skin",
  };

  // ---------- 3D (carregado só quando a Ellen abre o modo 3D)
  function styleOf(code) {
    const p = mp.byCode[code];
    return {
      color: merColor(p?.meridian),
      dim: (mp.filter && p?.meridian !== mp.filter) || (mp.usage && !mp.usage[code]),
      used: !!mp.usage?.[code],
      selected: mp.selected === code,
    };
  }

  function syncBodyButtons(body, available) {
    $$("[data-mp-body]").forEach((x) => x.classList.toggle("is-active", x.dataset.mpBody === body));
    $$("[data-mp-layer]").forEach((x) => {
      const ok = available.includes(x.dataset.mpLayer);
      x.disabled = !ok;
      x.title = ok ? "" : "Não disponível no corpo feminino";
    });
  }

  // Modos: "2d" (corpo 2D), "3d" (corpo 3D) e "ear" (orelha 2D separada, auriculoterapia)
  async function setMode(mode) {
    if (mode !== "ear") mode = "3d";
    const wasEar = mp.mode === "ear";
    mp.mode = mode;
    const is3d = mode === "3d";
    const isEar = mode === "ear";
    $$("[data-mp-mode]").forEach((b) => b.classList.toggle("is-active", b.dataset.mpMode === mode));
    $$(".mp-only-3d").forEach((el) => (el.hidden = !is3d));
    $(".mp-views").hidden = isEar;
    $(".mp-regions").hidden = isEar;
    $("#mp-meridians").hidden = isEar;
    $('[data-mp-zoom="reset"]').textContent = isEar ? "Orelha toda" : "Corpo todo";
    if (isEar && mp.filter && mp.filter !== "OR") mp.filter = null;
    $("#mp-stage").classList.toggle("is-ear", isEar);
    $("#mp-svg").style.display = is3d ? "none" : "";
    $("#mp-3d").hidden = !is3d;
    $(".mp-zoom").hidden = is3d;
    if (isEar) {
      mp.view = "ear";
      mp.vb = { ...baseFor("ear") };
    } else if (wasEar || mp.view === "ear") {
      mp.view = "front";
      mp.vb = { ...baseFor("front") };
    }
    if (!is3d) {
      mp.viewer?.pause(true);
      renderMap();
      renderPanel();
      localStorage.setItem("ajna-map-mode", mode);
      return;
    }
    if (is3d && !mp.viewer) {
      try {
        const mod = await import("./map3d.js");
        mp.viewer = await mod.createViewer($("#mp-3d"), {
          model: "f",
          getPoints: () => mp.points,
          styleOf,
          onSelect: (code) => selectPoint(code),
          onHover: (_code, structure) => ($("#mp-under").textContent = structure ? `Sob o cursor: ${structure}` : ""),
        });
      } catch (err) {
        console.error(err);
        window.__map3dError = String(err?.stack || err);
        toast("Não foi possível abrir o 3D neste navegador. Atualize o navegador ou use outro.", true);
        return setMode("ear");
      }
    }
    mp.viewer?.pause(!is3d);
    if (is3d) syncBodyButtons(mp.viewer.model, mp.viewer.layersAvailable());
    if (is3d) {
      mp.viewer.refresh();
      if (mp.selected) mp.viewer.select(mp.selected, { fly: true });
    }
    localStorage.setItem("ajna-map-mode", mode);
  }

  async function loadPoints(force = false) {
    if (mp.loaded && !force) return;
    const data = await api("/api/admin/acupoints");
    mp.points = data.points;
    mp.meridians = data.meridians;
    mp.byCode = Object.fromEntries(data.points.map((p) => [p.code, p]));
    mp.merById = Object.fromEntries(data.meridians.map((m) => [m.code, m]));
    mp.loaded = true;
    $("#acupoint-list").innerHTML = mp.points
      .map((p) => `<option value="${esc(p.code)}">${esc(p.code)} · ${esc(p.pinyin)}${p.name_pt ? ` — ${esc(p.name_pt)}` : ""}</option>`)
      .join("");
  }

  const pointLabel = (code) => {
    const p = mp.byCode[code];
    return p ? `${p.code} · ${p.pinyin}` : code;
  };
  const merColor = (code) => mp.merById[code]?.color || "#6c5b73";
  const isBilateral = (p) => mp.merById[p.meridian]?.bilateral;

  // ---------- desenho do corpo (contorno anatômico simplificado, frente e costas)
  // Metade esquerda da tela, de cima (pescoço) até a virilha; a direita é espelhada.
  const HALF_OUTLINE = [
    [141, 98], [139, 116], [120, 122], [103, 128], [93, 142], [87, 175], [82, 215], [72, 250], [64, 295],
    [60, 345], [53, 362], [49, 384], [52, 402], [60, 414], [69, 413], [76, 401], [78, 376], [79, 352],
    [85, 300], [93, 255], [99, 210], [104, 172], [103, 200], [105, 232], [106, 258], [102, 296],
    [97, 336], [96, 380], [99, 440], [103, 505], [100, 560], [107, 620], [108, 652], [101, 680],
    [104, 700], [118, 707], [131, 703], [134, 682], [134, 655], [139, 600], [142, 552], [145, 505],
    [147, 440], [148, 372], [150, 360],
  ];

  // Curva suave passando pelos pontos (Catmull-Rom -> Bézier)
  function smoothPath(pts) {
    let d = `M${pts[0][0]} ${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += ` C${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${p2[0]} ${p2[1]}`;
    }
    return d;
  }
  const BODY_PATH = (() => {
    const right = HALF_OUTLINE.slice(0, -1).reverse().map(([x, y]) => [300 - x, y]);
    return smoothPath([...HALF_OUTLINE, ...right]) + " Z";
  })();

  // ---------- desenho da orelha (auriculoterapia) — orelha direita vista de lado, 240 x 340
  const EAR_REGIONS = { HX: "Hélice", SF: "Escafa", AH: "Anti-hélice", TF: "Fossa triangular",
                        TG: "Trago", AT: "Antítrago", CO: "Concha", LO: "Lóbulo" };
  function earSvg() {
    return `
      <g class="mp-body mp-ear">
        <path class="mp-skin mp-outline" d="M96 258 C74 236 66 180 76 128 C88 66 134 26 178 38 C214 50 226 104 218 160
          C212 206 196 236 186 268 C178 300 160 330 128 330 C104 330 92 310 92 286 C92 276 94 266 96 258 Z"/>
        <path class="mp-ear-fold" d="M98 120 C108 76 144 52 176 60 C202 68 208 112 202 156 C196 196 184 226 176 252"/>
        <path class="mp-ear-ridge" d="M150 246 C166 224 176 196 176 168 L178 84 M176 168 C160 150 136 132 112 118"/>
        <path class="mp-ear-hollow" d="M108 132 C140 138 166 150 170 170 C172 200 160 236 146 244 C128 252 104 244 94 230
          C88 212 86 190 90 176 C94 160 100 140 108 132 Z"/>
        <path class="mp-ear-fossa" d="M118 116 C140 96 164 86 176 88 L176 160 C160 146 138 128 118 116 Z"/>
        <path class="mp-ear-ridge mp-ear-crus" d="M80 176 C98 168 120 166 140 172"/>
        <path class="mp-skin" d="M70 190 C62 200 62 226 74 236 C84 228 86 204 78 192 Z"/>
        <path class="mp-skin" d="M108 246 C120 238 140 238 150 248 C140 262 118 264 108 256 Z"/>
        <path class="mp-ear-grid" d="M100 289 L172 289 M100 307 L172 307 M124 272 L124 326 M148 272 L148 326"/>
        <g class="mp-ear-labels">
          <text x="224" y="120">Hélice</text><text x="206" y="232">Escafa</text>
          <text x="186" y="196">Anti-hélice</text><text x="140" y="80">Fossa triangular</text>
          <text x="132" y="140">Concha cimba</text><text x="128" y="224">Concha cava</text>
          <text x="44" y="212">Trago</text><text x="128" y="270">Antítrago</text><text x="190" y="304">Lóbulo</text>
        </g>
        <text x="120" y="14" class="mp-view-label">ORELHA ESQUERDA · vale para as duas</text>
      </g>`;
  }

  function bodySvg(view) {
    if (view === "ear") return earSvg();
    const isFront = view === "front";
    const ears = `<ellipse cx="117" cy="64" rx="6" ry="11" class="mp-skin"/><ellipse cx="183" cy="64" rx="6" ry="11" class="mp-skin"/>`;
    const fingers = (m) => {
      const X = (x) => (m ? 300 - x : x);
      return [[52, 402, 50, 414], [57, 408, 56, 420], [63, 411, 63, 423], [69, 410, 70, 420]]
        .map(([a, b, c, d]) => `<path d="M${X(a)} ${b} L${X(c)} ${d}"/>`).join("")
        + `<path d="M${X(76)} ${392} q${m ? -5 : 5} 8 ${m ? -3 : 3} 16"/>`;
    };
    const front = `
      <g class="mp-detail">
        <path d="M130 56 q7 -5 14 0 M156 56 q7 -5 14 0"/>
        <ellipse cx="137" cy="60" rx="4" ry="2"/><ellipse cx="163" cy="60" rx="4" ry="2"/>
        <path d="M150 60 L146 75 Q150 78 154 75"/><path d="M140 87 Q150 92 160 87"/>
        <path d="M112 123 Q132 117 147 124 M153 124 Q168 117 188 123"/>
        <path d="M118 165 Q128 186 146 172 M182 165 Q172 186 154 172"/>
        <circle cx="128" cy="175" r="2"/><circle cx="172" cy="175" r="2"/>
        <path d="M150 184 L150 210"/><path d="M128 212 Q150 222 172 212"/>
        <circle cx="150" cy="262" r="2.4"/>
        <path d="M118 318 Q134 340 150 350 Q166 340 182 318"/>
        <path d="M117 497 q8 -8 17 0 q-8 8 -17 0 M166 497 q8 -8 17 0 q-8 8 -17 0"/>
        ${fingers(false)}${fingers(true)}
        <path d="M110 700 L110 706 M117 702 L117 707 M124 702 L124 707 M190 700 L190 706 M183 702 L183 707 M176 702 L176 707"/>
      </g>`;
    const back = `
      <g class="mp-detail">
        <path d="M119 50 Q150 14 181 50 Q170 34 150 32 Q130 34 119 50 Z" class="mp-hair"/>
        <path d="M150 108 L150 336" stroke-dasharray="2 3"/>
        <path d="M112 140 Q118 176 136 190 Q140 160 128 138 M188 140 Q182 176 164 190 Q160 160 172 138"/>
        <path d="M128 300 Q150 312 172 300"/>
        <path d="M104 362 Q126 372 148 360 M152 360 Q174 372 196 362"/>
        <path d="M150 336 L150 360"/>
        <path d="M112 505 q11 5 22 0 M166 505 q11 5 22 0"/>
        <path d="M113 560 q9 18 1 40 M187 560 q-9 18 -1 40"/>
        ${fingers(false)}${fingers(true)}
      </g>`;
    return `
      <g class="mp-body">
        <path class="mp-skin mp-outline" d="${BODY_PATH}"/>
        ${ears}
        <ellipse class="mp-skin mp-outline" cx="150" cy="62" rx="32" ry="41"/>
        <path class="mp-skin" d="M141 94 L141 106 L159 106 L159 94 Z" stroke="none"/>
        ${isFront ? front : back}
        <text x="150" y="12" class="mp-view-label">${isFront ? "FRENTE" : "COSTAS"}</text>
        <text x="34" y="245" class="mp-side-label">${isFront ? "lado direito" : "lado esquerdo"}</text>
        <text x="266" y="245" class="mp-side-label">${isFront ? "lado esquerdo" : "lado direito"}</text>
      </g>`;
  }

  // Região do corpo de um ponto (a partir da posição no mapa) — ajuda a "achar no corpo".
  function bodyRegion(p) {
    if (p.view === "ear") {
      const pre = (p.intl_code || "").slice(0, 2);
      return `Orelha · ${EAR_REGIONS[pre] || "auriculoterapia"}`;
    }
    const x = Math.min(p.x, 300 - p.x); // lado esquerdo da tela
    const { y } = p;
    const back = p.view === "back";
    if (y < 106) return back ? "Cabeça (parte de trás) / nuca" : "Cabeça e rosto";
    if (y < 124) return "Pescoço";
    if (x < 100 && y < 420 && y > 120) {
      if (y < 145) return "Ombro";
      if (y < 240) return "Braço";
      if (y < 262) return "Cotovelo";
      if (y < 344) return "Antebraço";
      if (y < 360) return "Punho";
      return back ? "Mão (dorso)" : "Mão (palma) e dedos";
    }
    if (y < 345) {
      if (back) return y < 215 ? "Costas (região torácica)" : y < 300 ? "Lombar" : "Sacro / quadril";
      return y < 215 ? "Tórax" : y < 300 ? "Abdome" : "Baixo ventre / virilha";
    }
    if (y < 490) return back ? "Coxa (parte de trás)" : "Coxa";
    if (y < 520) return back ? "Atrás do joelho" : "Joelho";
    if (y < 645) return back ? "Panturrilha" : "Perna (canela)";
    if (y < 670) return "Tornozelo";
    return back ? "Calcanhar / sola do pé" : "Pé e dedos";
  }

  const REGIONS = {
    head: { x: 112, y: 14, w: 76 }, trunk: { x: 70, y: 100, w: 160 },
    arm: { x: 25, y: 110, w: 130 }, hand: { x: 28, y: 335, w: 72 },
    leg: { x: 60, y: 330, w: 180 }, foot: { x: 80, y: 600, w: 120 },
  };
  function zoomRegion(key) {
    if (key === "ear") { mp.view = "ear"; mp.vb = { ...baseFor("ear") }; return renderMap(); }
    if (mp.view === "ear") mp.view = "front";
    const r = REGIONS[key];
    const h = r.w * (BASE_VB.h / BASE_VB.w);
    mp.vb = { x: r.x, y: Math.min(r.y, BASE_VB.h - h), w: r.w, h };
    renderMap();
  }

  // ---------- pontos
  function visiblePoints() {
    return mp.points.filter((p) => p.view === mp.view);
  }

  function renderMap() {
    const svg = $("#mp-svg");
    const zoom = BASE_VB.w / mp.vb.w;
    const r = Math.max(1.3, 3.3 / Math.sqrt(zoom));
    const fs = Math.max(2.6, 7 / Math.sqrt(zoom));
    const showLabels = mp.labels || !!mp.filter || zoom >= 2.2;
    svg.setAttribute("viewBox", `${mp.vb.x} ${mp.vb.y} ${mp.vb.w} ${mp.vb.h}`);

    let paths = "";
    if (mp.filter) {
      const list = visiblePoints().filter((p) => p.meridian === mp.filter && !p.custom).sort((a, b) => a.number - b.number);
      const segs = [];
      let cur = [];
      list.forEach((p, i) => {
        if (i && p.number !== list[i - 1].number + 1) { segs.push(cur); cur = []; }
        cur.push(p);
      });
      segs.push(cur);
      const color = merColor(mp.filter);
      for (const seg of segs.filter((s) => s.length > 1)) {
        const pts = (m) => seg.map((p) => `${m ? 300 - p.x : p.x},${p.y}`).join(" ");
        paths += `<polyline points="${pts(false)}" class="mp-path" stroke="${color}"/>`;
        if (mp.merById[mp.filter]?.bilateral) paths += `<polyline points="${pts(true)}" class="mp-path" stroke="${color}"/>`;
      }
    }

    const dots = visiblePoints().map((p) => {
      const color = merColor(p.meridian);
      const dim = (mp.filter && p.meridian !== mp.filter) || (mp.usage && !mp.usage[p.code]);
      const sel = mp.selected === p.code;
      const used = mp.usage?.[p.code];
      const one = (x, mirror) => `
        <g class="mp-pt ${dim ? "is-dim" : ""} ${sel ? "is-sel" : ""}" data-code="${esc(p.code)}" data-mirror="${mirror ? 1 : 0}">
          ${sel ? `<circle cx="${x}" cy="${p.y}" r="${r * 2.4}" class="mp-ring" stroke="${color}"/>` : ""}
          ${used ? `<circle cx="${x}" cy="${p.y}" r="${r * 1.9}" class="mp-used"/>` : ""}
          <circle cx="${x}" cy="${p.y}" r="${sel ? r * 1.35 : r}" fill="${color}" class="mp-dot"/>
          ${(showLabels || used) && !dim ? `<text x="${x + r + 1}" y="${p.y + fs / 3}" font-size="${fs}" class="mp-label">${esc(p.code.replace("OR-", ""))}${used ? ` (${used})` : ""}</text>` : ""}
          <circle cx="${x}" cy="${p.y}" r="${Math.max(r * 2.2, 5 / zoom + r)}" class="mp-hit"/>
        </g>`;
      return one(p.x, false) + (isBilateral(p) ? one(300 - p.x, true) : "");
    });
    // pontos esmaecidos primeiro, destacados por cima
    dots.sort((a, b) => (a.includes("is-dim") ? 0 : 1) - (b.includes("is-dim") ? 0 : 1));
    if (mp.viewer && mp.mode === "3d") mp.viewer.refresh();
    svg.innerHTML = bodySvg(mp.view).replace('class="mp-view-label"', `class="mp-view-label" ${zoom > 1.4 ? 'display="none"' : ''}`) + paths + dots.join("");
    $$("[data-mp-view]").forEach((b) => b.classList.toggle("is-active", b.dataset.mpView === mp.view));
  }

  function renderMeridianChips() {
    const counts = {};
    mp.points.forEach((p) => (counts[p.meridian] = (counts[p.meridian] || 0) + 1));
    $("#mp-meridians").innerHTML =
      `<button class="mp-mer ${mp.filter ? "" : "is-active"}" data-mer="" type="button">Todos</button>` +
      mp.meridians.filter((m) => counts[m.code]).map((m) => `
        <button class="mp-mer ${mp.filter === m.code ? "is-active" : ""}" data-mer="${m.code}" type="button"
                style="--c:${m.color}" title="${esc(m.name)} (${m.intl})">
          <i></i>${m.code}<span>${counts[m.code]}</span>
        </button>`).join("");
  }

  // ---------- painel lateral
  async function renderPanel() {
    const panel = $("#mp-panel");
    const p = mp.selected && mp.byCode[mp.selected];
    if (!p) {
      const top = [...mp.points].filter((x) => x.used).sort((a, b) => b.used - a.used).slice(0, 8);
      if (mp.mode === "ear" && !mp.usage) {
        const ear = mp.points.filter((x) => x.view === "ear");
        const groups = {};
        ear.forEach((x) => (groups[EAR_REGIONS[(x.intl_code || "").slice(0, 2)] || "Outros"] ||= []).push(x));
        panel.innerHTML = `
          <h2 class="mp-panel__title">👂 Auriculoterapia</h2>
          <p class="adm-muted">${ear.length} pontos (nomenclatura GB/T 13734). Passe o mouse para ver o nome e clique para abrir.
          A orelha desenhada é a esquerda; os mesmos pontos valem para as duas.</p>
          ${Object.entries(groups).map(([region, pts]) => `
            <h3 class="mp-subtitle">${esc(region)} <span class="adm-muted">· ${pts.length}</span></h3>
            <div class="mp-point-grid">${pts.map((x) => `
              <button class="mp-point-chip" data-select="${esc(x.code)}" type="button"><b>${esc(x.intl_code)}</b><span>${esc(x.pinyin)}</span>${x.used ? `<em>${x.used}</em>` : ""}</button>`).join("")}
            </div>`).join("")}
          <button class="adm-btn adm-btn--ghost mp-new-ear" data-mp-new type="button">＋ Novo ponto da orelha</button>`;
        return;
      }
      if (mp.usage && !mp.filter) {
        const name = $("#mp-patient").selectedOptions[0]?.text || "";
        const used = Object.entries(mp.usage).sort((a, b) => b[1] - a[1]);
        panel.innerHTML = `
          <h2 class="mp-panel__title">🧘 Pontos usados com ${esc(name)}</h2>
          <p class="adm-muted">${used.length} ponto(s) em todos os protocolos. Pontos da frente e das costas aparecem em cada vista.</p>
          <div class="mp-point-grid">${used.map(([code, n]) => `
            <button class="mp-point-chip" data-select="${esc(code)}" type="button"><b>${esc(code)}</b><span>${esc(mp.byCode[code]?.pinyin || "")}</span><em>${n}</em></button>`).join("")}</div>`;
        return;
      }
      const mer = mp.filter && mp.merById[mp.filter];
      const merList = mer ? mp.points.filter((x) => x.meridian === mer.code) : [];
      panel.innerHTML = mer ? `
        <div class="mp-panel__head" style="--c:${mer.color}">
          <span class="mp-swatch"></span>
          <div><h2>${esc(mer.name)}</h2><p class="adm-muted">${mer.code} · ${mer.intl} · ${merList.length} pontos${mer.element !== "—" ? ` · ${esc(mer.element)}` : ""}</p></div>
        </div>
        <div class="mp-point-grid">${merList.map((x) => `
          <button class="mp-point-chip" data-select="${esc(x.code)}" type="button"><b>${esc(x.code)}</b><span>${esc(x.pinyin)}</span>${x.used ? `<em>${x.used}</em>` : ""}</button>`).join("")}
        </div>` : `
        <h2 class="mp-panel__title">☯ Mapa de pontos</h2>
        <p class="adm-muted">${mp.points.filter((x) => x.meridian !== "OR" && !x.custom).length} pontos clássicos da OMS ·
          ${mp.points.filter((x) => x.meridian === "OR").length} pontos de auriculoterapia (GB/T 13734)
          ${mp.points.some((x) => x.custom) ? ` · ${mp.points.filter((x) => x.custom).length} extras` : ""}.</p>
        <ul class="mp-help">
          <li><b>Clique</b> num ponto para ver e editar localização, indicações e observações.</li>
          <li><b>Filtre</b> por meridiano para ver o trajeto e a lista de pontos.</li>
          <li><b>Busque</b> pelo código (VB20) ou nome (Fengchi).</li>
          <li><b>Destaque</b> os pontos já usados com um paciente.</li>
          <li><b>Corrija</b> a posição arrastando o ponto (botão “Ajustar posição”).</li>
        </ul>
        <button class="adm-btn adm-btn--ghost" data-mp-new type="button">＋ Novo ponto extra</button>
        ${top.length ? `<h3 class="mp-subtitle">Mais usados nos protocolos</h3>
          <div class="mp-point-grid">${top.map((x) => `
            <button class="mp-point-chip" data-select="${esc(x.code)}" type="button"><b>${esc(x.code)}</b><span>${esc(x.pinyin)}</span><em>${x.used}</em></button>`).join("")}</div>` : ""}`;
      return;
    }

    const mer = mp.merById[p.meridian];
    const siblings = mp.points.filter((x) => x.meridian === p.meridian && !x.custom);
    const idx = siblings.findIndex((x) => x.code === p.code);
    panel.innerHTML = `
      <div class="mp-panel__head" style="--c:${mer?.color || "#6c5b73"}">
        <span class="mp-swatch"></span>
        <div>
          <h2>${esc(p.code)} <small>${esc(p.pinyin)}</small></h2>
          <p class="adm-muted">${esc(mer?.name || "")}${p.intl_code ? ` · ${esc(p.intl_code)}` : ""}${p.custom ? " · ponto extra" : ""}</p>
          <p class="mp-region">📍 ${esc(bodyRegion(p))} <span>· ${p.view === "ear" ? "auriculoterapia (vale para as duas orelhas)" : `vista de ${p.view === "front" ? "frente" : "costas"}`}${isBilateral(p) ? " · nos dois lados" : ""}</span></p>
        </div>
        <button class="adm-btn adm-btn--icon mp-close" data-mp-close type="button" aria-label="Fechar">×</button>
      </div>
      ${!p.custom ? `<div class="mp-nav">
        <button class="adm-btn adm-btn--sm" data-select="${esc(siblings[idx - 1]?.code || "")}" ${idx > 0 ? "" : "disabled"} type="button">‹ ${esc(siblings[idx - 1]?.code || "")}</button>
        <button class="adm-btn adm-btn--sm" data-select="${esc(siblings[idx + 1]?.code || "")}" ${idx < siblings.length - 1 ? "" : "disabled"} type="button">${esc(siblings[idx + 1]?.code || "")} ›</button>
      </div>` : ""}
      <form class="adm-form adm-form--inline mp-form" id="mp-form">
        <label>Nome em português<input name="name_pt" value="${esc(p.name_pt || "")}" placeholder="Ex.: Lago do Vento"></label>
        <label>📍 Localização<textarea name="location" rows="3" placeholder="Descreva como encontrar o ponto…">${esc(p.location || "")}</textarea></label>
        <label>💡 Indicações<textarea name="indications" rows="3" placeholder="Para que a clínica usa este ponto…">${esc(p.indications || "")}</textarea></label>
        <label>📝 Observações<textarea name="notes" rows="3" placeholder="Cuidados, profundidade, experiências…">${esc(p.notes || "")}</textarea></label>
        <p class="adm-form__error" role="alert"></p>
        <div class="adm-form__actions">
          ${p.updated_at ? `<span class="adm-muted mp-updated">Editado em ${dateBR(p.updated_at)}</span>` : ""}
          <button class="adm-btn adm-btn--primary" type="submit">Salvar textos</button>
        </div>
      </form>
      <div class="mp-actions">
        <button class="adm-btn adm-btn--sm" data-mp-move type="button">✋ Ajustar posição</button>
        ${p.custom ? "" : '<button class="adm-btn adm-btn--sm" data-mp-reset type="button">↺ Posição padrão</button>'}
        ${p.custom ? '<button class="adm-btn adm-btn--sm adm-btn--danger-ghost" data-mp-delete type="button">Excluir ponto</button>' : ""}
      </div>
      <h3 class="mp-subtitle">Usado em ${p.used || 0} sessão(ões)</h3>
      <div id="mp-sessions" class="mp-sessions"><p class="adm-muted">${p.used ? "Carregando…" : "Ainda não aparece em nenhum protocolo."}</p></div>`;

    $("#mp-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.currentTarget;
      try {
        const updated = await api(`/api/admin/acupoints/${encodeURIComponent(p.code)}`, {
          method: "PATCH", body: Object.fromEntries(new FormData(f)),
        });
        Object.assign(p, updated);
        toast(`${p.code} atualizado.`);
        renderPanel();
      } catch (err) { $(".adm-form__error", f).textContent = err.message; }
    });

    if (p.used) {
      const { items } = await api(`/api/admin/acupoints/${encodeURIComponent(p.code)}/sessions`);
      if (mp.selected !== p.code) return;
      $("#mp-sessions").innerHTML = items.map((s) => `
        <button class="mp-session" data-open-patient="${s.patient_id}" type="button">
          <b>${dateBR(s.date)}</b> ${esc(s.start)}<span>${esc(s.patient_name)}</span>
        </button>`).join("");
    }
  }

  function selectPoint(code, { focus = false } = {}) {
    const p = mp.byCode[code];
    if (!p) return;
    if (p.view === "ear" && mp.mode !== "ear") setMode("ear");
    else if (p.view !== "ear" && mp.mode === "ear") setMode("2d");
    mp.selected = code;
    if (p.view !== mp.view) mp.view = p.view;
    if (focus) {
      const w = p.view === "ear" ? 120 : 110, h = w * (BASE_VB.h / BASE_VB.w);
      mp.vb = { x: Math.min(Math.max(p.x - w / 2, 0), BASE_VB.w - w), y: Math.min(Math.max(p.y - h / 2, 0), BASE_VB.h - h), w, h };
    }
    renderMap();
    renderPanel();
    if (mp.mode === "3d" && mp.viewer) mp.viewer.select(code, { fly: true });
    if (window.matchMedia("(max-width: 1100px)").matches && !focus && mp.mode !== "3d") {
      $("#mp-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // ---------- zoom e arrastar o mapa
  function zoomBy(factor, cx, cy) {
    const vb = mp.vb;
    const w = Math.min(BASE_VB.w, Math.max(40, vb.w / factor));
    const h = w * (BASE_VB.h / BASE_VB.w);
    cx ??= vb.x + vb.w / 2;
    cy ??= vb.y + vb.h / 2;
    const x = cx - ((cx - vb.x) * w) / vb.w;
    const y = cy - ((cy - vb.y) * h) / vb.h;
    mp.vb = { x: Math.min(Math.max(x, 0), BASE_VB.w - w), y: Math.min(Math.max(y, 0), BASE_VB.h - h), w, h };
    renderMap();
  }

  function svgPoint(evt) {
    const svg = $("#mp-svg");
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function bindMap() {
    const svg = $("#mp-svg");
    const tip = $("#mp-tip");
    let pan = null;

    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const p = svgPoint(e);
      zoomBy(e.deltaY < 0 ? 1.25 : 0.8, p.x, p.y);
    }, { passive: false });

    svg.addEventListener("pointerdown", (e) => {
      const g = e.target.closest(".mp-pt");
      if (mp.dragging && g && g.dataset.code === mp.dragging) {
        mp.dragMirror = g.dataset.mirror === "1";
        svg.setPointerCapture(e.pointerId);
        mp.isDragging = true;
        return;
      }
      if (g) return;
      pan = { x: e.clientX, y: e.clientY, vb: { ...mp.vb }, moved: false };
      svg.setPointerCapture(e.pointerId);
    });

    svg.addEventListener("pointermove", (e) => {
      if (mp.isDragging) {
        const p = mp.byCode[mp.dragging];
        const pt = svgPoint(e);
        p.x = Math.round((mp.dragMirror ? 300 - pt.x : pt.x) * 10) / 10;
        p.y = Math.round(pt.y * 10) / 10;
        renderMap();
        return;
      }
      if (pan) {
        const rect = svg.getBoundingClientRect();
        const dx = ((e.clientX - pan.x) * pan.vb.w) / rect.width;
        const dy = ((e.clientY - pan.y) * pan.vb.h) / rect.height;
        if (Math.abs(dx) + Math.abs(dy) > 1) pan.moved = true;
        mp.vb = {
          ...pan.vb,
          x: Math.min(Math.max(pan.vb.x - dx, 0), BASE_VB.w - pan.vb.w),
          y: Math.min(Math.max(pan.vb.y - dy, 0), BASE_VB.h - pan.vb.h),
        };
        renderMap();
        return;
      }
      const g = e.target.closest(".mp-pt");
      if (g && e.pointerType === "mouse") {
        const p = mp.byCode[g.dataset.code];
        const stage = $("#mp-stage").getBoundingClientRect();
        tip.innerHTML = `<b>${esc(p.code)}</b> ${esc(p.pinyin)}<br><span>${esc(p.name_pt || bodyRegion(p))}</span>`;
        tip.style.left = `${e.clientX - stage.left + 12}px`;
        tip.style.top = `${e.clientY - stage.top + 12}px`;
        tip.hidden = false;
      } else tip.hidden = true;
    });

    const end = () => { mp.isDragging = false; pan = null; };
    svg.addEventListener("pointerup", end);
    svg.addEventListener("pointercancel", end);
    svg.addEventListener("pointerleave", () => (tip.hidden = true));

    svg.addEventListener("click", (e) => {
      const g = e.target.closest(".mp-pt");
      if (g && !mp.dragging) selectPoint(g.dataset.code, { focus: BASE_VB.w / mp.vb.w < 1.5 });
    });

    $$("[data-mp-view]").forEach((b) => b.addEventListener("click", () => {
      if (mp.mode === "3d") { $$("[data-mp-view]").forEach((x) => x.classList.toggle("is-active", x === b)); return mp.viewer?.view(b.dataset.mpView); }
      mp.view = b.dataset.mpView;
      mp.vb = { ...BASE_VB };
      renderMap();
    }));
    $$("[data-mp-region]").forEach((b) => b.addEventListener("click", () =>
      mp.mode === "3d" ? mp.viewer?.view(b.dataset.mpRegion) : zoomRegion(b.dataset.mpRegion)));
    $$("[data-mp-mode]").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mpMode)));
    const fsTarget = $("#view-points .mp-layout");
    $("[data-mp-fullscreen]").addEventListener("click", async () => {
      try {
        if (document.fullscreenElement) await document.exitFullscreen();
        else await fsTarget.requestFullscreen();
      } catch (_) {
        fsTarget.classList.toggle("is-pseudo-fs"); // navegadores sem tela cheia (ex.: iPhone)
        document.body.classList.toggle("mp-noscroll", fsTarget.classList.contains("is-pseudo-fs"));
        $("[data-mp-fullscreen]").textContent = fsTarget.classList.contains("is-pseudo-fs") ? "✕ Sair da tela cheia" : "⛶ Tela cheia";
      }
    });
    document.addEventListener("fullscreenchange", () => {
      $("[data-mp-fullscreen]").textContent = document.fullscreenElement ? "✕ Sair da tela cheia" : "⛶ Tela cheia";
    });
    $$("[data-mp-body]").forEach((b) => b.addEventListener("click", async () => {
      if (!mp.viewer) return;
      const available = await mp.viewer.setModel(b.dataset.mpBody);
      localStorage.setItem("ajna-map-body", b.dataset.mpBody);
      syncBodyButtons(b.dataset.mpBody, available);
      if (!available.includes(mp.layer)) {
        mp.layer = "skin";
        $$("[data-mp-layer]").forEach((x) => x.classList.toggle("is-active", x.dataset.mpLayer === "skin"));
        $("#mp-skin-opacity").value = 100;
      }
      toast(b.dataset.mpBody === "f" ? "Corpo feminino (pele e esqueleto parcial, sem músculos)." : "Corpo masculino.");
    }));
    $$("[data-mp-layer]").forEach((b) => b.addEventListener("click", () => {
      mp.layer = b.dataset.mpLayer;
      $$("[data-mp-layer]").forEach((x) => x.classList.toggle("is-active", x === b));
      const op = mp.layer === "skin" ? 100 : 15;
      $("#mp-skin-opacity").value = op;
      mp.viewer?.setLayer(mp.layer, op / 100);
    }));
    $("#mp-skin-opacity").addEventListener("input", (e) => mp.viewer?.setLayer(mp.layer, e.target.value / 100));
    $$("[data-mp-zoom]").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.mpZoom === "reset") { mp.vb = { ...BASE_VB }; renderMap(); }
      else zoomBy(b.dataset.mpZoom === "in" ? 1.5 : 1 / 1.5);
    }));

    $("#mp-meridians").addEventListener("click", (e) => {
      const b = e.target.closest("[data-mer]");
      if (!b) return;
      mp.filter = b.dataset.mer || null;
      mp.selected = null;
      // mostra a vista onde o meridiano tem mais pontos
      if (mp.filter) {
        const list = mp.points.filter((p) => p.meridian === mp.filter);
        const count = (v) => list.filter((p) => p.view === v).length;
        const best = ["front", "back", "ear"].sort((a, b) => count(b) - count(a))[0];
        if (best === "ear") { if (mp.mode !== "ear") setMode("ear"); }
        else { if (mp.mode === "ear") setMode("2d"); mp.view = best; }
      }
      mp.vb = { ...BASE_VB };
      renderMeridianChips();
      renderMap();
      renderPanel();
    });

    const search = $("#mp-search");
    const runSearch = () => {
      const q = search.value.trim().toUpperCase().split(/\s|·/)[0];
      const hit = mp.byCode[q] || mp.points.find((p) => p.pinyin.toUpperCase() === search.value.trim().toUpperCase())
        || mp.points.find((p) => p.pinyin.toUpperCase().startsWith(search.value.trim().toUpperCase()) && search.value.trim().length > 2);
      if (hit) { selectPoint(hit.code, { focus: true }); search.select(); }
      else if (search.value.trim()) toast("Ponto não encontrado.", true);
    };
    search.addEventListener("change", runSearch);
    search.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); runSearch(); } });

    $("#mp-labels").addEventListener("change", (e) => { mp.labels = e.target.checked; renderMap(); });

    $("#mp-patient").addEventListener("change", async (e) => {
      mp.usage = e.target.value ? await api(`/api/admin/acupoints/usage?patient_id=${e.target.value}`) : null;
      if (mp.usage && !Object.keys(mp.usage).length) toast("Nenhum ponto registrado nos protocolos deste paciente ainda.");
      mp.selected = null;
      renderMap();
      renderPanel();
    });

    // painel: selecionar, fechar, mover, restaurar, excluir, novo
    $("#mp-panel").addEventListener("click", async (e) => {
      const sel = e.target.closest("[data-select]");
      if (sel?.dataset.select) return selectPoint(sel.dataset.select);
      if (e.target.closest("[data-mp-close]")) { mp.selected = null; mp.viewer?.select(null, { fly: false }); renderMap(); return renderPanel(); }
      if (e.target.closest("[data-mp-new]")) return openNewPoint();
      const p = mp.byCode[mp.selected];
      if (!p) return;
      try {
        if (e.target.closest("[data-mp-move]")) startDrag(p);
        if (e.target.closest("[data-mp-reset]")) {
          Object.assign(p, await api(`/api/admin/acupoints/${encodeURIComponent(p.code)}`, { method: "PATCH", body: { reset_position: true } }));
          toast("Posição padrão restaurada (2D e 3D).");
          mp.view = p.view;
          renderMap();
          if (mp.mode === "3d") mp.viewer?.select(p.code, { fly: true });
        }
        if (e.target.closest("[data-mp-delete]")) {
          if (!(await confirmAction(`Excluir ${p.code}?`, "O ponto extra será apagado do mapa.", "Excluir"))) return;
          await api(`/api/admin/acupoints/${encodeURIComponent(p.code)}`, { method: "DELETE" });
          toast("Ponto excluído.");
          mp.selected = null;
          await loadPoints(true);
          renderMeridianChips();
          renderMap();
          renderPanel();
        }
      } catch (err) { toast(err.message, true); }
    });

    $("#mp-drag-bar").addEventListener("click", async (e) => {
      const b = e.target.closest("[data-mp-drag]");
      if (!b) return;
      const p = mp.byCode[mp.dragging];
      if (mp.dragMode3d) {
        mp.viewer.stopPick();
        mp.dragMode3d = false;
        if (b.dataset.mpDrag === "cancel") p.pos3d = mp.dragOrig.pos3d;
        else if (mp.pending3d) {
          try {
            Object.assign(p, await api(`/api/admin/acupoints/${encodeURIComponent(p.code)}`, { method: "PATCH", body: { pos3d: mp.pending3d, model: mp.viewer.model } }));
            toast("Posição 3D salva.");
          } catch (err) { toast(err.message, true); p.pos3d = mp.dragOrig.pos3d; }
        }
        mp.pending3d = null;
        mp.dragging = null;
        $("#mp-drag-bar").hidden = true;
        $("#mp-stage").classList.remove("is-dragging");
        mp.viewer.refresh();
        return;
      }
      if (b.dataset.mpDrag === "cancel") Object.assign(p, mp.dragOrig);
      else {
        try {
          Object.assign(p, await api(`/api/admin/acupoints/${encodeURIComponent(p.code)}`, {
            method: "PATCH", body: { x: p.x, y: p.y, view: mp.view },
          }));
          toast("Posição salva.");
        } catch (err) { toast(err.message, true); Object.assign(p, mp.dragOrig); }
      }
      mp.dragging = null;
      $("#mp-drag-bar").hidden = true;
      $("#mp-stage").classList.remove("is-dragging");
      renderMap();
    });
  }

  function startDrag(p) {
    if (mp.mode === "3d" && mp.viewer) {
      mp.dragging = p.code;
      mp.dragMode3d = true;
      mp.dragOrig = { pos3d: p.pos3d };
      mp.pending3d = null;
      $("#mp-drag-text").textContent = `🎯 Clique na pele onde fica ${p.code}`;
      $("#mp-drag-bar").hidden = false;
      $("#mp-stage").classList.add("is-dragging");
      mp.viewer.startPick((pos) => {
        mp.pending3d = pos;
        let saved = p.pos3d ? (typeof p.pos3d === "string" ? JSON.parse(p.pos3d) : p.pos3d) : {};
        if (Array.isArray(saved)) saved = { m: saved };
        p.pos3d = { ...saved, [mp.viewer.model]: pos };
        mp.viewer.refresh();
        mp.viewer.select(p.code, { fly: false });
        $("#mp-drag-text").textContent = `✔ Posição marcada — clique em “Salvar posição” (ou clique de novo para ajustar)`;
      });
      return;
    }
    $("#mp-drag-text").textContent = "✋ Arraste o ponto para a posição correta";
    mp.dragging = p.code;
    mp.dragOrig = { x: p.x, y: p.y, view: p.view };
    p.view = mp.view = p.view;
    $("#mp-drag-bar").hidden = false;
    $("#mp-stage").classList.add("is-dragging");
    $("#mp-stage").scrollIntoView({ behavior: "smooth", block: "nearest" });
    renderMap();
  }

  // Novo ponto extra
  const pointModal = $("#point-modal");
  const pointForm = $("#point-form");
  function openNewPoint() {
    pointForm.reset();
    $(".adm-form__error", pointForm).textContent = "";
    pointForm.elements.view.value = mp.mode === "ear" ? "ear" : mp.view;
    pointModal.showModal();
  }
  bindForm(pointModal, async (data) => {
    const center = { x: mp.vb.x + mp.vb.w / 2, y: mp.vb.y + mp.vb.h / 2 };
    const r = await api("/api/admin/acupoints", { method: "POST", body: { ...data, ...center } });
    await loadPoints(true);
    mp.view = data.view;
    mp.filter = null;
    renderMeridianChips();
    selectPoint(r.code);
    startDrag(mp.byCode[r.code]);
    toast("Ponto criado. Arraste-o até a posição certa.");
  });

  async function loadPointsView() {
    await loadPoints();
    if (!mp.bound) { bindMap(); mp.bound = true; }
    if (!state.patients.length) await fetchPatients();
    const sel = $("#mp-patient");
    const current = sel.value;
    sel.innerHTML = '<option value="">— nenhum paciente —</option>' +
      state.patients.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
    sel.value = current;
    renderMeridianChips();
    renderMap();
    renderPanel();
    const wantMode = localStorage.getItem("ajna-map-mode") === "ear" ? "ear" : "3d";
    if (wantMode !== mp.mode || !mp.viewer) await setMode(wantMode);
    if (localStorage.getItem("ajna-map-split") === "theory") setSplit("theory");
  }

  // Abrir um ponto no mapa a partir de outra tela (ex.: protocolo)
  document.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-open-point]");
    if (!b) return;
    if (protocolModal.open) protocolModal.close();
    show("points");
    await loadPoints();
    selectPoint(b.dataset.openPoint, { focus: true });
  });

  // ---------- bonequinho da sessão (frente, costas e orelha com os pontos marcados)
  const DOLL_VIEWS = [["front", "Frente"], ["back", "Costas"], ["ear", "Orelha"]];

  function dollSvg(view, codes, editable) {
    const base = baseFor(view);
    const sel = new Set(codes);
    const pts = mp.points.filter((p) => p.view === view && (editable || sel.has(p.code)));
    pts.sort((a, b) => (sel.has(a.code) ? 1 : 0) - (sel.has(b.code) ? 1 : 0)); // marcados por cima
    const small = view === "ear" ? 2.2 : 2.4;
    const big = view === "ear" ? 5 : 6.5;
    const dots = pts.map((p) => {
      const on = sel.has(p.code);
      const color = merColor(p.meridian);
      const one = (x) => `
        <g class="doll-pt ${on ? "is-on" : ""}" data-doll-code="${esc(p.code)}">
          <title>${esc(p.code)} · ${esc(p.pinyin)}</title>
          ${editable ? `<circle cx="${x}" cy="${p.y}" r="${view === "ear" ? 6 : 7}" class="doll-hit"/>` : ""}
          <circle cx="${x}" cy="${p.y}" r="${on ? big : small}" fill="${on ? color : "#bfa9c9"}" class="doll-dot"/>
          ${on ? `<text x="${x + big + 2}" y="${p.y + 3}" class="doll-label">${esc(p.code.replace("OR-", ""))}</text>` : ""}
        </g>`;
      return one(p.x) + (isBilateral(p) ? one(300 - p.x) : "");
    }).join("");
    return `<svg viewBox="0 0 ${base.w} ${base.h}" class="doll-svg doll-svg--${view}" role="img"
      aria-label="${view === "ear" ? "Orelha" : view === "front" ? "Corpo de frente" : "Corpo de costas"}">${bodySvg(view)}${dots}</svg>`;
  }

  function dollHtml(codes, editable) {
    const has = (v) => codes.some((c) => mp.byCode[c]?.view === v);
    const views = DOLL_VIEWS.filter(([v]) => editable || v !== "ear" || has("ear"));
    return views.map(([v, label]) => `
      <figure class="doll-panel">
        ${dollSvg(v, codes, editable)}
        <figcaption>${label}${codes.filter((c) => mp.byCode[c]?.view === v).length ? ` · ${codes.filter((c) => mp.byCode[c]?.view === v).length}` : ""}</figcaption>
      </figure>`).join("");
  }

  function refreshDoll(box) {
    const codes = $$(".pf-pchip", box).map((c) => c.dataset.code);
    const doll = $(".pf-doll__body", box);
    if (doll) doll.innerHTML = dollHtml(codes, true);
  }

  // clique no boneco do protocolo marca/desmarca o ponto
  document.addEventListener("click", (e) => {
    const dot = e.target.closest(".pf-doll [data-doll-code]");
    if (!dot) return;
    const box = dot.closest(".pf-points");
    const code = dot.dataset.dollCode;
    const chip = $(`.pf-pchip[data-code="${CSS.escape(code)}"]`, box);
    if (chip) chip.remove();
    else $(".pf-points__chips", box).insertAdjacentHTML("beforeend", pointChip(code, true));
    refreshDoll(box);
  });

  // ---------- campo "pontos" no formulário do protocolo
  function pointsInput(f, value) {
    const chips = (value || []).map((c) => pointChip(c, true)).join("");
    return `
      <div class="pf-points" data-points="${f.key}">
        <div class="pf-points__chips">${chips}</div>
        <div class="pf-points__add">
          <input type="text" list="acupoint-list" placeholder="Digite o código ou nome (ex.: VB20, Hegu, Shenmen) e tecle Enter" autocomplete="off">
          <button class="adm-btn adm-btn--sm" data-points-add type="button">Adicionar</button>
          <select class="adm-select adm-btn--sm" data-insert-combo aria-label="Inserir combinação"><option value="">＋ Inserir combinação…</option></select>
        </div>
        <div class="pf-doll">
          <p class="pf-doll__hint">👆 Ou clique nos pontos do boneco para marcar / desmarcar (inclui auriculoterapia).</p>
          <div class="pf-doll__body">${dollHtml(value || [], true)}</div>
        </div>
      </div>`;
  }

  function pointChip(code, removable) {
    const p = mp.byCode[code];
    const color = p ? merColor(p.meridian) : "#6c5b73";
    return `<span class="pf-pchip" data-code="${esc(code)}" style="--c:${color}" title="${esc(pointLabel(code))}">
      <button class="pf-pchip__open" data-open-point="${esc(code)}" type="button">${esc(code)}</button>
      ${removable ? `<button class="pf-pchip__x" data-points-remove type="button" aria-label="Remover ${esc(code)}">×</button>` : ""}
    </span>`;
  }

  function addPointFromInput(box) {
    const input = $("input", box);
    const raw = input.value.trim();
    const code = raw.toUpperCase().split(/\s|·/)[0];
    const hit = mp.byCode[code] || mp.points.find((p) => p.pinyin.toUpperCase() === raw.toUpperCase());
    if (!hit) { toast("Ponto não encontrado. Use o código (ex.: VB20) ou o nome.", true); return; }
    if (!$(`.pf-pchip[data-code="${CSS.escape(hit.code)}"]`, box)) {
      $(".pf-points__chips", box).insertAdjacentHTML("beforeend", pointChip(hit.code, true));
    }
    refreshDoll(box);
    input.value = "";
    input.focus();
  }

  document.addEventListener("click", (e) => {
    const add = e.target.closest("[data-points-add]");
    if (add) return addPointFromInput(add.closest(".pf-points"));
    const rm = e.target.closest("[data-points-remove]");
    if (rm) {
      const box = rm.closest(".pf-points");
      rm.closest(".pf-pchip").remove();
      if (box) refreshDoll(box);
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.matches(".pf-points__add input")) {
      e.preventDefault();
      addPointFromInput(e.target.closest(".pf-points"));
    }
  });


  // ---------------------------------------------------------------- 🎨 Visual / 📚 Teórico
  function setSplit(which, code) {
    $$("[data-mp-split]").forEach((b) => b.classList.toggle("is-active", b.dataset.mpSplit === which));
    $("#mp-theory").hidden = which !== "theory";
    $("#view-points .mp-layout").hidden = which === "theory";
    mp.viewer?.pause(which === "theory" || mp.mode !== "3d");
    if (which === "theory") loadPoints().then(() => window.AjnaTheory?.open(code));
    localStorage.setItem("ajna-map-split", which);
  }
  $$("[data-mp-split]").forEach((b) => b.addEventListener("click", () => setSplit(b.dataset.mpSplit)));

  // Funções do painel usadas pela parte teórica (theory.js)
  window.AjnaAdmin = {
    api, esc, toast, confirmAction,
    async patients() { await fetchPatients(); return state.patients; },
    dateBR: (s) => (s ? s.slice(0, 10).split("-").reverse().join("/") : ""),
    meridian: (code) => mp.merById[code],
    meridians: () => mp.meridians,
    usedCount: (code) => mp.byCode[code]?.used || 0,
    resolvePoint(raw) {
      const t = String(raw || "").trim();
      const code = t.toUpperCase().split(/\s|·/)[0];
      const hit = mp.byCode[code] || mp.points.find((p) => p.pinyin.toUpperCase() === t.toUpperCase())
        || mp.points.find((p) => (p.name_pt || "").toUpperCase() === t.toUpperCase());
      return hit?.code || null;
    },
    async showPointOnMap(code) {
      setSplit("visual");
      await loadPoints();
      selectPoint(code, { focus: true });
    },
    async reloadMapPoints() { await loadPoints(true); },
  };

  // Protocolo: inserir uma combinação salva (🧺) de uma vez
  document.addEventListener("focusin", async (e) => {
    const sel = e.target.closest?.("[data-insert-combo]");
    if (!sel || sel.dataset.loaded) return;
    sel.dataset.loaded = "1";
    const combos = (await window.AjnaTheory?.combos()) || [];
    sel.insertAdjacentHTML("beforeend", combos.map((c) => `<option value="${c.id}">${esc(c.name)} (${c.points.length})</option>`).join("")
      || '<option disabled>Nenhuma combinação salva (📚 Teórico › 🧺)</option>');
    sel._combos = combos;
  });
  document.addEventListener("change", (e) => {
    const sel = e.target.closest?.("[data-insert-combo]");
    if (!sel || !sel.value) return;
    const combo = (sel._combos || []).find((c) => String(c.id) === sel.value);
    const box = sel.closest(".pf-points");
    (combo?.points || []).forEach((code) => {
      if (!$(`.pf-pchip[data-code="${CSS.escape(code)}"]`, box)) $(".pf-points__chips", box).insertAdjacentHTML("beforeend", pointChip(code, true));
    });
    refreshDoll(box);
    toast(`Combinação “${combo?.name}” inserida.`);
    sel.value = "";
  });


  // ---------------------------------------------------------------- ficha do paciente › corpo 3D com os pontos usados nele
  // Corpo masculino só para paciente homem (sexo no prontuário); nos demais casos, o feminino.
  const p3d = { viewer: null, usage: {}, sel: null };

  async function openPatient3D() {
    const file = state.file;
    const gender = file.record?.data?.gender || file.patient.profile?.gender || "";
    const model = gender === "Masculino" ? "m" : "f";
    await loadPoints();
    p3d.usage = await api(`/api/admin/acupoints/usage?patient_id=${state.patientId}`);
    p3d.sel = null;
    const codes = Object.keys(p3d.usage).sort((a, b) => p3d.usage[b] - p3d.usage[a]);
    const body = codes.filter((c) => mp.byCode[c] && mp.byCode[c].view !== "ear");
    const ear = codes.filter((c) => mp.byCode[c]?.view === "ear");
    $("#p3d-title").textContent = file.patient.name;
    $("#p3d-sub").textContent = `${model === "m" ? "♂ Corpo masculino" : "♀ Corpo feminino"} · ${body.length} ponto(s) no corpo` +
      `${ear.length ? ` · ${ear.length} na orelha` : ""} · ${file.sessions.filter((s) => s.protocol).length} protocolo(s)` +
      `${gender ? "" : " · defina o sexo no prontuário para usar o corpo masculino em pacientes homens"}`;
    const row = (c) => {
      const p = mp.byCode[c];
      return `<button class="p3d__row" data-p3d="${esc(c)}" type="button"><i style="--c:${merColor(p?.meridian)}"></i>
        <b>${esc(c.replace("OR-", ""))}</b><span>${esc(p?.pinyin || "")}</span><em>${p3d.usage[c]}×</em></button>`;
    };
    $("#p3d-list").innerHTML = codes.length ? `
      ${body.length ? `<h3 class="mp-subtitle">No corpo</h3>${body.map(row).join("")}` : ""}
      ${ear.length ? `<h3 class="mp-subtitle">Na orelha</h3><div class="p3d__ear">${dollSvg("ear", ear, false)}</div>${ear.map(row).join("")}` : ""}`
      : '<p class="adm-empty">Nenhum ponto registrado nos protocolos deste paciente ainda.</p>';
    $("#p3d-modal").showModal();
    if (!p3d.viewer) {
      try {
        const mod = await import("./map3d.js");
        p3d.viewer = await mod.createViewer($("#p3d-canvas"), {
          model,
          getPoints: () => mp.points.filter((p) => p3d.usage[p.code] && p.view !== "ear"),
          styleOf: (code) => ({ color: merColor(mp.byCode[code]?.meridian), used: true, dim: false, selected: p3d.sel === code }),
          onSelect: (code) => selectP3d(code),
        });
      } catch (err) {
        console.error(err);
        $("#p3d-canvas").innerHTML = '<p class="adm-empty">Não foi possível abrir o 3D neste navegador.</p>';
        return;
      }
    } else {
      p3d.viewer.pause(false);
      await p3d.viewer.setModel(model);
    }
    p3d.viewer.refresh();
    p3d.viewer.view("front");
  }

  function selectP3d(code) {
    p3d.sel = code;
    $$(".p3d__row").forEach((b) => b.classList.toggle("is-sel", b.dataset.p3d === code));
    if (mp.byCode[code]?.view === "ear") return;
    p3d.viewer?.select(code, { fly: true });
  }

  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-patient-3d]")) return void openPatient3D().catch((err) => toast(err.message, true));
    const r = e.target.closest("[data-p3d]");
    if (r) selectP3d(r.dataset.p3d);
  });
  $("#p3d-close").addEventListener("click", () => $("#p3d-modal").close());
  $("#p3d-modal").addEventListener("close", () => p3d.viewer?.pause(true));

  // ---------------------------------------------------------------- botões gerais
  document.addEventListener("click", (event) => {
    const nav = event.target.closest(".adm-nav__item[data-view], [data-goto]");
    if (nav) return show(nav.dataset.view || nav.dataset.goto);
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "new-client") openClient();
    if (action === "new-appointment") openAppointment();
  });

  // Endereço com #agenda / #clients (e o botão Voltar do navegador) trocam a tela.
  window.addEventListener("hashchange", () => {
    const view = location.hash.slice(1);
    if (view && view !== state.hash) show(view);
  });

  $("#logout").addEventListener("click", () =>
    api("/api/auth/logout", { method: "POST" }).finally(() => location.assign("/login")));

  // ---------------------------------------------------------------- início
  (async () => {
    try {
      const me = await api("/api/auth/me");
      if (me.role !== "admin") return location.replace("/cliente");
      csrfToken = me.csrf_token || "";
      $("#admin-name").textContent = me.name;
      window.AjnaShell?.setUser(me);
      if (!window.AjnaShell) $("#admin-avatar").textContent = initials(me.name);
      $("#today-label").textContent = fmt(new Date(), { weekday: "long", day: "numeric", month: "long" });
      show(location.hash.slice(1) || "overview");
    } catch (_) {
      location.replace("/login");
    }
  })();
})();
