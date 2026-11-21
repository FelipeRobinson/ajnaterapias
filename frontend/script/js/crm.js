let csrfToken = "";

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(url, {
    credentials: "same-origin",
    ...options,
    headers,
  });
  const data =
    response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const err = new Error(data?.error || "Não foi possível concluir a ação.");
    err.status = response.status;
    throw err;
  }
  return data;
}

const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const homeFor = (role) => (role === "admin" ? "/crm/painel" : "/cliente");

// ---------- Login (clientes e administrador) ----------
const loginForm = document.querySelector("#login-form");
if (loginForm) {
  const error = document.querySelector("#form-error");

  document.querySelector("[data-toggle-password]")?.addEventListener("click", (event) => {
    const input = document.querySelector("#password");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    event.currentTarget.textContent = show ? "Ocultar" : "Mostrar";
  });
  // Já logado? vai direto para a área certa.
  request("/api/auth/me")
    .then((me) => location.replace(homeFor(me.role)))
    .catch(() => {});

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    const button = loginForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const result = await request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(new FormData(loginForm))),
      });
      location.assign(homeFor(result.role));
    } catch (err) {
      error.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}

// ---------- Páginas protegidas ----------
const page = document.querySelector("[data-page]")?.dataset.page;

async function requireSession(expectedRole) {
  try {
    const me = await request("/api/auth/me");
    if (me.role !== expectedRole) {
      location.replace(homeFor(me.role));
      return null;
    }
    csrfToken = me.csrf_token || "";
    return me;
  } catch (_) {
    location.replace("/login");
    return null;
  }
}

async function loadAdmin() {
  const [dashboard, patients] = await Promise.all([
    request("/api/admin/dashboard"),
    request("/api/admin/patients"),
  ]);
  document.querySelector("#patient-count").textContent = dashboard.patients;
  document.querySelector("#appointment-count").textContent =
    dashboard.appointments_today;
  document.querySelector("#patients").innerHTML =
    patients.items
      .map(
        (p) => `
    <div class="patient-row">
      <div><strong>${escapeHtml(p.name)}</strong><br><span class="helper">${escapeHtml(p.email)}${p.phone ? " · " + escapeHtml(p.phone) : ""}</span></div>
      <div class="row-actions">
        <button class="text-button" data-reset="${p.id}" type="button">Nova senha</button>
        <button class="text-button" data-toggle="${p.id}" data-active="${p.active}" type="button">${p.active ? "Desativar" : "Reativar"}</button>
      </div>
    </div>`,
      )
      .join("") || '<p class="helper">Nenhum cliente cadastrado.</p>';
}

if (page === "admin") {
  requireSession("admin").then((me) => {
    if (!me) return;
    loadAdmin();

    const form = document.querySelector("#new-patient");
    const msg = document.querySelector("#new-patient-msg");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      msg.textContent = "";
      try {
        await request("/api/admin/patients", {
          method: "POST",
          body: JSON.stringify(Object.fromEntries(new FormData(form))),
        });
        msg.textContent =
          "Acesso criado. Envie o e-mail e a senha inicial ao cliente.";
        form.reset();
        loadAdmin();
      } catch (err) {
        msg.textContent = err.message;
      }
    });

    document
      .querySelector("#patients")
      .addEventListener("click", async (event) => {
        const btn = event.target.closest("button");
        if (!btn) return;
        try {
          if (btn.dataset.toggle) {
            await request(`/api/admin/patients/${btn.dataset.toggle}`, {
              method: "PATCH",
              body: JSON.stringify({ active: btn.dataset.active !== "1" }),
            });
          } else if (btn.dataset.reset) {
            const password = prompt(
              "Nova senha para o cliente (mín. 8 caracteres):",
            );
            if (!password) return;
            await request(`/api/admin/patients/${btn.dataset.reset}`, {
              method: "PATCH",
              body: JSON.stringify({ password }),
            });
            alert("Senha atualizada.");
          }
          loadAdmin();
        } catch (err) {
          alert(err.message);
        }
      });
  });
}

if (page === "patient") {
  requireSession("patient").then(async (me) => {
    if (!me) return;
    document.querySelector("#client-name").textContent = me.name;
    const { items } = await request("/api/patient/me/appointments");
    document.querySelector("#appointments").innerHTML =
      items
        .map(
          (a) => `
      <div class="patient-row"><strong>${escapeHtml(a.date.split("-").reverse().join("/"))}</strong>
      <span>${escapeHtml(a.start)} – ${escapeHtml(a.end)} · ${a.status === "cancelled" ? "Cancelada" : "Agendada"}</span></div>`,
        )
        .join("") ||
      '<p class="helper">Você ainda não tem consultas registradas.</p>';
  });
}

document
  .querySelector("#logout")
  ?.addEventListener("click", () =>
    request("/api/auth/logout", { method: "POST" }).finally(() =>
      location.assign("/login"),
    ),
  );
