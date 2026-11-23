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

  window.AjnaShell = {
    paintAvatar,
    avatarHtml,
    openPhoto,
    /** Chamado pela página depois de carregar /api/auth/me. */
    setUser(user) {
      me.name = user.name;
      me.avatar = user.avatar || null;
      me.csrf = user.csrf_token || "";
      paintAvatar(topAvatar, me.name, me.avatar);
    },
  };
})();
