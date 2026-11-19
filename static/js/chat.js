/* HANS Project — chat pelanggan <-> admin (halaman akun & panel).
   Tanpa JavaScript, chat tetap jalan sebagai formulir biasa. Dengan skrip ini:
   - pesan terkirim tanpa memuat ulang halaman (fetch + FormData);
   - pesan baru dari lawan bicara diambil berkala (hanya saat tab terlihat);
   - tombol "Balas" pada gelembung, pratinjau gambar sebelum dikirim;
   - Enter = kirim di komputer (Shift+Enter = baris baru), aman untuk IME.
   HTML gelembung dibuat server (sudah di-escape), jadi aman disisipkan. */
(function () {
  "use strict";
  var thread = document.querySelector("[data-chat]");
  if (!thread) return;
  var form = document.querySelector("[data-chat-form]");
  var lastId = parseInt(thread.getAttribute("data-last-id") || "0", 10);
  var pollUrl = thread.getAttribute("data-poll-url");
  var POLL_MS = 8000;

  function nearBottom() { return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 120; }
  function toBottom() { thread.scrollTop = thread.scrollHeight; }

  /* Posisi awal: pesan terakhir. CSS scroll-initial-target bila didukung, selain itu JS. */
  if (!(window.CSS && CSS.supports && CSS.supports("scroll-initial-target", "nearest"))) toBottom();
  var stick = true;
  thread.addEventListener("scroll", function () { stick = nearBottom(); });
  thread.addEventListener("load", function (ev) {
    if (ev.target.tagName === "IMG" && stick) toBottom();
  }, true);

  function append(html) {
    if (!html) return;
    var keep = nearBottom();
    var tpl = document.createElement("template");
    tpl.innerHTML = html;
    var empty = thread.querySelector(".chat-empty");
    if (empty) empty.remove();
    Array.prototype.slice.call(tpl.content.children).forEach(function (node) {
      if (node.id && document.getElementById(node.id)) return; // sudah tampil (hindari dobel)
      thread.appendChild(node);
    });
    if (keep) toBottom();
  }

  /* ---------- Ambil pesan baru berkala ---------- */
  var polling = false;
  function poll() {
    if (polling || document.visibilityState !== "visible" || !pollUrl) return;
    polling = true;
    fetch(pollUrl + "?after=" + lastId, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        polling = false;
        if (!data) return;
        append(data.html);
        if (data.last_id > lastId) lastId = data.last_id;
        if (!data.open && thread.getAttribute("data-open") === "1") window.location.reload();
      })
      .catch(function () { polling = false; });
  }
  setInterval(poll, POLL_MS);
  document.addEventListener("visibilitychange", poll);

  if (!form) return;
  var text = form.querySelector("[data-chat-text]");
  var replyInput = form.querySelector("[data-reply-input]");
  var replyBar = form.querySelector("[data-reply-bar]");
  var replyText = form.querySelector("[data-reply-text]");
  var fileInput = form.querySelector("[data-file-input]");
  var fileBar = form.querySelector("[data-file-bar]");
  var fileName = form.querySelector("[data-file-name]");
  var filePreview = form.querySelector("[data-file-preview]");
  var errorBox = form.querySelector("[data-chat-error]");
  var sendBtn = form.querySelector("[data-chat-send]");
  var previewUrl = null;

  /* ---------- Balas pesan ---------- */
  function setReply(id, preview) {
    replyInput.value = id || "";
    replyText.textContent = preview || "";
    replyBar.hidden = !id;
  }
  thread.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-reply]");
    if (!btn) return;
    setReply(btn.getAttribute("data-reply"), btn.getAttribute("data-reply-text"));
    text.focus();
  });
  form.querySelector("[data-reply-cancel]").addEventListener("click", function () { setReply("", ""); text.focus(); });

  /* ---------- Gambar ---------- */
  function clearFile() {
    fileInput.value = "";
    fileBar.hidden = true;
    if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
  }
  fileInput.addEventListener("change", function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) { clearFile(); return; }
    if (file.size > 3 * 1024 * 1024) { showError("Ukuran gambar maksimal 3 MB."); clearFile(); return; }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    filePreview.src = previewUrl;
    fileName.textContent = file.name;
    fileBar.hidden = false;
    hideError();
  });
  form.querySelector("[data-file-clear]").addEventListener("click", clearFile);

  function showError(msg) { errorBox.textContent = msg; errorBox.hidden = false; }
  function hideError() { errorBox.hidden = true; }

  /* ---------- Enter = kirim (komputer), aman untuk IME ---------- */
  var finePointer = window.matchMedia && window.matchMedia("(pointer: fine)").matches;
  text.addEventListener("keydown", function (ev) {
    if (!finePointer || ev.key !== "Enter" || ev.shiftKey) return;
    ev.preventDefault();
    if (ev.isComposing || ev.keyCode === 229) return; // sedang menyusun huruf (IME)
    form.requestSubmit();
  });

  /* ---------- Kirim tanpa memuat ulang ---------- */
  var sending = false;
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (sending) return;
    if (!text.value.trim() && !(fileInput.files && fileInput.files.length)) {
      showError("Tulis pesan atau pilih gambar.");
      return;
    }
    sending = true;
    sendBtn.disabled = true;
    hideError();
    fetch(form.action || window.location.pathname, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      headers: { "Accept": "application/json" }
    }).then(function (res) {
      return res.json().catch(function () { return { ok: false, error: "Pesan gagal terkirim (" + res.status + "). Coba lagi." }; });
    }).then(function (data) {
      sending = false;
      sendBtn.disabled = false;
      if (!data.ok) { showError(data.error || "Pesan gagal terkirim. Coba lagi."); return; }
      append(data.html);
      if (data.last_id > lastId) lastId = data.last_id;
      text.value = "";
      setReply("", "");
      clearFile();
      toBottom();
      text.focus();
    }).catch(function () {
      sending = false;
      sendBtn.disabled = false;
      showError("Internet terputus. Pesan belum terkirim, coba lagi.");
    });
  });
})();
