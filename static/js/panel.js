/* Panel pengelola — sedikit bantuan interaksi. Panel tetap berfungsi tanpa JavaScript. */
(function () {
  "use strict";

  /* Formulir yang perlu konfirmasi: <form data-confirm="..."> (mis. tutup obrolan) */
  document.addEventListener("submit", function (ev) {
    var msg = ev.target.getAttribute && ev.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) ev.preventDefault();
  });

  /* Menu samping di HP: dukungan untuk browser tanpa :has() */
  var menu = document.querySelector(".topbar-menu");
  var sidebar = document.querySelector(".sidebar");
  if (menu && sidebar) {
    menu.addEventListener("toggle", function () { sidebar.classList.toggle("is-open", menu.open); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") menu.open = false; });
  }

  /* Tambah baris formset ("Tambah baris") */
  document.querySelectorAll("[data-formset]").forEach(function (box) {
    var prefix = box.getAttribute("data-prefix");
    var total = box.querySelector("#id_" + prefix + "-TOTAL_FORMS");
    var max = box.querySelector("#id_" + prefix + "-MAX_NUM_FORMS");
    var rows = box.querySelector("[data-formset-rows]");
    var tpl = box.querySelector("template[data-formset-template]");
    var add = box.querySelector("[data-formset-add]");
    if (!total || !rows || !tpl || !add) return;
    add.addEventListener("click", function () {
      var index = parseInt(total.value, 10) || 0;
      if (max && index >= parseInt(max.value, 10)) { add.disabled = true; return; }
      var html = tpl.innerHTML.replace(/__prefix__/g, String(index));
      var wrap = document.createElement("div");
      wrap.innerHTML = html.trim();
      var row = wrap.firstElementChild;
      var num = row.querySelector(".row-num");
      if (num) num.textContent = String(index + 1);
      rows.appendChild(row);
      total.value = String(index + 1);
      var first = row.querySelector("input:not([type=hidden]), select, textarea");
      if (first) first.focus();
    });
  });

  /* Peringatan bila meninggalkan form yang sudah diubah tapi belum disimpan */
  var form = document.querySelector(".crud-form");
  if (form) {
    var dirty = false;
    form.addEventListener("input", function () { dirty = true; });
    form.addEventListener("submit", function () { dirty = false; });
    window.addEventListener("beforeunload", function (e) { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
  }
})();
