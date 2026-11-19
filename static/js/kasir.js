/* HANS Project — layar kasir (subdomain toko /kasir/).
   - Data barang ada di <script type="application/json" id="pos-data"> (tanpa request tambahan).
   - Harga & total di layar hanya tampilan: server SELALU menghitung ulang dari database.
   - Setiap transaksi punya kode unik (key). Bila internet putus saat menekan Bayar lalu dicoba lagi,
     server mengenali kode yang sama, jadi transaksi tidak tercatat dua kali.
   - Keranjang disimpan sementara di sessionStorage supaya tidak hilang bila halaman termuat ulang. */
(function () {
  "use strict";

  /* Konfirmasi untuk <form data-confirm="..."> (mis. tombol Keluar) */
  document.addEventListener("submit", function (ev) {
    var msg = ev.target.getAttribute && ev.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) ev.preventDefault();
  });

  var app = document.querySelector("[data-pos-app]");
  if (!app) return;
  var dataEl = document.getElementById("pos-data");
  var data = JSON.parse(dataEl.textContent);
  var tokenEl = app.querySelector("input[name=csrfmiddlewaretoken]");
  var STORE_KEY = "hp-kasir:" + location.host + ":" + (app.getAttribute("data-cashier") || "");
  var MAX_SHOWN = 240;

  var byId = {};
  data.products.forEach(function (p) { byId[p.id] = p; });

  function $(sel) { return app.querySelector(sel); }
  function rupiah(n) { return "Rp" + Math.round(n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function digits(v) { var d = String(v || "").replace(/\D/g, ""); return d ? parseInt(d.slice(0, 10), 10) : 0; }
  function newKey() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var a = new Uint8Array(16); (window.crypto || window.msCrypto).getRandomValues(a);
    return Array.prototype.map.call(a, function (b) { return ("0" + b.toString(16)).slice(-2); }).join("");
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  var ui = {
    search: $("[data-search]"), cats: $("[data-cats]"), grid: $("[data-grid]"), gridEmpty: $("[data-grid-empty]"),
    gridMore: $("[data-grid-more]"), panel: $("[data-cart-panel]"), lines: $("[data-lines]"), cartEmpty: $("[data-cart-empty]"),
    clear: $("[data-clear]"), subtotal: $("[data-subtotal]"), discType: $("[data-disc-type]"), discValue: $("[data-disc-value]"),
    discRow: $("[data-disc-row]"), discount: $("[data-discount]"), total: $("[data-total]"), cash: $("[data-cash]"),
    paid: $("[data-paid]"), quick: $("[data-quick]"), change: $("[data-change]"), error: $("[data-error]"), pay: $("[data-pay]"),
    barCount: $("[data-bar-count]"), barTotal: $("[data-bar-total]"), openCart: $("[data-open-cart]"), closeCart: $("[data-close-cart]"),
    done: $("[data-done]"), doneNumber: $("[data-done-number]"), doneTotal: $("[data-done-total]"), donePaid: $("[data-done-paid]"),
    doneMethod: $("[data-done-method]"), doneChange: $("[data-done-change]"), doneReceipt: $("[data-done-receipt]"), newSale: $("[data-new]")
  };

  /* ---------- Keadaan ---------- */
  var state = { cart: [], key: newKey(), category: 0, query: "", sending: false };

  function save() {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify({ cart: state.cart, key: state.key })); } catch (e) { /* abaikan */ }
  }
  function restore() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || "null");
      if (saved && Array.isArray(saved.cart)) {
        state.cart = saved.cart.filter(function (l) { return byId[l.id] && l.qty > 0; });
        if (saved.key && state.cart.length) state.key = saved.key;
      }
    } catch (e) { /* abaikan */ }
  }

  function lineOf(id) {
    for (var i = 0; i < state.cart.length; i++) if (state.cart[i].id === id) return state.cart[i];
    return null;
  }
  function setQty(id, qty) {
    qty = Math.max(0, Math.min(9999, qty));
    var line = lineOf(id);
    if (!line && qty > 0) state.cart.push({ id: id, qty: qty });
    else if (line && qty === 0) state.cart = state.cart.filter(function (l) { return l.id !== id; });
    else if (line) line.qty = qty;
    hideError();
    save();
    renderCart();
    renderGridBadges();
  }

  function totals() {
    var subtotal = 0, count = 0;
    state.cart.forEach(function (l) { subtotal += byId[l.id].p * l.qty; count += l.qty; });
    var type = ui.discType.value, value = digits(ui.discValue.value), discount = 0;
    if (type === "rp") discount = Math.min(value, subtotal);
    if (type === "persen") { value = Math.min(value, 100); discount = Math.floor(subtotal * value / 100); }
    return { subtotal: subtotal, count: count, discount: discount, total: subtotal - discount, type: type, value: value };
  }
  function method() {
    var checked = app.querySelector("input[name=pos-method]:checked");
    return checked ? checked.value : "tunai";
  }

  /* ---------- Katalog ---------- */
  function renderCats() {
    if (!data.categories.length) { ui.cats.hidden = true; return; }
    var all = [{ id: 0, n: "Semua" }].concat(data.categories);
    if (data.products.some(function (p) { return !p.c; })) all.push({ id: -1, n: "Lainnya" });
    all.forEach(function (c) {
      var b = el("button", "pos-cat", c.n);
      b.type = "button";
      b.setAttribute("aria-pressed", c.id === state.category ? "true" : "false");
      b.addEventListener("click", function () {
        state.category = c.id;
        Array.prototype.forEach.call(ui.cats.children, function (x) { x.setAttribute("aria-pressed", "false"); });
        b.setAttribute("aria-pressed", "true");
        renderGrid();
      });
      ui.cats.appendChild(b);
    });
  }

  function matches(p) {
    if (state.category > 0 && p.c !== state.category) return false;
    if (state.category === -1 && p.c) return false;
    if (!state.query) return true;
    return p.n.toLowerCase().indexOf(state.query) !== -1 || (p.k && p.k.toLowerCase() === state.query);
  }

  function renderGrid() {
    var list = data.products.filter(matches);
    ui.grid.textContent = "";
    var frag = document.createDocumentFragment();
    list.slice(0, MAX_SHOWN).forEach(function (p) {
      var b = el("button", "pos-item");
      b.type = "button";
      b.setAttribute("data-id", p.id);
      b.appendChild(el("span", "pos-item-name", p.n));
      b.appendChild(el("span", "pos-item-price", rupiah(p.p)));
      var badge = el("span", "pos-item-qty");
      badge.setAttribute("aria-hidden", "true");
      b.appendChild(badge);
      frag.appendChild(b);
    });
    ui.grid.appendChild(frag);
    ui.gridEmpty.hidden = list.length > 0;
    ui.gridMore.hidden = list.length <= MAX_SHOWN;
    renderGridBadges();
  }

  function renderGridBadges() {
    Array.prototype.forEach.call(ui.grid.children, function (b) {
      var line = lineOf(parseInt(b.getAttribute("data-id"), 10));
      var badge = b.lastChild;
      badge.textContent = line ? line.qty : "";
      b.classList.toggle("in-cart", !!line);
      b.setAttribute("aria-label", b.firstChild.textContent + ", " + b.children[1].textContent + (line ? ", di keranjang " + line.qty : ""));
    });
  }

  ui.grid.addEventListener("click", function (ev) {
    var b = ev.target.closest(".pos-item");
    if (!b) return;
    var id = parseInt(b.getAttribute("data-id"), 10);
    var line = lineOf(id);
    setQty(id, (line ? line.qty : 0) + 1);
    b.classList.remove("bump"); void b.offsetWidth; b.classList.add("bump");
  });

  ui.search.addEventListener("input", function () {
    state.query = ui.search.value.trim().toLowerCase();
    renderGrid();
  });
  ui.search.addEventListener("keydown", function (ev) {
    // Pemindai barcode biasanya mengetik kode lalu Enter: langsung masukkan ke keranjang.
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    var q = state.query;
    var exact = data.products.filter(function (p) { return p.k && p.k.toLowerCase() === q; });
    var list = exact.length ? exact : data.products.filter(matches);
    if (list.length === 1) {
      var line = lineOf(list[0].id);
      setQty(list[0].id, (line ? line.qty : 0) + 1);
      ui.search.value = ""; state.query = ""; renderGrid();
    }
  });

  /* ---------- Keranjang ---------- */
  function renderCart() {
    var t = totals();
    ui.lines.textContent = "";
    var frag = document.createDocumentFragment();
    state.cart.forEach(function (l) {
      var p = byId[l.id];
      var li = el("li", "pos-line");
      var info = el("div", "pos-line-info");
      info.appendChild(el("b", "", p.n));
      info.appendChild(el("span", "muted", rupiah(p.p) + " × " + l.qty));
      li.appendChild(info);
      var ctr = el("div", "pos-qty");
      var minus = el("button", "pos-qty-btn", "−"); minus.type = "button"; minus.setAttribute("aria-label", "Kurangi " + p.n);
      minus.addEventListener("click", function () { setQty(l.id, l.qty - 1); });
      var input = el("input", "pos-qty-input"); input.type = "text"; input.inputMode = "numeric"; input.value = l.qty;
      input.setAttribute("aria-label", "Jumlah " + p.n);
      input.addEventListener("change", function () { setQty(l.id, digits(input.value)); });
      var plus = el("button", "pos-qty-btn", "+"); plus.type = "button"; plus.setAttribute("aria-label", "Tambah " + p.n);
      plus.addEventListener("click", function () { setQty(l.id, l.qty + 1); });
      ctr.appendChild(minus); ctr.appendChild(input); ctr.appendChild(plus);
      li.appendChild(ctr);
      li.appendChild(el("b", "pos-line-total", rupiah(p.p * l.qty)));
      frag.appendChild(li);
    });
    ui.lines.appendChild(frag);
    ui.cartEmpty.hidden = state.cart.length > 0;
    ui.clear.hidden = state.cart.length === 0;
    renderTotals(t);
  }

  function renderTotals(t) {
    t = t || totals();
    ui.subtotal.textContent = rupiah(t.subtotal);
    ui.discRow.hidden = t.discount === 0;
    ui.discount.textContent = "−" + rupiah(t.discount);
    ui.total.textContent = rupiah(t.total);
    ui.barCount.textContent = t.count + " barang";
    ui.barTotal.textContent = rupiah(t.total);
    var cash = method() === "tunai";
    ui.cash.hidden = !cash;
    var paid = digits(ui.paid.value);
    var short = cash && paid < t.total;
    ui.change.textContent = cash && paid >= t.total ? rupiah(paid - t.total) : "–";
    ui.pay.disabled = state.sending || !state.cart.length || short;
    ui.pay.textContent = !state.cart.length ? "Keranjang kosong" : short ? "Isi uang diterima" : "Selesaikan pembayaran " + rupiah(t.total);
    renderQuick(t.total);
  }

  var lastQuickTotal = -1;
  function renderQuick(total) {
    if (total === lastQuickTotal) return;
    lastQuickTotal = total;
    ui.quick.textContent = "";
    if (!total) return;
    var options = [total];
    [5000, 10000, 20000, 50000, 100000].forEach(function (step) {
      var v = Math.ceil(total / step) * step;
      if (v > total && options.indexOf(v) === -1) options.push(v);
    });
    options.sort(function (a, b) { return a - b; }).slice(0, 5).forEach(function (v, i) {
      var b = el("button", "pos-chip", i === 0 ? "Uang pas" : rupiah(v));
      b.type = "button";
      b.addEventListener("click", function () { ui.paid.value = v.toLocaleString("id-ID"); renderTotals(); });
      ui.quick.appendChild(b);
    });
  }

  function formatMoneyInput(input) {
    var v = digits(input.value);
    input.value = v ? v.toLocaleString("id-ID") : "";
  }

  ui.clear.addEventListener("click", function () {
    if (!window.confirm("Kosongkan keranjang?")) return;
    state.cart = []; save(); renderCart(); renderGridBadges();
  });
  ui.discType.addEventListener("change", function () {
    ui.discValue.hidden = !ui.discType.value;
    ui.discValue.placeholder = ui.discType.value === "persen" ? "Contoh: 10" : "Contoh: 5.000";
    if (!ui.discType.value) ui.discValue.value = "";
    else ui.discValue.focus();
    renderTotals();
  });
  ui.discValue.addEventListener("input", function () {
    if (ui.discType.value === "rp") formatMoneyInput(ui.discValue);
    renderTotals();
  });
  ui.paid.addEventListener("input", function () { formatMoneyInput(ui.paid); renderTotals(); });
  Array.prototype.forEach.call(app.querySelectorAll("input[name=pos-method]"), function (r) {
    r.addEventListener("change", function () { renderTotals(); if (method() === "tunai") ui.paid.focus(); });
  });

  /* Panel keranjang di HP */
  function openCart(open) {
    app.classList.toggle("cart-open", open);
    if (open) ui.panel.focus();
  }
  ui.openCart.addEventListener("click", function () { openCart(true); });
  ui.closeCart.addEventListener("click", function () { openCart(false); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !ui.done.open) openCart(false); });

  /* ---------- Bayar ---------- */
  function showError(msg) { ui.error.textContent = msg; ui.error.hidden = false; }
  function hideError() { ui.error.hidden = true; }

  ui.pay.addEventListener("click", function () {
    if (state.sending || !state.cart.length) return;
    var t = totals();
    if (t.type === "rp" && digits(ui.discValue.value) > t.subtotal) { showError("Diskon lebih besar dari total belanja."); return; }
    var payload = {
      key: state.key,
      items: state.cart.map(function (l) { return { id: l.id, qty: l.qty }; }),
      discount_type: t.discount ? t.type : "",
      discount_value: t.discount ? t.value : 0,
      method: method(),
      paid: method() === "tunai" ? digits(ui.paid.value) : t.total
    };
    state.sending = true;
    hideError();
    renderTotals(t);
    ui.pay.textContent = "Menyimpan…";
    fetch(data.pay_url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "Accept": "application/json", "X-CSRFToken": tokenEl ? tokenEl.value : "" },
      body: JSON.stringify(payload)
    }).then(function (res) {
      return res.json().catch(function () { return { ok: false, error: "Server sedang bermasalah (" + res.status + "). Coba lagi." }; });
    }).then(function (body) {
      state.sending = false;
      if (body.ok) { finish(body.sale); return; }
      if (body.login) { window.location.reload(); return; }
      showError(body.error || "Transaksi gagal disimpan. Coba lagi.");
      renderTotals();
    }).catch(function () {
      state.sending = false;
      // Kode transaksi tetap sama: aman untuk menekan Bayar lagi.
      showError("Internet terputus. Periksa koneksi, lalu tekan tombol bayar lagi. Transaksi tidak akan tercatat dua kali.");
      renderTotals();
    });
  });

  function finish(sale) {
    ui.doneNumber.textContent = sale.number;
    ui.doneTotal.textContent = rupiah(sale.total);
    ui.donePaid.textContent = rupiah(sale.paid);
    ui.doneMethod.textContent = sale.method;
    ui.doneChange.textContent = rupiah(sale.change);
    ui.doneReceipt.href = sale.receipt_url + "?cetak=1";
    state.cart = []; state.key = newKey();
    ui.paid.value = ""; ui.discType.value = ""; ui.discValue.value = ""; ui.discValue.hidden = true;
    var cashRadio = app.querySelector("input[name=pos-method][value=tunai]");
    if (cashRadio) cashRadio.checked = true;
    save();
    openCart(false);
    renderCart(); renderGridBadges();
    ui.done.showModal();
  }

  /* Dialog ditutup (tombol "Transaksi baru", Esc, atau tombol kembali HP): siap transaksi berikutnya. */
  ui.done.addEventListener("close", function () { ui.search.focus(); });

  /* ---------- Mulai ---------- */
  restore();
  renderCats();
  renderGrid();
  renderCart();
  app.classList.add("ready");
})();
