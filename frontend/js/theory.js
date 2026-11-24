/* Mapa de pontos › 📚 Teórico: listas de pontos, diagnósticos da MTC, sintomas e combinações (cesta).
 * Usa as funções do painel expostas em window.AjnaAdmin (admin.js). Tudo editável.
 */
(() => {
  "use strict";
  const A = () => window.AjnaAdmin;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (v) => A().esc(v);
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  const POINT_FIELDS = [
    ["name_pt", "Nome em português", "text", "col"],
    ["location", "📍 Localização", "long", "col"],
    ["functions", "⚙️ Funções (MTC)", "long", "det"],
    ["indications", "💡 Indicações", "long", "col"],
    ["contraindications", "⚠️ Contraindicações e cuidados", "long", "det"],
    ["needling_depth", "📏 Profundidade de agulhamento", "text", "det"],
    ["needling_angle", "📐 Ângulo / direção", "text", "det"],
    ["technique", "🖐️ Técnica / manipulação", "text", "det"],
    ["moxa", "🔥 Moxabustão", "text", "det"],
    ["combinations_hint", "🔗 Combinações usadas com este ponto", "long", "det"],
    ["notes", "📝 Observações da clínica", "long", "col"],
  ];
  const KIND_FIELDS = {
    syndrome: [["cardinal_signs", "Sinais e sintomas cardinais"], ["tongue", "Língua"], ["pulse", "Pulso"],
               ["causes", "Causas"], ["emotional", "Aspectos emocionais"], ["diet", "Alimentação"],
               ["principle", "Princípio de tratamento"], ["tips", "Dicas de tratamento"], ["notes", "Observações"]],
    symptom: [["notes", "Observações"]],
    combination: [["indication", "Para que serve"], ["notes", "Observações"]],
    tongue: [["meaning", "Significado na MTC"], ["notes", "Observações"]],
  };
  const KIND_LABEL = { syndrome: "diagnóstico", symptom: "sintoma", combination: "combinação", tongue: "aspecto da língua" };
  const KIND_PLURAL = { syndrome: "diagnósticos", symptom: "sintomas", combination: "combinações", tongue: "aspectos da língua" };

  const st = {
    loaded: false, tab: "points", data: null, byCode: {}, sel: null,
    f: { q: "", mer: "", cat: "", syn: "", used: false, filled: false },
    basket: JSON.parse(localStorage.getItem("ajna-basket") || "[]"),
    pick: { q: "", mer: "", open: false }, // lista de pontos da cesta
  };
  const saveBasket = () => { localStorage.setItem("ajna-basket", JSON.stringify(st.basket)); renderBasketBadge(); };

  async function load(force = false) {
    if (st.loaded && !force) return;
    st.data = await A().api("/api/admin/theory");
    st.byCode = Object.fromEntries(st.data.points.map((p) => [p.code, p]));
    st.basket = st.basket.filter((c) => st.byCode[c]); // tira códigos que não existem mais (ex.: siglas antigas)
    st.loaded = true;
  }
  const items = (kind) => st.data.items.filter((i) => i.kind === kind);
  const merName = (code) => A().meridian(code)?.name || code;
  const color = (code) => A().meridian(st.byCode[code]?.meridian)?.color || "#6c5b73";
  const chip = (code) => `<button class="th-pchip" style="--c:${color(code)}" data-th-point="${esc(code)}" type="button" title="${esc(st.byCode[code]?.pinyin || "")}">${esc(code)}</button>`;

  // ---------------------------------------------------------------- estrutura
  function shell() {
    const root = $("#mp-theory");
    root.innerHTML = `
      <div class="th-top">
        <div class="cli-tabs th-tabs" role="tablist">
          <button class="cli-tab" data-th-tab="points" type="button">📍 Pontos</button>
          <button class="cli-tab" data-th-tab="syndrome" type="button">🩺 Diagnósticos MTC</button>
          <button class="cli-tab" data-th-tab="symptom" type="button">🤒 Sintomas</button>
          <button class="cli-tab" data-th-tab="combination" type="button">🧺 Combinações <span id="th-basket-badge"></span></button>
          <button class="cli-tab" data-th-tab="tongue" type="button">👅 Língua</button>
        </div>
        <input class="adm-search th-global" id="th-global" type="search" placeholder="🔎 Buscar em tudo: ponto, função, sintoma, diagnóstico…">
      </div>
      <div class="th-body">
        <section class="adm-card th-list" id="th-list"></section>
        <section class="adm-card th-detail" id="th-detail"></section>
      </div>`;
    $$("[data-th-tab]", root).forEach((b) => b.addEventListener("click", () => { st.sel = null; setTab(b.dataset.thTab); }));
    $("#th-global").addEventListener("input", (e) => { st.global = e.target.value; renderList(); });
    root.addEventListener("click", onClick);
    renderBasketBadge();
  }

  function setTab(tab) {
    st.tab = tab;
    $$("[data-th-tab]").forEach((b) => b.classList.toggle("is-active", b.dataset.thTab === tab));
    renderList();
    renderDetail();
  }

  function renderBasketBadge() {
    const b = $("#th-basket-badge");
    if (b) b.textContent = st.basket.length ? `(${st.basket.length})` : "";
  }

  // ---------------------------------------------------------------- listas
  function pointText(p) {
    const d = p.details || {};
    return norm([p.code, p.intl_code, p.pinyin, p.name_pt, p.location, p.indications, p.notes,
                 ...Object.values(d).flat()].join(" "));
  }

  function filteredPoints() {
    const f = st.f, q = norm(st.global || f.q);
    const synPts = f.syn ? new Set(items("syndrome").find((s) => s.id == f.syn)?.points || []) : null;
    return st.data.points.filter((p) =>
      (!f.mer || p.meridian === f.mer) &&
      (!f.cat || (p.details?.categories || []).includes(f.cat)) &&
      (!synPts || synPts.has(p.code)) &&
      (!f.used || A().usedCount(p.code)) &&
      (!f.filled || p.location || p.indications || p.details?.functions) &&
      (!q || q.split(/\s+/).every((w) => pointText(p).includes(w))));
  }

  function renderList() {
    const box = $("#th-list");
    if (st.tab === "points") return renderPointList(box);
    const kind = st.tab;
    const q = norm(st.global || st.f["q_" + kind] || "");
    const list = items(kind).filter((i) => !q || norm([i.name, i.group_name, ...Object.values(i.data).flat(), ...i.points].join(" ")).split(" ").join(" ").includes(q)
      || q.split(/\s+/).every((w) => norm([i.name, i.group_name, ...Object.values(i.data).flat(), ...i.points].join(" ")).includes(w)));
    const groups = {};
    list.forEach((i) => (groups[i.group_name || "Sem grupo"] ||= []).push(i));
    box.innerHTML = `
      <div class="th-list__head">
        <input class="adm-search" data-th-filter="q_${kind}" value="${esc(st.f["q_" + kind] || "")}" placeholder="Filtrar ${KIND_PLURAL[kind]}…">
        <button class="adm-btn adm-btn--primary adm-btn--sm" data-th-new="${kind}" type="button">＋ Novo ${KIND_LABEL[kind]}</button>
      </div>
      ${kind === "combination" ? basketHtml() : ""}
      <p class="adm-muted th-count">${list.length} ${list.length === 1 ? KIND_LABEL[kind] : KIND_PLURAL[kind]}</p>
      ${kind === "tongue" ? Object.entries(groups).map(([g, arr]) => `
        <h3 class="th-group">${esc(g)} <span>· ${arr.length}</span></h3>
        <div class="th-gallery">${arr.map((i) => `
          <button class="th-card ${st.sel?.kind === kind && st.sel.id === i.id ? "is-sel" : ""}" data-th-open="tongue:${i.id}" type="button">
            ${i.data.image ? `<img src="${i.data.image}" alt="">` : '<span class="th-card__ph">👅</span>'}
            <b>${esc(i.name)}</b>${i.data.meaning ? "" : "<em>a preencher</em>"}
          </button>`).join("")}</div>`).join("") : Object.entries(groups).map(([g, arr]) => `
        <h3 class="th-group">${esc(g)} <span>· ${arr.length}</span></h3>
        ${arr.map((i) => `
          <button class="th-row ${st.sel?.kind === kind && st.sel.id === i.id ? "is-sel" : ""}" data-th-open="${kind}:${i.id}" type="button">
            <b>${esc(i.name)}</b>
            <span>${i.points.length ? `${i.points.length} ponto(s)` : ""}${kind === "symptom" && i.data.syndromes?.length ? ` · ${i.data.syndromes.length} diagnóstico(s)` : ""}${!Object.keys(i.data).length ? " · <em>a preencher</em>" : ""}</span>
          </button>`).join("")}`).join("") || `<p class="adm-empty">Nada encontrado. Use “＋ Novo ${KIND_LABEL[kind]}”.</p>`}`;
    bindFilters(box);
  }

  function renderPointList(box) {
    const pts = filteredPoints();
    const mers = A().meridians();
    box.innerHTML = `
      <div class="th-filters">
        <input class="adm-search" data-th-filter="q" value="${esc(st.f.q)}" placeholder="Código, nome, função, indicação…">
        <select class="adm-select" data-th-filter="mer"><option value="">Todos os meridianos</option>
          ${mers.map((m) => `<option value="${m.code}" ${st.f.mer === m.code ? "selected" : ""}>${esc(m.code)} · ${esc(m.name)}</option>`).join("")}</select>
        <select class="adm-select" data-th-filter="cat"><option value="">Todas as categorias</option>
          ${st.data.categories.map((c) => `<option ${st.f.cat === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <select class="adm-select" data-th-filter="syn"><option value="">Pontos de um diagnóstico…</option>
          ${items("syndrome").map((s) => `<option value="${s.id}" ${st.f.syn == s.id ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select>
        <label class="pf-check"><input type="checkbox" data-th-filter="used" ${st.f.used ? "checked" : ""}> Já usados em sessões</label>
        <label class="pf-check"><input type="checkbox" data-th-filter="filled" ${st.f.filled ? "checked" : ""}> Com texto preenchido</label>
      </div>
      <p class="adm-muted th-count">${pts.length} ponto(s) <button class="adm-btn adm-btn--link" data-th-clear type="button">limpar filtros</button></p>
      <div class="th-table">${pts.slice(0, 500).map((p) => `
        <button class="th-row th-row--point ${st.sel?.kind === "point" && st.sel.id === p.code ? "is-sel" : ""}" data-th-open="point:${esc(p.code)}" type="button">
          <i style="--c:${color(p.code)}"></i>
          <b>${esc(p.code)}</b>
          <span class="th-row__name">${esc(p.pinyin)}${p.name_pt ? ` · ${esc(p.name_pt)}` : ""}</span>
          <span class="th-row__cats">${(p.details?.categories || []).slice(0, 3).map((c) => `<em>${esc(c)}</em>`).join("")}</span>
          ${p.location || p.indications || p.details?.functions ? '<span class="th-dot" title="Tem texto preenchido">●</span>' : ""}
        </button>`).join("")}</div>`;
    bindFilters(box);
  }

  function bindFilters(box) {
    $$("[data-th-filter]", box).forEach((el) => {
      const ev = el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input";
      el.addEventListener(ev, () => {
        st.f[el.dataset.thFilter] = el.type === "checkbox" ? el.checked : el.value;
        const pos = el.selectionStart;
        renderList();
        if (ev === "input") { const n = $(`[data-th-filter="${el.dataset.thFilter}"]`); n.focus(); n.setSelectionRange?.(pos, pos); }
      });
    });
  }

  // ---------------------------------------------------------------- detalhe / edição
  function renderDetail() {
    const box = $("#th-detail");
    if (!st.sel) {
      box.innerHTML = introHtml();
      return;
    }
    if (st.sel.kind === "point") return renderPointDetail(box, st.byCode[st.sel.id]);
    const item = st.sel.id === "new" ? { kind: st.sel.kind, name: "", group_name: "", data: {}, points: [] }
      : st.data.items.find((i) => i.id === st.sel.id && i.kind === st.sel.kind);
    if (!item) { st.sel = null; return renderDetail(); }
    renderItemDetail(box, item);
  }

  function introHtml() {
    const filled = st.data.points.filter((p) => p.location || p.indications || p.details?.functions).length;
    const tips = {
      points: `<b>${st.data.points.length}</b> pontos · <b>${filled}</b> com texto preenchido. Escolha um ponto à esquerda para ver e editar a ficha técnica. As categorias padrão (Yuan, Luo, Xi, cinco Shu com elemento, Shu do dorso, Mu, Hui, abertura dos vasos extraordinários, Janela do Céu) já vêm marcadas.`,
      syndrome: "Diagnósticos (padrões) da MTC com sinais cardinais, língua, pulso, causas, princípio de tratamento e a combinação de pontos. Os nomes padrão já estão cadastrados; o conteúdo é da clínica.",
      symptom: "Sintomas ligados aos diagnósticos e aos pontos. Ao buscar um sintoma, você chega ao diagnóstico e aos pontos.",
      tongue: "Diagnóstico pela língua: os aspectos padrão (cor, forma, saburra, umidade, veias sublinguais) já estão cadastrados. Adicione o significado na MTC, os diagnósticos relacionados e fotos da clínica.",
      combination: "Monte combinações de pontos: adicione pontos à 🧺 cesta (na ficha de cada ponto) e salve. As combinações podem ser inseridas direto no protocolo de uma sessão.",
    };
    return `<h2 class="mp-panel__title">📚 Teórico</h2><p class="adm-muted">${tips[st.tab]}</p>
      <p class="adm-muted th-legal">Estrutura inspirada em atlas de acupuntura. As classificações padrão são de domínio técnico; os textos clínicos devem ser escritos pela clínica.</p>`;
  }

  function renderPointDetail(box, p) {
    const d = p.details || {};
    const cats = d.categories || [];
    const inSyn = items("syndrome").filter((s) => s.points.includes(p.code));
    const inCombo = items("combination").filter((s) => s.points.includes(p.code));
    const inBasket = st.basket.includes(p.code);
    box.innerHTML = `
      <div class="mp-panel__head" style="--c:${color(p.code)}">
        <span class="mp-swatch"></span>
        <div><h2>${esc(p.code)} <small>${esc(p.pinyin)}</small></h2>
          <p class="adm-muted">${esc(merName(p.meridian))}${p.intl_code ? ` · ${esc(p.intl_code)}` : ""}${p.custom ? " · ponto extra" : ""}</p></div>
      </div>
      <div class="th-actions">
        <button class="adm-btn adm-btn--sm" data-th-map="${esc(p.code)}" type="button">👁 Ver no mapa visual</button>
        <button class="adm-btn adm-btn--sm ${inBasket ? "adm-btn--confirm" : ""}" data-th-basket="${esc(p.code)}" type="button">${inBasket ? "✓ Na cesta" : "🧺 Adicionar à cesta"}</button>
      </div>
      <form class="adm-form adm-form--inline th-form" id="th-point-form">
        <fieldset class="th-cats"><legend>🏷️ Categorias</legend>
          <div class="pf-chips">${[...new Set([...cats, ...st.data.categories])].sort().map((c) => `
            <label class="pf-chip"><input type="checkbox" name="cat" value="${esc(c)}" ${cats.includes(c) ? "checked" : ""}><span>${esc(c)}</span></label>`).join("")}</div>
          <input name="cat_new" placeholder="＋ Nova categoria (ex.: Ponto mestre do…) e salve">
        </fieldset>
        ${POINT_FIELDS.map(([k, label, type, where]) => {
          const v = where === "col" ? p[k] : d[k];
          return `<label>${label}${type === "long" ? `<textarea name="${k}" rows="3">${esc(v || "")}</textarea>` : `<input name="${k}" value="${esc(v || "")}">`}</label>`;
        }).join("")}
        <p class="adm-form__error" role="alert"></p>
        <div class="adm-form__actions pf-sticky-actions">
          ${p.updated_at ? `<span class="adm-muted mp-updated">Editado em ${A().dateBR(p.updated_at)}</span>` : ""}
          <button class="adm-btn adm-btn--primary" type="submit">Salvar ficha do ponto</button>
        </div>
      </form>
      ${inSyn.length ? `<h3 class="mp-subtitle">🩺 Usado nos diagnósticos</h3><div class="th-links">${inSyn.map((s) => `<button class="th-link" data-th-open="syndrome:${s.id}" type="button">${esc(s.name)}</button>`).join("")}</div>` : ""}
      ${inCombo.length ? `<h3 class="mp-subtitle">🧺 Nas combinações</h3><div class="th-links">${inCombo.map((s) => `<button class="th-link" data-th-open="combination:${s.id}" type="button">${esc(s.name)}</button>`).join("")}</div>` : ""}`;
    $("#th-point-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.currentTarget;
      const body = { details: { categories: $$('input[name="cat"]:checked', f).map((i) => i.value) } };
      if (f.elements.cat_new.value.trim()) body.details.categories.push(f.elements.cat_new.value.trim());
      POINT_FIELDS.forEach(([k, , , where]) => { if (where === "col") body[k] = f.elements[k].value; else body.details[k] = f.elements[k].value; });
      try {
        await A().api(`/api/admin/theory/points/${encodeURIComponent(p.code)}`, { method: "PATCH", body });
        A().toast(`Ficha de ${p.code} salva.`);
        await load(true);
        A().reloadMapPoints();
        renderList();
        renderDetail();
      } catch (err) { $(".adm-form__error", f).textContent = err.message; }
    });
  }

  function renderItemDetail(box, item) {
    const kind = item.kind;
    const syndromes = items("syndrome");
    const linkedSymptoms = kind === "syndrome" && item.id ? items("symptom").filter((s) => (s.data.syndromes || []).includes(item.id)) : [];
    box.innerHTML = `
      <h2 class="mp-panel__title">${item.id ? "" : "Novo "}${KIND_LABEL[kind][0].toUpperCase() + KIND_LABEL[kind].slice(1)}</h2>
      <form class="adm-form adm-form--inline th-form" id="th-item-form">
        <label>Nome<input name="name" required value="${esc(item.name)}"></label>
        <label>${kind === "syndrome" ? "Órgão / grupo" : "Grupo"}<input name="group_name" list="th-groups-${kind}" value="${esc(item.group_name || "")}"
          placeholder="${kind === "syndrome" ? "Ex.: Rim" : kind === "symptom" ? "Ex.: Digestivo, Dor, Sono…" : "Ex.: Ansiedade"}"></label>
        <datalist id="th-groups-${kind}">${[...new Set(items(kind).map((i) => i.group_name).filter(Boolean))].map((g) => `<option value="${esc(g)}">`).join("")}</datalist>
        ${KIND_FIELDS[kind].map(([k, label]) => `<label>${label}<textarea name="${k}" rows="${k === "notes" ? 2 : 3}">${esc(item.data[k] || "")}</textarea></label>`).join("")}
        ${kind === "tongue" ? `
          <fieldset class="th-cats th-photo"><legend>📷 Foto</legend>
            <div class="th-photo__box">${item.data.image ? `<img src="${item.data.image}" alt="Foto">` : '<span class="th-card__ph">👅</span>'}</div>
            <input type="file" accept="image/*" capture="environment" data-th-photo>
            ${item.data.image ? '<button class="adm-btn adm-btn--sm" data-th-photo-rm type="button">Remover foto</button>' : ""}
            <p class="adm-muted">Use fotos da própria clínica (com consentimento do paciente). A imagem é reduzida automaticamente.</p>
          </fieldset>` : ""}
        ${kind === "symptom" || kind === "tongue" ? `
          <fieldset class="th-cats"><legend>🩺 Diagnósticos relacionados</legend>
            <input class="th-mini-search" placeholder="Filtrar diagnósticos…" data-th-minifilter>
            <div class="th-checklist">${syndromes.map((s) => `
              <label class="pf-check" data-th-mini="${esc(norm(s.name))}"><input type="checkbox" name="syn" value="${s.id}" ${(item.data.syndromes || []).includes(s.id) ? "checked" : ""}> ${esc(s.name)} <span class="adm-muted">· ${esc(s.group_name || "")}</span></label>`).join("")}</div>
          </fieldset>` : ""}
        <label>Pontos
          <div class="pf-points" data-th-points>
            <div class="pf-points__chips">${item.points.map((c) => `<span class="pf-pchip" data-code="${esc(c)}" style="--c:${color(c)}"><button class="pf-pchip__open" data-th-point="${esc(c)}" type="button">${esc(c)}</button><button class="pf-pchip__x" data-th-rm type="button">×</button></span>`).join("")}</div>
            <div class="pf-points__add">
              <input type="text" list="acupoint-list" placeholder="Código ou nome do ponto e Enter" data-th-add-input>
              ${st.basket.length ? `<button class="adm-btn adm-btn--sm" data-th-from-basket type="button">🧺 Usar a cesta (${st.basket.length})</button>` : ""}
            </div>
          </div>
        </label>
        <p class="adm-form__error" role="alert"></p>
        <div class="adm-form__actions pf-sticky-actions">
          ${item.id ? `<button class="adm-btn adm-btn--danger-ghost" data-th-del type="button">Excluir</button>` : ""}
          <button class="adm-btn adm-btn--primary" type="submit">Salvar</button>
        </div>
      </form>
      ${linkedSymptoms.length ? `<h3 class="mp-subtitle">🤒 Sintomas ligados</h3><div class="th-links">${linkedSymptoms.map((s) => `<button class="th-link" data-th-open="symptom:${s.id}" type="button">${esc(s.name)}</button>`).join("")}</div>` : ""}
      ${(kind === "symptom" || kind === "tongue") && (item.data.syndromes || []).length ? `<h3 class="mp-subtitle">🩺 Abrir diagnóstico</h3><div class="th-links">${item.data.syndromes.map((id) => syndromes.find((s) => s.id === id)).filter(Boolean).map((s) => `<button class="th-link" data-th-open="syndrome:${s.id}" type="button">${esc(s.name)}</button>`).join("")}</div>` : ""}`;

    const form = $("#th-item-form");
    const chips = $(".pf-points__chips", form);
    const addCode = (raw) => {
      const code = A().resolvePoint(raw);
      if (!code) return A().toast("Ponto não encontrado.", true);
      if (!$(`[data-code="${CSS.escape(code)}"]`, chips)) chips.insertAdjacentHTML("beforeend",
        `<span class="pf-pchip" data-code="${esc(code)}" style="--c:${color(code)}"><button class="pf-pchip__open" data-th-point="${esc(code)}" type="button">${esc(code)}</button><button class="pf-pchip__x" data-th-rm type="button">×</button></span>`);
    };
    $("[data-th-add-input]", form).addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addCode(e.target.value); e.target.value = ""; }
    });
    $("[data-th-from-basket]", form)?.addEventListener("click", () => st.basket.forEach(addCode));
    $("[data-th-photo]", form)?.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      form.dataset.image = await shrinkImage(file);
      $(".th-photo__box", form).innerHTML = `<img src="${form.dataset.image}" alt="Foto">`;
    });
    $("[data-th-photo-rm]", form)?.addEventListener("click", () => {
      form.dataset.image = "none";
      $(".th-photo__box", form).innerHTML = '<span class="th-card__ph">👅</span>';
    });
    $("[data-th-minifilter]", form)?.addEventListener("input", (e) => {
      const q = norm(e.target.value);
      $$("[data-th-mini]", form).forEach((l) => (l.hidden = q && !l.dataset.thMini.includes(q)));
    });
    form.addEventListener("click", async (e) => {
      if (e.target.closest("[data-th-rm]")) e.target.closest(".pf-pchip").remove();
      if (e.target.closest("[data-th-del]")) {
        if (!(await A().confirmAction(`Excluir “${item.name}”?`, "Isso não pode ser desfeito.", "Excluir"))) return;
        await A().api(`/api/admin/theory/${kind}/${item.id}`, { method: "DELETE" });
        A().toast("Excluído.");
        st.sel = null;
        await load(true);
        renderList(); renderDetail();
      }
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = {};
      KIND_FIELDS[kind].forEach(([k]) => (data[k] = form.elements[k].value));
      if (kind === "symptom" || kind === "tongue") data.syndromes = $$('input[name="syn"]:checked', form).map((i) => Number(i.value));
      if (kind === "tongue" && form.dataset.image !== "none") data.image = form.dataset.image || item.data.image;
      const body = { name: form.elements.name.value, group_name: form.elements.group_name.value, data,
                     points: $$(".pf-pchip", chips).map((c) => c.dataset.code) };
      try {
        const r = await A().api(item.id ? `/api/admin/theory/${kind}/${item.id}` : `/api/admin/theory/${kind}`,
          { method: item.id ? "PATCH" : "POST", body });
        A().toast("Salvo.");
        if (!item.id && kind === "combination") { st.basket = []; saveBasket(); }
        await load(true);
        st.sel = { kind, id: item.id || r.id };
        renderList(); renderDetail();
        A().refreshCombos?.();
      } catch (err) { $(".adm-form__error", form).textContent = err.message; }
    });
  }

  function shrinkImage(file, max = 900) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const k = Math.min(1, max / Math.max(img.width, img.height));
        const c = document.createElement("canvas");
        c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(img.src);
        resolve(c.toDataURL("image/jpeg", 0.82));
      };
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  }

  function basketTop() {
    return `<b>🧺 Cesta atual${st.basket.length ? ` · ${st.basket.length} ponto(s)` : ""}</b>
      <div class="th-links">${st.basket.map((c) => `<span class="th-basket__item">${chip(c)}<button data-th-unbasket="${esc(c)}" type="button" aria-label="Tirar">×</button></span>`).join("") || '<span class="adm-muted">Vazia. Marque os pontos na lista abaixo (ou abra um ponto e clique em “🧺 Adicionar à cesta”).</span>'}</div>
      ${st.basket.length ? `<div class="th-basket__actions"><button class="adm-btn adm-btn--sm adm-btn--primary" data-th-new="combination" type="button">Salvar como combinação</button>
        <button class="adm-btn adm-btn--sm" data-th-empty type="button">Esvaziar</button></div>` : ""}`;
  }

  // Lista de todos os pontos com caixinha: marcar = pôr na cesta, desmarcar = tirar.
  function pickRows() {
    const q = norm(st.pick.q);
    const words = q.split(/\s+/).filter(Boolean);
    const list = st.data.points.filter((p) => (!st.pick.mer || p.meridian === st.pick.mer)
      && words.every((w) => norm([p.code, p.pinyin, p.name_pt, p.intl_code].join(" ")).includes(w)));
    // ordem tradicional dos meridianos (LU, LI, ST…), depois orelha e extras
    const order = Object.fromEntries((A().meridians() || []).map((m, i) => [m.code, i]));
    list.sort((a, b) => (order[a.meridian] ?? 99) - (order[b.meridian] ?? 99) || (a.number ?? 0) - (b.number ?? 0) || a.code.localeCompare(b.code));
    if (!list.length) return '<p class="adm-empty">Nenhum ponto encontrado.</p>';
    return list.map((p) => `
      <label class="th-pick ${st.basket.includes(p.code) ? "is-on" : ""}">
        <input type="checkbox" data-th-pick="${esc(p.code)}" ${st.basket.includes(p.code) ? "checked" : ""}>
        <span class="th-pick__code" style="--c:${color(p.code)}">${esc(p.code)}</span>
        <span class="th-pick__name">${esc(p.pinyin)}${p.name_pt ? ` <small>${esc(p.name_pt)}</small>` : ""}</span>
      </label>`).join("");
  }

  function basketHtml() {
    const mers = A().meridians() || [];
    return `<div class="th-basket">
      <div id="th-basket-top">${basketTop()}</div>
      <details class="th-picker" id="th-picker" ${st.pick.open ? "open" : ""}>
        <summary>📋 Lista de pontos — marque para pôr na cesta</summary>
        <div class="th-picker__bar">
          <input class="adm-search" data-th-pick-q value="${esc(st.pick.q)}" placeholder="Buscar código, pinyin ou nome (ex.: LI4, Hegu)…" aria-label="Buscar ponto">
          <select class="adm-select" data-th-pick-mer aria-label="Meridiano">
            <option value="">Todos os meridianos</option>
            ${mers.map((m) => `<option value="${esc(m.code)}" ${st.pick.mer === m.code ? "selected" : ""}>${esc(m.code)} · ${esc(m.name)}</option>`).join("")}
          </select>
        </div>
        <div class="th-picker__list" id="th-pick-list">${pickRows()}</div>
      </details>
    </div>`;
  }

  function refreshBasket() {
    const top = $("#th-basket-top");
    if (top) top.innerHTML = basketTop();
  }

  document.addEventListener("input", (e) => {
    if (!e.target.matches?.("[data-th-pick-q]")) return;
    st.pick.q = e.target.value;
    $("#th-pick-list").innerHTML = pickRows();
  });
  document.addEventListener("change", (e) => {
    if (e.target.matches?.("[data-th-pick-mer]")) {
      st.pick.mer = e.target.value;
      $("#th-pick-list").innerHTML = pickRows();
      return;
    }
    const box = e.target.closest?.("[data-th-pick]");
    if (!box) return;
    const c = box.dataset.thPick;
    st.basket = box.checked ? [...new Set([...st.basket, c])] : st.basket.filter((x) => x !== c);
    box.closest(".th-pick").classList.toggle("is-on", box.checked);
    saveBasket();
    refreshBasket();
  });
  document.addEventListener("toggle", (e) => {
    if (e.target.id === "th-picker") st.pick.open = e.target.open;
  }, true);

  // ---------------------------------------------------------------- cliques
  function onClick(e) {
    const t = e.target;
    const open = t.closest("[data-th-open]");
    if (open) {
      const [kind, id] = open.dataset.thOpen.split(":");
      if (kind !== "point" && st.tab !== kind) setTab(kind);
      if (kind === "point" && st.tab !== "points") setTab("points");
      st.sel = { kind, id: kind === "point" ? id : Number(id) };
      renderList(); renderDetail();
      if (window.matchMedia("(max-width: 1100px)").matches) $("#th-detail").scrollIntoView({ behavior: "smooth" });
      return;
    }
    const pt = t.closest("[data-th-point]");
    if (pt) { st.sel = { kind: "point", id: pt.dataset.thPoint }; setTab("points"); return; }
    const nw = t.closest("[data-th-new]");
    if (nw) {
      st.sel = { kind: nw.dataset.thNew, id: "new" };
      renderDetail();
      if (nw.dataset.thNew === "combination" && st.basket.length) {
        const chipsBox = $("#th-item-form .pf-points__chips");
        st.basket.forEach((c) => chipsBox.insertAdjacentHTML("beforeend",
          `<span class="pf-pchip" data-code="${esc(c)}" style="--c:${color(c)}"><button class="pf-pchip__open" data-th-point="${esc(c)}" type="button">${esc(c)}</button><button class="pf-pchip__x" data-th-rm type="button">×</button></span>`));
      }
      $("#th-item-form [name=name]")?.focus();
      return;
    }
    const bk = t.closest("[data-th-basket]");
    if (bk) {
      const c = bk.dataset.thBasket;
      st.basket = st.basket.includes(c) ? st.basket.filter((x) => x !== c) : [...st.basket, c];
      saveBasket();
      A().toast(st.basket.includes(c) ? `${c} na cesta (${st.basket.length}).` : `${c} saiu da cesta.`);
      renderDetail();
      return;
    }
    const ub = t.closest("[data-th-unbasket]");
    if (ub) { st.basket = st.basket.filter((x) => x !== ub.dataset.thUnbasket); saveBasket(); renderList(); return; }
    if (t.closest("[data-th-empty]")) { st.basket = []; saveBasket(); renderList(); return; }
    if (t.closest("[data-th-clear]")) { st.f = { q: "", mer: "", cat: "", syn: "", used: false, filled: false }; renderList(); return; }
    const mp = t.closest("[data-th-map]");
    if (mp) A().showPointOnMap(mp.dataset.thMap);
  }

  // ---------------------------------------------------------------- entrada
  window.AjnaTheory = {
    async open(code) {
      await load(true);
      if (!$("#mp-theory .th-top")) shell();
      if (code) st.sel = { kind: "point", id: code };
      setTab(code ? "points" : st.tab);
    },
    combos: async () => { await load(); return items("combination"); },
  };
})();
