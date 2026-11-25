/* SIM: formulir KK + anggota.
   - Baris anggota kosong disembunyikan; tombol "Tambah baris anggota" memunculkannya satu per satu.
   - Nama kepala keluarga tampil otomatis dari anggota yang Hubungan-nya "Kepala Keluarga".
   Tanpa JavaScript semua baris tampil dan formulir tetap bisa disimpan. */
(function () {
  "use strict";
  var KEPALA = "Kepala Keluarga";
  document.querySelectorAll("[data-kk-editor]").forEach(function (editor) {
    var rows = Array.prototype.slice.call(editor.querySelectorAll("[data-member-row]"));
    var blank = rows.filter(function (r) { return r.hasAttribute("data-blank"); });
    var addWrap = editor.querySelector("[data-member-add-wrap]");
    var addBtn = editor.querySelector("[data-member-add]");
    var nameOut = editor.querySelector("[data-kepala-name]");

    // Sisakan satu baris kosong (atau baris pertama bila semua kosong) supaya formulir ringkas.
    blank.slice(1).forEach(function (r) { r.hidden = true; });
    function refreshAdd() {
      var hidden = rows.filter(function (r) { return r.hidden; });
      if (addWrap) addWrap.hidden = hidden.length === 0;
    }
    refreshAdd();
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        var next = rows.filter(function (r) { return r.hidden; })[0];
        if (!next) return;
        next.hidden = false;
        var input = next.querySelector("[data-nama]");
        if (input) input.focus();
        refreshAdd();
      });
    }

    function refreshKepala() {
      var head = null;
      rows.forEach(function (r) {
        var rel = r.querySelector("[data-hubungan]");
        var del = r.querySelector("input[type=checkbox][name$='-DELETE']");
        var isHead = !!(rel && rel.value === KEPALA && !(del && del.checked));
        var tag = r.querySelector("[data-kepala-tag]");
        if (tag) tag.hidden = !isHead;
        if (isHead && !head) head = r;
      });
      if (!nameOut) return;
      var name = head ? (head.querySelector("[data-nama]") || {}).value || "" : "";
      name = name.trim().toUpperCase();
      nameOut.textContent = name || nameOut.getAttribute("data-empty") || "";
      nameOut.classList.toggle("is-empty", !name);
    }
    editor.addEventListener("input", function (ev) {
      if (ev.target.matches("[data-nama]")) refreshKepala();
    });
    editor.addEventListener("change", function (ev) {
      if (ev.target.matches("[data-hubungan], input[type=checkbox]")) refreshKepala();
    });
    refreshKepala();
  });

  /* Tombol yang butuh waktu (mis. Baca ulang otomatis): tandai sedang bekerja & cegah klik ganda. */
  document.addEventListener("submit", function (ev) {
    var btn = ev.target.querySelector && ev.target.querySelector("button[data-busy]");
    if (!btn || ev.defaultPrevented) return;
    var label = btn.querySelector("span");
    if (label) label.textContent = btn.getAttribute("data-busy");
    btn.setAttribute("aria-disabled", "true");
    setTimeout(function () { btn.disabled = true; }, 0);
  });
})();

/* SIM: kecilkan foto KK/KTP di HP sebelum diunggah (hemat kuota & tetap terbaca),
   lalu tampilkan status "sedang membaca". Tanpa JavaScript, unggah tetap jalan apa adanya. */
(function () {
  "use strict";
  var form = document.querySelector("[data-scan-form]");
  if (!form) return;
  var input = form.querySelector("input[type=file][data-resize]");
  var status = form.querySelector("[data-scan-status]");
  var maxSide = input ? parseInt(input.getAttribute("data-resize"), 10) || 2600 : 2600;
  var busy = false;

  function shrink(file) {
    return new Promise(function (resolve) {
      if (!window.createImageBitmap || !window.DataTransfer || !/^image\/(jpeg|png|webp)$/.test(file.type)) {
        resolve(null);
        return;
      }
      createImageBitmap(file).then(function (bmp) {
        var scale = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
        if (scale >= 1 && file.size < 2.5 * 1024 * 1024) { resolve(null); return; }
        var canvas = document.createElement("canvas");
        canvas.width = Math.round(bmp.width * scale);
        canvas.height = Math.round(bmp.height * scale);
        canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function (blob) {
          resolve(blob ? new File([blob], "foto.jpg", { type: "image/jpeg" }) : null);
        }, "image/jpeg", 0.9);
      }).catch(function () { resolve(null); });
    });
  }

  form.addEventListener("submit", function (event) {
    if (busy || !input || !input.files || !input.files.length) {
      if (status) status.hidden = false;
      return;
    }
    event.preventDefault();
    busy = true;
    if (status) status.hidden = false;
    shrink(input.files[0]).then(function (small) {
      if (small) {
        var dt = new DataTransfer();
        dt.items.add(small);
        input.files = dt.files;
      }
      form.submit();
    });
  });
})();
