/* Área do cliente: início, agendar sessão, sessões e meus dados. */
(() => {
  "use strict";

  // Número do WhatsApp da clínica, só dígitos com DDI e DDD (ex.: "5511999998888").
  const WHATSAPP = "";

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
    if (!res.ok) throw new Error(data?.error || "Não foi possível concluir a ação.");
    return data;
  }

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const fromIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const fmt = (d, opts) => d.toLocaleDateString("pt-BR", opts);
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const when = (a) => new Date(`${a.date}T${a.start}:00`);

  const STATUS = { requested: "Aguardando confirmação", scheduled: "Confirmada", done: "Realizada", cancelled: "Cancelada" };

  let toastTimer;
  function toast(message, isError = false) {
    const el = $("#toast");
    el.textContent = message;
    el.classList.toggle("is-error", isError);
    el.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("is-visible"), 3500);
  }

  function confirmAction(title, text, okLabel) {
    const modal = $("#confirm-modal");
    $("#confirm-title").textContent = title;
    $("#confirm-text").textContent = text;
    $("#confirm-ok").textContent = okLabel;
    modal.showModal();
    return new Promise((resolve) => modal.addEventListener("close", () => resolve(modal.returnValue === "ok"), { once: true }));
  }

  // ---------------------------------------------------------------- estado e navegação
  const state = { view: "home", me: null, items: [], tab: "upcoming", info: null, day: null, slot: null };
  const TITLES = { home: null, book: "Agendar Sessão", appointments: "Minhas sessões", profile: "Meus dados" };

  function show(view) {
    if (!(view in TITLES)) view = "home";
    state.view = view;
    $$(".adm-view").forEach((s) => (s.hidden = s.id !== `view-${view}`));
    $$(".adm-nav__item[data-view]").forEach((b) => b.classList.toggle("is-active", b.dataset.view === view));
    $("#view-title").textContent = TITLES[view] || `Olá, ${state.me.name.split(" ")[0]}!`;
    if (location.hash !== `#${view}`) history.pushState(null, "", `#${view}`);
    window.scrollTo({ top: 0 });
    ({ home: loadHome, book: loadBook, appointments: loadAppointments, profile: loadProfile })[view]();
  }

  window.addEventListener("hashchange", () => {
    const view = location.hash.slice(1);
    if (view && view !== state.view) show(view);
  });

  document.addEventListener("click", (event) => {
    const nav = event.target.closest(".adm-nav__item[data-view], [data-goto]");
    if (nav) show(nav.dataset.view || nav.dataset.goto);
  });

  // ---------------------------------------------------------------- sessões (dados)
  async function fetchAppointments() {
    const data = await api("/api/patient/me/appointments");
    state.items = data.items;
    state.cancelHours = data.cancel_min_hours;
  }

  const isUpcoming = (a) => ["requested", "scheduled"].includes(a.status) && when(a) >= new Date();

  function canCancel(a) {
    if (!isUpcoming(a)) return false;
    if (a.status === "requested") return true;
    return when(a) - new Date() >= state.cancelHours * 3600 * 1000;
  }

  function row(a) {
    const d = fromIso(a.date);
    return `
      <div class="adm-appt adm-appt--${a.status}">
        <div class="cli-date" aria-hidden="true">
          <span>${fmt(d, { month: "short" }).replace(".", "")}</span><b>${d.getDate()}</b>
        </div>
        <div>
          <div class="adm-appt__who">${cap(fmt(d, { weekday: "long" }))}, ${esc(a.start)} às ${esc(a.end)}</div>
          <span class="adm-badge adm-badge--${a.status}">${STATUS[a.status] || a.status}</span>
        </div>
        ${canCancel(a) ? `<div class="adm-appt__actions"><button class="adm-btn adm-btn--sm" data-cancel="${a.id}" type="button">${a.status === "requested" ? "Desistir do pedido" : "Cancelar"}</button></div>` : ""}
      </div>`;
  }

  document.addEventListener("click", async (event) => {
    const btn = event.target.closest("[data-cancel]");
    if (!btn) return;
    const a = state.items.find((x) => x.id == btn.dataset.cancel);
    const label = a.status === "requested" ? "Desistir do pedido?" : "Cancelar sessão?";
    if (!(await confirmAction(label, `${cap(fmt(fromIso(a.date), { weekday: "long", day: "numeric", month: "long" }))}, às ${a.start}.`, "Sim, cancelar"))) return;
    try {
      await api(`/api/patient/appointments/${a.id}/cancel`, { method: "POST" });
      toast(a.status === "requested" ? "Pedido retirado." : "Sessão cancelada.");
      show(state.view);
    } catch (err) { toast(err.message, true); }
  });

  // ---------------------------------------------------------------- início
  async function loadHome() {
    await fetchAppointments();
    const upcoming = state.items.filter(isUpcoming);
    const next = upcoming[0];
    $("#next-card").innerHTML = next ? `
      <p class="cli-hero__label">${next.status === "requested" ? "Seu pedido de horário" : "Sua próxima sessão"}</p>
      <h2>${cap(fmt(fromIso(next.date), { weekday: "long", day: "numeric", month: "long" }))}</h2>
      <p class="cli-hero__time">${esc(next.start)} às ${esc(next.end)}</p>
      <span class="adm-badge adm-badge--${next.status}">${STATUS[next.status]}</span>` : `
      <p class="cli-hero__label">Nenhuma sessão marcada</p>
      <h2>Que tal reservar um momento para você? 🌿</h2>
      <button class="adm-btn cli-hero__btn" data-goto="book" type="button">＋ Agendar Sessão</button>`;
    $("#home-upcoming").innerHTML = upcoming.slice(0, 3).map(row).join("")
      || '<p class="adm-empty">Você ainda não tem sessões futuras.</p>';
    // Eventos abertos a todos (ex.: Reiki voluntário, no último sábado do mês)
    try {
      const { items } = await api("/api/patient/events");
      $("#home-events").innerHTML = items.slice(0, 3).map((e, i) => `
        <div class="ag-event ${i === 0 ? "ag-event--big" : ""}">${esc(e.icon)} <b>${esc(e.title)}</b> · ${cap(fmt(fromIso(e.date), { weekday: "long", day: "numeric", month: "long", year: "numeric" }))}${e.start_time ? ` · ${esc(e.start_time)}${e.end_time ? `–${esc(e.end_time)}` : ""}` : ""}
          ${i === 0 && e.description ? `<span>${esc(e.description)}</span>` : ""}</div>`).join("") || '<p class="adm-empty">Nenhum evento programado.</p>';
    } catch { $("#home-events").innerHTML = ""; }
  }

  // ---------------------------------------------------------------- agendar
  async function loadBook() {
    if (!state.info) state.info = await api("/api/patient/schedule-info");
    const open = new Set(state.info.open_weekdays.map((w) => (w + 1) % 7)); // backend: seg=0 · JS: dom=0
    const days = [];
    const now = new Date();
    const hm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    const skipToday = !state.info.today_closes || hm >= state.info.today_closes;
    for (let i = skipToday ? 1 : 0; days.length < 14 && i <= state.info.days_ahead; i++) {
      const d = addDays(new Date(), i);
      if (open.has(d.getDay())) days.push(d);
    }
    if (!state.day || !days.some((d) => iso(d) === state.day)) state.day = days.length ? iso(days[0]) : null;
    $("#day-strip").innerHTML = days.map((d) => `
      <button class="cli-day ${iso(d) === state.day ? "is-active" : ""}" data-day="${iso(d)}" type="button" role="option" aria-selected="${iso(d) === state.day}">
        <span>${fmt(d, { weekday: "short" }).replace(".", "")}</span><b>${d.getDate()}</b><span>${fmt(d, { month: "short" }).replace(".", "")}</span>
      </button>`).join("");
    loadSlots();
  }

  async function loadSlots() {
    state.slot = null;
    $("#book-summary").hidden = true;
    if (!state.day) { $("#slot-grid").innerHTML = '<p class="adm-empty">Sem dias disponíveis.</p>'; return; }
    $("#slots-title").textContent = `2. Escolha o horário · ${cap(fmt(fromIso(state.day), { weekday: "long", day: "numeric", month: "long" }))}`;
    $("#slot-grid").innerHTML = '<p class="adm-muted">Carregando horários…</p>';
    const { slots } = await api(`/api/patient/slots?date=${state.day}`);
    $("#slot-grid").innerHTML = slots.length
      ? slots.map((s) => `<button class="cli-slot" data-slot="${s.start}" data-end="${s.end}" type="button">${s.start}</button>`).join("")
      : '<p class="adm-empty">Nenhum horário livre neste dia. Tente outro dia. 🌙</p>';
  }

  $("#day-strip").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-day]");
    if (!btn) return;
    state.day = btn.dataset.day;
    $$(".cli-day").forEach((b) => { b.classList.toggle("is-active", b === btn); b.setAttribute("aria-selected", b === btn); });
    loadSlots();
  });

  $("#slot-grid").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-slot]");
    if (!btn) return;
    state.slot = btn.dataset.slot;
    $$(".cli-slot").forEach((b) => b.classList.toggle("is-active", b === btn));
    $("#book-text").textContent = `${cap(fmt(fromIso(state.day), { weekday: "long", day: "numeric", month: "long" }))}, das ${btn.dataset.slot} às ${btn.dataset.end}`;
    $("#book-summary").hidden = false;
    $("#book-summary").scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  $("#book-send").addEventListener("click", async (event) => {
    event.currentTarget.disabled = true;
    try {
      await api("/api/patient/appointments", { method: "POST", body: { date: state.day, start: state.slot } });
      toast("Pedido enviado! A clínica vai confirmar o horário. 💜");
      show("appointments");
    } catch (err) {
      toast(err.message, true);
      loadSlots();
    } finally {
      event.currentTarget.disabled = false;
    }
  });

  // ---------------------------------------------------------------- sessões (tela)
  async function loadAppointments() {
    await fetchAppointments();
    renderAppointments();
  }

  function renderAppointments() {
    const upcoming = state.items.filter(isUpcoming);
    const past = state.items.filter((a) => !isUpcoming(a)).reverse();
    const list = state.tab === "upcoming" ? upcoming : past;
    $$(".cli-tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === state.tab));
    $("#appointment-list").innerHTML = list.map(row).join("") || `<p class="adm-empty">${state.tab === "upcoming"
      ? 'Nenhuma sessão marcada. <button class="adm-btn adm-btn--link" data-goto="book" type="button">Agendar Sessão →</button>'
      : "Seu histórico aparecerá aqui."}</p>`;
    $("#cancel-rule").textContent = state.tab === "upcoming"
      ? `Sessões confirmadas podem ser canceladas aqui até ${state.cancelHours}h antes. Depois disso, fale com a clínica.` : "";
  }

  $$(".cli-tab").forEach((t) => t.addEventListener("click", () => { state.tab = t.dataset.tab; renderAppointments(); }));

  // ---------------------------------------------------------------- meus dados
  async function loadProfile() {
    const p = await api("/api/patient/me");
    const f = $("#profile-form");
    f.elements.name.value = p.name;
    f.elements.email.value = p.email;
    f.elements.phone.value = p.phone || "";
    state.profileFields = p.profile_fields;
    const v = (k) => esc(p.profile?.[k] || "");
    $("#personal-fields").innerHTML = p.profile_fields.map((sec) => `
      <fieldset class="cli-fieldset"><legend>${sec.icon} ${esc(sec.title)}</legend>
        <div class="cli-fields">${sec.fields.map((fl) => `<label>${esc(fl.label)}${
          fl.type === "select" ? `<select name="${fl.key}"><option value="">—</option>${fl.options.map((o) =>
            `<option ${o === p.profile?.[fl.key] ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`
          : `<input name="${fl.key}" type="${fl.type === "date" ? "date" : "text"}" value="${v(fl.key)}"
              ${fl.placeholder ? `placeholder="${esc(fl.placeholder)}"` : ""} ${["cpf", "cep"].includes(fl.type) ? 'inputmode="numeric"' : ""}
              ${fl.type === "cpf" ? 'data-mask="cpf"' : fl.type === "cep" ? 'data-mask="cep"' : ""}>`}</label>`).join("")}</div>
      </fieldset>`).join("");
  }

  // máscaras simples para CPF e CEP
  document.addEventListener("input", (e) => {
    const m = e.target.dataset?.mask;
    if (!m) return;
    const d = e.target.value.replace(/\D/g, "").slice(0, m === "cpf" ? 11 : 8);
    e.target.value = m === "cpf"
      ? d.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2")
      : d.replace(/(\d{5})(\d)/, "$1-$2");
  });

  $("#personal-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const f = event.currentTarget;
    const err = $(".adm-form__error", f);
    err.textContent = "";
    const profile = {};
    state.profileFields.flatMap((s) => s.fields).forEach((fl) => { profile[fl.key] = f.elements[fl.key].value; });
    try {
      await api("/api/patient/me", { method: "PATCH", body: { profile } });
      toast("Dados pessoais salvos.");
    } catch (e2) { err.textContent = e2.message; }
  });

  $("#profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const f = event.currentTarget;
    $(".adm-form__error", f).textContent = "";
    try {
      await api("/api/patient/me", { method: "PATCH", body: { phone: f.elements.phone.value } });
      toast("Telefone atualizado.");
    } catch (err) { $(".adm-form__error", f).textContent = err.message; }
  });

  $("#password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const f = event.currentTarget;
    const error = $(".adm-form__error", f);
    error.textContent = "";
    if (f.elements.new.value !== f.elements.repeat.value) { error.textContent = "As novas senhas não conferem."; return; }
    try {
      await api("/api/patient/me/password", { method: "POST", body: { current: f.elements.current.value, new: f.elements.new.value } });
      f.reset();
      toast("Senha alterada com sucesso.");
    } catch (err) { error.textContent = err.message; }
  });

  $("#logout").addEventListener("click", () =>
    api("/api/auth/logout", { method: "POST" }).finally(() => location.assign("/login")));

  // ---------------------------------------------------------------- início
  (async () => {
    try {
      const me = await api("/api/auth/me");
      if (me.role !== "patient") return location.replace("/crm/painel");
      csrfToken = me.csrf_token || "";
      state.me = me;
      if (window.AjnaShell) window.AjnaShell.setUser(me);
      else $("#client-avatar").textContent = me.name.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
      $("#today-label").textContent = fmt(new Date(), { weekday: "long", day: "numeric", month: "long" });
      if (WHATSAPP) $("#whatsapp-link").href = `https://wa.me/${WHATSAPP}`;
      show(location.hash.slice(1) || "home");
    } catch (_) {
      location.replace("/login");
    }
  })();
})();
