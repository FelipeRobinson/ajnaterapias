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

// ---------- Login (clientes e administrador). Painel: admin.js · Área do cliente: cliente.js ----------
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
