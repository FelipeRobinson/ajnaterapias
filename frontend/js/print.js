/* Relatórios para imprimir / salvar em PDF e planilhas (CSV que abre no Excel).
 * window.AjnaPrint.open({ title, subtitle, html }) abre uma página limpa, com o cabeçalho da clínica,
 * pronta para "Imprimir → Salvar como PDF". window.AjnaPrint.csv(nome, linhas) baixa a planilha.
 */
(() => {
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const logo = new URL("../img/logo (1).png", location.href).href;

  const CSS = `
    *{box-sizing:border-box} body{margin:0;font:13px/1.5 "Segoe UI",system-ui,sans-serif;color:#24152e;background:#f6f2f8}
    .page{max-width:900px;margin:0 auto;padding:28px 34px;background:#fff;min-height:100vh}
    .bar{position:sticky;top:0;display:flex;gap:8px;justify-content:center;padding:10px;background:#24063a}
    .bar button{padding:9px 16px;border:0;border-radius:10px;font:600 14px system-ui;cursor:pointer;background:#fff;color:#24063a}
    .bar button.primary{background:#9b42c7;color:#fff}
    .tip{position:sticky;top:57px;z-index:2;padding:10px 14px;background:#fff8e1;border-bottom:1px solid #f0d58a;text-align:center;font-size:14px}
    header{display:flex;align-items:center;gap:14px;padding-bottom:14px;margin-bottom:18px;border-bottom:2px solid #7800b4}
    header img{width:54px;height:54px;object-fit:contain;background:#24063a;border-radius:12px;padding:4px}
    header h1{margin:0;font-size:20px;color:#7800b4} header p{margin:2px 0 0;color:#6c5b73}
    header .gen{margin-left:auto;text-align:right;font-size:11px;color:#6c5b73}
    h2{margin:22px 0 8px;font-size:15px;color:#7800b4;border-bottom:1px solid #ebe2ef;padding-bottom:4px}
    h3{margin:16px 0 6px;font-size:13px}
    table{width:100%;border-collapse:collapse;margin:6px 0 12px} th,td{padding:6px 8px;border-bottom:1px solid #ebe2ef;text-align:left;vertical-align:top}
    th{background:#f6eefb;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c5b73}
    td.num,th.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
    .in{color:#15803d} .out{color:#b4233f}
    .kv{display:grid;grid-template-columns:220px 1fr;gap:4px 14px;margin:0} .kv dt{color:#6c5b73} .kv dd{margin:0;white-space:pre-wrap}
    .totals{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}
    .totals div{flex:1;min-width:150px;padding:10px 12px;border:1px solid #ebe2ef;border-radius:10px}
    .totals span{display:block;font-size:11px;color:#6c5b73} .totals b{font-size:17px}
    .muted{color:#6c5b73} .tag{display:inline-block;padding:1px 8px;margin:1px;border-radius:99px;background:#f1e6f7;font-size:11px}
    .session{page-break-inside:avoid;border:1px solid #ebe2ef;border-radius:10px;padding:10px 14px;margin:10px 0}
    .filters{font-size:12px;color:#6c5b73;margin:-8px 0 12px}
    .sheet{margin-top:26px;padding-top:18px;border-top:3px dashed #ebe2ef}
    .sheet h2:first-child{margin-top:0}
    footer{margin-top:28px;padding-top:10px;border-top:1px solid #ebe2ef;font-size:10px;color:#6c5b73;text-align:center}
    @media print{.tip{display:none!important}.sheet{break-before:page;page-break-before:always;margin-top:0;padding-top:0;border-top:0}body{background:#fff}.bar{display:none}.page{padding:0;max-width:none;min-height:0}@page{margin:14mm}}`;

  function open({ title, subtitle = "", html, confidential = false }) {
    const w = window.open("", "_blank");
    if (!w) { alert("O navegador bloqueou a janela do relatório. Permita pop-ups para este site."); return; }
    const now = new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
    w.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${esc(title)} — Ajna Terapias</title>
      <style>${CSS}</style></head><body>
      <div class="bar">
        <button class="primary" id="save-pdf" type="button">💾 Salvar PDF</button>
        <button class="primary" id="do-print" type="button">🖨️ Imprimir</button>
        <button type="button" onclick="close()">Fechar</button>
      </div>
      <div class="tip" id="tip" hidden>💡 Na janela que abrir, em <b>Destino</b>, escolha <b>“Salvar como PDF”</b> e clique em <b>Salvar</b>.</div>
      <div class="page">
        <header><img src="${logo}" alt=""><div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div>
          <div class="gen">Instituto Ajna Terapias Integrativas<br>e Complementares®<br>Gerado em ${esc(now)}</div></header>
        ${html}
        <footer>${confidential ? "Documento confidencial — dados de saúde protegidos pela LGPD. " : ""}Instituto Ajna Terapias Integrativas e Complementares®</footer>
      </div></body></html>`);
    w.document.close();
    // nome sugerido para o arquivo PDF (o navegador usa o título da página)
    const fileName = `${title} - ${subtitle}`.replace(/[\/:*?"<>|]+/g, "-").trim();
    const d = w.document;
    d.getElementById("do-print").onclick = () => { d.getElementById("tip").hidden = true; w.print(); };
    d.getElementById("save-pdf").onclick = () => {
      d.getElementById("tip").hidden = false;
      const old = d.title;
      d.title = fileName;
      setTimeout(() => { w.print(); d.title = old; }, 150);
    };
  }

  /** Baixa um CSV (separado por ";", com BOM) que o Excel em português abre certinho. */
  function csv(filename, rows) {
    const cell = (v) => {
      const s = String(v ?? "");
      return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const text = "﻿" + rows.map((r) => r.map(cell).join(";")).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    a.download = filename;
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }

  window.AjnaPrint = { open, csv, esc };
})();
