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
    if (!res.ok) throw new Error(data?.error || "Não foi possível concluir a ação.");
    return data;
  }

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
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
  const state = { patients: [], weekStart: startOfWeek(new Date()), view: "overview" };

  // ---------------------------------------------------------------- navegação
  const TITLES = { overview: "Visão geral", agenda: "Agenda", clients: "Clientes", account: "Minha conta" };

  function show(view) {
    if (!TITLES[view]) view = "overview";
    state.view = view;
    $$(".adm-view").forEach((s) => (s.hidden = s.id !== `view-${view}`));
    $$(".adm-nav__item[data-view]").forEach((b) => b.classList.toggle("is-active", b.dataset.view === view));
    $("#view-title").textContent = TITLES[view];
    if (location.hash !== `#${view}`) history.pushState(null, "", `#${view}`);
    window.scrollTo({ top: 0 });
    refresh();
  }

  function refresh() {
    if (state.view === "overview") return loadOverview();
    if (state.view === "agenda") return loadAgenda();
    if (state.view === "clients") return loadClients();
    if (state.view === "account") return loadAccount();
  }

  // ---------------------------------------------------------------- minha conta
  const accountForm = $("#account-form");

  async function loadAccount() {
    const me = await api("/api/account");
    accountForm.reset();
    $(".adm-form__error", accountForm).textContent = "";
    accountForm.elements.name.value = me.name;
    accountForm.elements.email.value = me.email;
    accountForm.elements.phone.value = me.phone || "";
    const [user, domain] = me.email.split("@");
    $("#account-email-mask").textContent = `${user.slice(0, 2)}***@${domain}`;
  }

  accountForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = $(".adm-form__error", accountForm);
    error.textContent = "";
    const data = Object.fromEntries(new FormData(accountForm));
    if (data.new_password !== data.repeat) { error.textContent = "As novas senhas não conferem."; return; }
    delete data.repeat;
    const button = event.submitter || $('button[type="submit"]', accountForm);
    button.disabled = true;
    try {
      const r = await api("/api/account/change-request", { method: "POST", body: data });
      const status = $("#account-status");
      status.hidden = false;
      status.innerHTML = `📧 Enviamos o link para <b>${esc(r.sent_to)}</b>. Abra o e-mail e clique em <b>Confirmar alteração</b> em até ${r.minutes} minutos.`;
      accountForm.elements.current_password.value = "";
      accountForm.elements.new_password.value = "";
      accountForm.elements.repeat.value = "";
      toast("Confirmação enviada por e-mail.");
    } catch (err) {
      error.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });

  $(".adm-top__user").addEventListener("click", (e) => { if (!e.target.closest("#logout")) show("account"); });

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
        ${a.status === "scheduled" ? `<button class="adm-btn adm-btn--sm" data-appt-done="${a.id}" type="button">✓ Realizada</button>` : ""}
        ${a.status !== "cancelled" ? `<button class="adm-btn adm-btn--sm" data-appt-edit="${a.id}" type="button">Remarcar</button>` : ""}
        ${a.status !== "cancelled" ? `<button class="adm-btn adm-btn--sm" data-appt-cancel="${a.id}" type="button">Cancelar</button>` : ""}
        ${a.status === "cancelled" ? `<button class="adm-btn adm-btn--sm" data-appt-delete="${a.id}" type="button">Excluir</button>` : ""}
      </div>`;
    return `
      <div class="adm-appt adm-appt--${a.status}">
        <span class="adm-appt__time">${when}${esc(a.start)}–${esc(a.end)}</span>
        <div>
          <div class="adm-appt__who">${esc(a.patient_name)}</div>
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
  async function loadAgenda() {
    const start = state.weekStart;
    const end = addDays(start, 6);
    const sameMonth = start.getMonth() === end.getMonth();
    $("#week-label").textContent = sameMonth
      ? `${start.getDate()} – ${fmt(end, { day: "numeric", month: "long" })}`
      : `${fmt(start, { day: "numeric", month: "short" })} – ${fmt(end, { day: "numeric", month: "short" })}`;

    const { items } = await api(`/api/admin/appointments?from=${iso(start)}&to=${iso(end)}`);
    const today = iso(new Date());
    $("#week-days").innerHTML = Array.from({ length: 7 }, (_, i) => {
      const day = addDays(start, i);
      const key = iso(day);
      const list = items.filter((a) => a.date === key);
      return `
        <section class="adm-card adm-day ${key === today ? "adm-day--today" : ""}">
          <div class="adm-day__head">
            <h3>${cap(fmt(day, { weekday: "long", day: "numeric", month: "short" }))}</h3>
            ${key === today ? '<span class="adm-badge adm-badge--scheduled">Hoje</span>' : ""}
            <button class="adm-btn adm-btn--link" data-new-on="${key}" type="button" style="margin-left:auto">＋ Agendar</button>
          </div>
          <div class="adm-list">${list.length ? list.map((a) => appointmentRow(a)).join("") : '<p class="adm-muted">Livre</p>'}</div>
        </section>`;
    }).join("");
    state.weekItems = items;
  }

  $("#week-prev").addEventListener("click", () => { state.weekStart = addDays(state.weekStart, -7); loadAgenda(); });
  $("#week-next").addEventListener("click", () => { state.weekStart = addDays(state.weekStart, 7); loadAgenda(); });
  $("#week-today").addEventListener("click", () => { state.weekStart = startOfWeek(new Date()); loadAgenda(); });

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
    apptModal.showModal();
  }

  // Ao mudar o início, sugere 1h de duração.
  apptForm.elements.start.addEventListener("change", (e) => {
    const [h, m] = e.target.value.split(":").map(Number);
    if (Number.isFinite(h) && h < 23) apptForm.elements.end.value = `${String(h + 1).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  });

  bindForm(apptModal, async (data) => {
    const id = apptForm.dataset.id;
    if (id) {
      delete data.patient_user_id;
      await api(`/api/admin/appointments/${id}`, { method: "PATCH", body: data });
      toast("Consulta remarcada.");
    } else {
      await api("/api/admin/appointments", { method: "POST", body: data });
      toast("Consulta agendada.");
    }
    state.weekStart = startOfWeek(fromIso(data.date || iso(new Date())));
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
        <span class="adm-client__avatar" aria-hidden="true">${esc(initials(p.name))}</span>
        <div>
          <div class="adm-client__name">${esc(p.name)}</div>
          <div class="adm-muted" style="font-size:.82rem">${p.appointments} consulta(s)</div>
        </div>
        <div class="adm-client__contact">${esc(p.email)}${p.phone ? `<br>${esc(p.phone)}` : ""}</div>
        <span class="adm-client__badge adm-badge adm-badge--${p.active ? "active" : "inactive"}">${p.active ? "Ativo" : "Desativado"}</span>
        <div class="adm-client__actions">
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
    if (view && view !== state.view) show(view);
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
      $("#admin-avatar").textContent = initials(me.name);
      $("#today-label").textContent = fmt(new Date(), { weekday: "long", day: "numeric", month: "long" });
      show(location.hash.slice(1) || "overview");
    } catch (_) {
      location.replace("/login");
    }
  })();
})();
