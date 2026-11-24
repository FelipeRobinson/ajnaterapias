/* Agenda › ⚙️ Horários e eventos: horários extras (fora do 9h–11h / 13h–19h, só de terça a quinta)
   e eventos da clínica (criar, editar, excluir). */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const A = () => window.AjnaAdmin;
  const modal = $("#ag-settings-modal");
  const evModal = $("#event-modal");
  const evForm = $("#event-form");
  if (!modal || !evModal) return;

  const st = { open: [1, 2, 3], recurrences: {}, events: [], extras: [], editing: null };
  const dateBR = (s) => (s ? s.split("-").reverse().join("/") : "");
  const WD = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

  // ---------------------------------------------------------------- horários extras
  function renderExtras() {
    const esc = A().esc;
    $("#ags-extras").innerHTML = st.extras.map((x) => `
      <div class="adm-appt ag-set__ev">
        <div class="ag-set__ev-main">
          <b>🕐 ${esc(dateBR(x.date))} (${WD[new Date(`${x.date}T12:00`).getDay()]})</b>
          <span class="adm-muted">das ${esc(x.start)} às ${esc(x.end)}</span>
        </div>
        <div class="ag-set__ev-act">
          <button class="adm-btn adm-btn--sm adm-btn--danger" data-extra-del="${x.id}" type="button">🗑️ Excluir</button>
        </div>
      </div>`).join("") || '<p class="adm-empty">Nenhum horário extra aberto.</p>';
  }

  $("#ags-extra-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.currentTarget.elements;
    $("#ags-extra-error").textContent = "";
    const wd = (new Date(`${f.date.value}T12:00`).getDay() + 6) % 7; // 0 = segunda
    if (f.date.value && !st.open.includes(wd)) {
      $("#ags-extra-error").textContent = "Horários extras só de terça a quinta. Segunda, sexta, sábado e domingo não têm agendamento.";
      return;
    }
    try {
      await A().api("/api/admin/extra-hours", { method: "POST", body: { date: f.date.value, start: f.start.value, end: f.end.value } });
      A().toast("Horário extra aberto para os clientes.");
      await loadAll();
      A().reloadAgenda();
    } catch (err) { $("#ags-extra-error").textContent = err.message; }
  });

  // ---------------------------------------------------------------- eventos
  const recLabel = (ev) => (ev.recurrence === "once" ? dateBR(ev.date)
    : `${st.recurrences[ev.recurrence] || ""} · desde ${dateBR(ev.date)}${ev.until ? ` até ${dateBR(ev.until)}` : ""}`);

  function renderEvents() {
    const esc = A().esc;
    $("#ags-events").innerHTML = st.events.map((ev) => `
      <div class="adm-appt ag-set__ev">
        <div class="ag-set__ev-main">
          <b>${esc(ev.icon || "📅")} ${esc(ev.title)}</b>
          <span class="adm-muted">${esc(recLabel(ev))}${ev.start_time ? ` · ${esc(ev.start_time)}${ev.end_time ? `–${esc(ev.end_time)}` : ""}` : ""}</span>
          ${ev.description ? `<span class="adm-muted ag-set__desc">${esc(ev.description)}</span>` : ""}
        </div>
        <div class="ag-set__ev-act">
          <button class="adm-btn adm-btn--sm" data-ev-edit="${ev.id}" type="button">✏️ Editar</button>
          <button class="adm-btn adm-btn--sm adm-btn--danger" data-ev-del="${ev.id}" type="button">🗑️ Excluir</button>
        </div>
      </div>`).join("") || '<p class="adm-empty">Nenhum evento cadastrado.</p>';
  }

  async function loadAll() {
    const [cfg, evs, ex] = await Promise.all([A().api("/api/admin/calendar-settings"), A().api("/api/admin/events"),
      A().api("/api/admin/extra-hours")]);
    st.open = cfg.open_weekdays; st.recurrences = cfg.recurrences; st.events = evs.items; st.extras = ex.items;
    renderExtras();
    renderEvents();
  }

  function toggleUntil() {
    $("[data-ev-until]", evForm).hidden = evForm.elements.recurrence.value === "once";
  }

  function openEvent(ev) {
    st.editing = ev?.id || null;
    $("#event-modal-title").textContent = ev ? "Editar evento" : "Novo evento";
    evForm.elements.recurrence.innerHTML = Object.entries(st.recurrences)
      .map(([k, v]) => `<option value="${k}">${A().esc(v)}</option>`).join("");
    const f = evForm.elements;
    f.icon.value = ev?.icon || "🌟";
    f.title.value = ev?.title || "";
    f.date.value = ev?.date || new Date().toLocaleDateString("sv-SE");
    f.recurrence.value = ev?.recurrence || "once";
    f.until.value = ev?.until || "";
    f.start_time.value = ev?.start_time || "";
    f.end_time.value = ev?.end_time || "";
    f.description.value = ev?.description || "";
    $(".adm-form__error", evForm).textContent = "";
    toggleUntil();
    evModal.showModal();
  }

  evForm.elements.recurrence.addEventListener("change", toggleUntil);

  evForm.addEventListener("submit", async (e) => {
    if (e.submitter?.value !== "save") return;
    e.preventDefault();
    const f = evForm.elements;
    const body = Object.fromEntries(["icon", "title", "date", "recurrence", "until", "start_time", "end_time", "description"]
      .map((k) => [k, f[k].value.trim()]));
    try {
      await A().api(st.editing ? `/api/admin/events/${st.editing}` : "/api/admin/events",
        { method: st.editing ? "PUT" : "POST", body });
      evModal.close();
      A().toast(st.editing ? "Evento atualizado." : "Evento criado.");
      await loadAll();
      A().reloadAgenda();
    } catch (err) { $(".adm-form__error", evForm).textContent = err.message; }
  });

  modal.addEventListener("click", async (e) => {
    if (e.target.closest("[data-ags-close]")) return modal.close();
    if (e.target.closest("#ags-new-event")) return openEvent(null);
    const xd = e.target.closest("[data-extra-del]");
    if (xd) {
      if (!(await A().confirmAction("Excluir horário extra?", "Os clientes não vão mais conseguir agendar nesse horário.", "Excluir"))) return;
      try {
        await A().api(`/api/admin/extra-hours/${xd.dataset.extraDel}`, { method: "DELETE" });
        A().toast("Horário extra excluído.");
        await loadAll();
        A().reloadAgenda();
      } catch (err) { A().toast(err.message, true); }
      return;
    }
    const ed = e.target.closest("[data-ev-edit]");
    if (ed) return openEvent(st.events.find((x) => x.id === Number(ed.dataset.evEdit)));
    const del = e.target.closest("[data-ev-del]");
    if (del) {
      const ev = st.events.find((x) => x.id === Number(del.dataset.evDel));
      if (!(await A().confirmAction("Excluir evento?", `“${ev.title}” some da agenda e da área dos clientes.`, "Excluir"))) return;
      try {
        await A().api(`/api/admin/events/${ev.id}`, { method: "DELETE" });
        A().toast("Evento excluído.");
        await loadAll();
        A().reloadAgenda();
      } catch (err) { A().toast(err.message, true); }
    }
  });

  $("#ag-settings-btn").addEventListener("click", async () => {
    try {
      await loadAll();
      modal.showModal();
    } catch (err) { A().toast(err.message, true); }
  });
})();
