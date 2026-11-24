/* Partes comuns do painel e da área do cliente:
   - menu hambúrguer (faixa com logo + ☰ no computador; botão ☰ no canto no celular)
   - foto de perfil opcional (clique no avatar do topo) */
(() => {
  const $ = (sel, root = document) => root.querySelector(sel);
  const nav = $(".adm-nav");
  if (!nav) return;

  // ---------------------------------------------------------------- menu
  const brand = $(".adm-nav__brand", nav);
  const rail = document.createElement("div");
  rail.className = "adm-rail";
  rail.innerHTML = `
    <a class="adm-rail__logo" href="${brand?.getAttribute("href") || "../index.html"}" title="Ver o site">
      <img src="${brand ? $("img", brand).getAttribute("src") : ""}" alt="Ajna Terapias">
    </a>
    <button class="adm-rail__menu" type="button" aria-label="Abrir menu" aria-expanded="false" aria-controls="adm-nav">
      <span></span><span></span><span></span><i class="adm-rail__dot" hidden></i>
    </button>`;
  nav.id = "adm-nav";
  nav.before(rail);
  const backdrop = document.createElement("div");
  backdrop.className = "adm-nav-backdrop";
  nav.after(backdrop);
  const close = document.createElement("button");
  close.className = "adm-nav__close";
  close.type = "button";
  close.setAttribute("aria-label", "Fechar menu");
    nav.prepend(close);

  const btn = $(".adm-rail__menu", rail);
  const setOpen = (open) => {
    document.body.classList.toggle("nav-open", open);
    btn.setAttribute("aria-expanded", String(open));
    if (open) $(".adm-nav__item.is-active", nav)?.focus({ preventScroll: true });
  };
  btn.addEventListener("click", () => setOpen(!document.body.classList.contains("nav-open")));
  backdrop.addEventListener("click", () => setOpen(false));
  close.addEventListener("click", () => setOpen(false));
  nav.addEventListener("click", (e) => { if (e.target.closest(".adm-nav__item[data-view]")) setOpen(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });

  // botão de tema no fim do menu (claro por padrão; a escolha fica salva neste navegador)
  const themeBtn = document.createElement("button");
  themeBtn.type = "button";
  themeBtn.className = "adm-theme";
  const paintTheme = () => {
    const dark = document.documentElement.classList.contains("theme-dark");
    themeBtn.innerHTML = `<span aria-hidden="true">${dark ? "🌙" : "☀️"}</span><span>${dark ? "Tema escuro" : "Tema claro"}</span><i class="adm-theme__switch"></i>`;
    themeBtn.setAttribute("aria-pressed", String(dark));
    themeBtn.title = dark ? "Voltar para o tema claro" : "Usar o tema escuro";
  };
  themeBtn.addEventListener("click", () => {
    const dark = document.documentElement.classList.toggle("theme-dark");
    localStorage.setItem("ajna-theme", dark ? "dark" : "light");
    paintTheme();
  });
  paintTheme();
  // rodapé do menu: vídeo explicativo + tema
  const navFoot = document.createElement("div");
  navFoot.className = "adm-nav__foot";
  navFoot.append(themeBtn);
  nav.append(navFoot);

  // bolinha no ☰ quando há pedidos pendentes (contador da "Visão geral")
  const syncDot = () => {
    const count = $(".adm-nav__count", nav);
    $(".adm-rail__dot", rail).hidden = !count || count.hidden || !Number(count.textContent);
  };
  new MutationObserver(syncDot).observe(nav, { subtree: true, childList: true, characterData: true, attributes: true });

  // ---------------------------------------------------------------- foto de perfil
  const initials = (name) => (name || "?").trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join("").toUpperCase();

  /** Mostra a foto (se houver) ou as iniciais num elemento .adm-avatar / .adm-client__avatar. */
  function paintAvatar(el, name, avatar) {
    if (!el) return;
    el.textContent = avatar ? "" : initials(name);
    el.style.backgroundImage = avatar ? `url("${avatar}")` : "";
    el.classList.toggle("has-photo", Boolean(avatar));
  }

  const avatarHtml = (name, avatar, cls = "adm-client__avatar") => avatar
    ? `<span class="${cls} has-photo" style="background-image:url(&quot;${avatar.replace(/"/g, "")}&quot;)" aria-hidden="true"></span>`
    : `<span class="${cls}" aria-hidden="true">${initials(name).replace(/[<>&]/g, "")}</span>`;

  // reduz para 320px (quadrado, centralizado) em JPEG
  function shrink(file) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const side = Math.min(img.width, img.height);
        const size = Math.min(320, side);
        const c = document.createElement("canvas");
        c.width = c.height = size;
        c.getContext("2d").drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, size, size);
        URL.revokeObjectURL(img.src);
        resolve(c.toDataURL("image/jpeg", 0.85));
      };
      img.onerror = () => reject(new Error("Não foi possível ler essa imagem."));
      img.src = URL.createObjectURL(file);
    });
  }

  const dlg = document.createElement("dialog");
  dlg.className = "adm-modal adm-modal--small photo-modal";
  dlg.innerHTML = `
    <div class="adm-form">
      <h2>Foto do perfil</h2>
      <p class="adm-muted">Opcional. Aparece no topo do painel${document.body.dataset.page === "admin" ? "" : " e na sua ficha na clínica"}.</p>
      <span class="adm-avatar photo-modal__preview"></span>
      <input type="file" accept="image/jpeg,image/png,image/webp" hidden>
      <p class="adm-form__error" role="alert"></p>
      <div class="photo-modal__actions">
        <button class="adm-btn adm-btn--primary" data-photo-pick type="button">📷 Escolher foto</button>
        <button class="adm-btn" data-photo-remove type="button">Remover foto</button>
        <button class="adm-btn adm-btn--ghost" data-photo-close type="button">Fechar</button>
      </div>
    </div>`;
  document.body.append(dlg);
  const input = $("input", dlg);
  const err = $(".adm-form__error", dlg);
  const me = { name: "", avatar: null, csrf: "" };
  const topAvatar = $(".adm-top__user .adm-avatar");

  async function save(image) {
    const res = await fetch("/api/auth/me/avatar", {
      method: "PUT", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": me.csrf },
      body: JSON.stringify({ image }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Não foi possível salvar a foto.");
    me.avatar = data.avatar;
    paintAvatar(topAvatar, me.name, me.avatar);
    paintAvatar($(".photo-modal__preview", dlg), me.name, me.avatar);
    $("[data-photo-remove]", dlg).hidden = !me.avatar;
  }

  function openPhoto() {
    err.textContent = "";
    paintAvatar($(".photo-modal__preview", dlg), me.name, me.avatar);
    $("[data-photo-remove]", dlg).hidden = !me.avatar;
    dlg.showModal();
  }

  $("[data-photo-pick]", dlg).addEventListener("click", () => input.click());
  $("[data-photo-close]", dlg).addEventListener("click", () => dlg.close());
  $("[data-photo-remove]", dlg).addEventListener("click", () => save(null).catch((e) => { err.textContent = e.message; }));
  input.addEventListener("change", async () => {
    const file = input.files[0];
    input.value = "";
    if (!file) return;
    err.textContent = "";
    try { await save(await shrink(file)); } catch (e) { err.textContent = e.message; }
  });

  if (topAvatar) {
    topAvatar.setAttribute("role", "button");
    topAvatar.setAttribute("tabindex", "0");
    topAvatar.setAttribute("title", "Foto do perfil");
    topAvatar.removeAttribute("aria-hidden");
    topAvatar.addEventListener("click", openPhoto);
    topAvatar.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openPhoto(); } });
  }


  // ---------------------------------------------------------------- boas-vindas (primeiro login)
  // Administração: vídeo do sistema. Cliente: guia do cliente + formulário de dados pessoais
  // (se a clínica já preencheu, aparece como preenchido para ele só conferir).
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const onb = document.createElement("dialog");
  onb.className = "adm-modal onb-modal";
  document.body.append(onb);
  let onbUser = null;

  async function api(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (me.csrf) headers["X-CSRF-Token"] = me.csrf;
    const res = await fetch(url, { credentials: "same-origin", ...options, headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.error || "Não foi possível concluir a ação.");
    return data;
  }

  function videoStep(isClient, firstTime) {
    const total = isClient && firstTime ? 2 : 1;
    onb.innerHTML = `
      <div class="onb">
        <div class="onb__head">
          <div>
            <p class="adm-eyebrow">${!firstTime ? "Vídeo explicativo" : total > 1 ? `Boas-vindas · passo 1 de ${total}` : "Boas-vindas"}</p>
            <h2>${firstTime ? `Olá, ${esc((onbUser.name || "").split(" ")[0])}! 💜` : "Como usar o sistema"}</h2>
            <p class="adm-muted">${isClient
              ? "Veja em poucos minutos como usar a sua área do cliente: agendar sessões, acompanhar sessões e manter seus dados em dia."
              : "Um passeio pelo sistema: agenda, clientes, prontuário, mapa de pontos e financeiro."}</p>
          </div>
          ${firstTime ? "" : '<button class="adm-nav__close onb__x" type="button" data-onb-close aria-label="Fechar"></button>'}
        </div>
        ${onbUser.has_video
          ? `<video class="onb__video" controls preload="metadata" playsinline poster="/api/auth/onboarding/poster"
               src="/api/auth/onboarding/video"></video>`
          : '<p class="adm-empty">O vídeo ainda não está disponível.</p>'}
        <div class="adm-form__actions onb__actions">
          ${firstTime && isClient
            ? '<button class="adm-btn adm-btn--primary" data-onb-next type="button">Continuar →</button>'
            : firstTime ? '<button class="adm-btn adm-btn--primary" data-onb-finish type="button">✓ Entendi, começar</button>'
            : '<button class="adm-btn adm-btn--primary" data-onb-close type="button">Fechar</button>'}
        </div>
      </div>`;
  }

  async function formStep() {
    const p = await api("/api/patient/me");
    const filled = Object.values(p.profile || {}).some(Boolean);
    const val = (k) => esc(p.profile?.[k] || "");
    onb.innerHTML = `
      <form class="onb adm-form" id="onb-form" novalidate>
        <div class="onb__head"><div>
          <p class="adm-eyebrow">Boas-vindas · passo 2 de 2</p>
          <h2>🪪 Seus dados pessoais</h2>
          ${filled
            ? '<p class="onb__done">✅ <b>Já preenchido pela clínica.</b> Confira se está tudo certo e corrija o que precisar.</p>'
            : '<p class="adm-muted">Preencha o que quiser agora — nenhum campo é obrigatório. Só você e a clínica veem estas informações.</p>'}
        </div></div>
        <div class="onb__fields">${p.profile_fields.map((sec) => `
          <fieldset class="cli-fieldset"><legend>${sec.icon} ${esc(sec.title)}</legend>
            <div class="cli-fields">${sec.fields.map((f) => `<label>${esc(f.label)}${f.type === "select"
              ? `<select name="${f.key}"><option value="">—</option>${f.options.map((o) => `<option ${o === p.profile?.[f.key] ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`
              : `<input name="${f.key}" type="${f.type === "date" ? "date" : "text"}" value="${val(f.key)}" ${f.placeholder ? `placeholder="${esc(f.placeholder)}"` : ""}
                  ${f.type === "cpf" ? 'data-mask="cpf" inputmode="numeric"' : f.type === "cep" ? 'data-mask="cep" inputmode="numeric"' : ""}>`}</label>`).join("")}</div>
          </fieldset>`).join("")}</div>
        <p class="adm-form__error" role="alert"></p>
        <div class="adm-form__actions onb__actions">
          <button class="adm-btn adm-btn--ghost" data-onb-finish type="button">Preencher depois</button>
          <button class="adm-btn adm-btn--primary" type="submit">${filled ? "✓ Está tudo certo" : "Salvar e começar"}</button>
        </div>
      </form>`;
    const form = onb.querySelector("#onb-form");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = {};
      p.profile_fields.flatMap((s) => s.fields).forEach((f) => { profile[f.key] = form.elements[f.key].value; });
      try {
        await api("/api/patient/me", { method: "PATCH", body: { profile } });
        await finish();
      } catch (err) { form.querySelector(".adm-form__error").textContent = err.message; }
    });
    onb.scrollTop = 0;
  }

  async function finish() {
    onb.querySelector("video")?.pause();
    try { await api("/api/auth/onboarding/done", { method: "POST", body: {} }); } catch { /* tenta de novo no próximo login */ }
    onbUser.onboarded = true;
    onb.close();
    if (location.hash === "#profile") location.reload();
  }

  onb.addEventListener("click", (e) => {
    if (e.target.closest("[data-onb-next]")) { onb.querySelector("video")?.pause(); formStep().catch(() => finish()); }
    else if (e.target.closest("[data-onb-finish]")) finish();
    else if (e.target.closest("[data-onb-close]")) { onb.querySelector("video")?.pause(); onb.close(); }
  });
  // no primeiro acesso a janela não fecha com Esc (precisa escolher um botão)
  onb.addEventListener("cancel", (e) => { if (!onbUser?.onboarded) e.preventDefault(); else onb.querySelector("video")?.pause(); });

  function openOnboarding(firstTime) {
    if (!onbUser) return;
    videoStep(onbUser.role === "patient", firstTime);
    onb.showModal();
  }

  // link no menu para rever o vídeo quando quiser
  const videoBtn = document.createElement("button");
  videoBtn.type = "button";
  videoBtn.className = "adm-theme adm-video-btn";
  videoBtn.innerHTML = '<span class="adm-nav__icon" aria-hidden="true">🎬</span><span>Vídeo explicativo</span>';
  videoBtn.addEventListener("click", () => { document.body.classList.remove("nav-open"); openOnboarding(false); });
  navFoot.prepend(videoBtn);

  window.AjnaShell = {
    paintAvatar,
    avatarHtml,
    openPhoto,
    csrf: () => me.csrf,
    /** Chamado pela página depois de carregar /api/auth/me. */
    setUser(user) {
      me.name = user.name;
      me.avatar = user.avatar || null;
      me.csrf = user.csrf_token || "";
      paintAvatar(topAvatar, me.name, me.avatar);
      onbUser = user;
      if (!user.onboarded) openOnboarding(true);  // primeiro login: boas-vindas
    },
    openOnboarding,
  };
})();
