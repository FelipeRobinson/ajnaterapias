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

// ---------- Esqueci minha senha ----------
const forgotForm = document.querySelector("#forgot-form");
if (forgotForm) {
  const showCard = (name) => {
    document.querySelector("#login-card").hidden = name !== "login";
    document.querySelector("#forgot-card").hidden = name !== "forgot";
    if (name === "forgot") {
      // aproveita o e-mail já digitado no login
      const typed = loginForm?.elements.email.value;
      if (typed) forgotForm.elements.email.value = typed;
      forgotForm.elements.email.focus();
    }
    history.replaceState(null, "", name === "forgot" ? "#esqueci" : location.pathname);
  };
  document.querySelectorAll("[data-show]").forEach((b) => b.addEventListener("click", () => showCard(b.dataset.show)));
  if (location.hash === "#esqueci") showCard("forgot");

  forgotForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const error = document.querySelector("#forgot-error");
    const ok = document.querySelector("#forgot-ok");
    error.textContent = "";
    const button = forgotForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const r = await request("/api/auth/forgot", {
        method: "POST",
        body: JSON.stringify({ email: forgotForm.elements.email.value }),
      });
      ok.textContent = `📧 ${r.message} Confira também a caixa de spam. O link vale por 30 minutos.`;
      ok.hidden = false;
      forgotForm.hidden = true;
    } catch (err) {
      error.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}

// ---------- Criar nova senha (página redefinir.html) ----------
const resetForm = document.querySelector("#reset-form");
if (resetForm) {
  const token = new URLSearchParams(location.search).get("token") || "";
  const error = document.querySelector("#reset-error");
  const invalid = () => {
    resetForm.hidden = true;
    document.querySelector("#reset-invalid").hidden = false;
  };
  request(`/api/auth/reset-info?token=${encodeURIComponent(token)}`)
    .then((info) => {
      if (!info.valid) return invalid();
      resetForm.elements.password.minLength = info.min_length;
      document.querySelector("#reset-min").textContent = info.min_length;
    })
    .catch(invalid);

  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    const { password, repeat } = resetForm.elements;
    if (password.value !== repeat.value) { error.textContent = "As senhas não conferem."; return; }
    const button = resetForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await request("/api/auth/reset", { method: "POST", body: JSON.stringify({ token, password: password.value }) });
      resetForm.hidden = true;
      document.querySelector("#reset-done").hidden = false;
      history.replaceState(null, "", location.pathname); // tira o token da barra de endereço
    } catch (err) {
      error.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}
