/* HANS Project — interaksi ringan. Semua konten tetap terbaca tanpa JavaScript. */
(function () {
  "use strict";
  var doc = document.documentElement;
  doc.classList.add("js");

  /* ---------- 0. Penanda login pelanggan (cookie hp_masuk=1, tanpa data rahasia) ----------
     Halaman publik di-cache sama untuk semua orang; tombol "Daftar / Masuk" ditukar
     menjadi "Profil" lewat CSS (.when-guest / .when-member). */
  if (/(?:^|;\s*)hp_masuk=1(?:;|$)/.test(document.cookie)) doc.classList.add("is-member");

  /* Popup persetujuan: <dialog> modal asli yang tidak bisa ditutup sebelum memilih.
     Esc tetap memicu "cancel" di browser tanpa dukungan closedby, jadi dicegah dan dibuka lagi bila tertutup. */
  var consentDialog = document.getElementById("consent-dialog");
  if (consentDialog && typeof consentDialog.showModal === "function") {
    consentDialog.addEventListener("cancel", function (ev) { ev.preventDefault(); });
    consentDialog.addEventListener("close", function () { consentDialog.showModal(); });
    consentDialog.showModal();
  }

  /* Popup persetujuan: tombol "Setuju" aktif setelah kotak dicentang (server tetap memeriksa). */
  var consentCheck = document.querySelector("[data-consent-check]");
  var consentSubmit = document.querySelector("[data-consent-submit]");
  if (consentCheck && consentSubmit) {
    var syncConsent = function () { consentSubmit.disabled = !consentCheck.checked; };
    consentCheck.addEventListener("change", syncConsent);
    syncConsent();
  }

  /* Formulir yang perlu konfirmasi, mis. batalkan pesanan: <form data-confirm="..."> */
  document.addEventListener("submit", function (ev) {
    var msg = ev.target.getAttribute && ev.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) ev.preventDefault();
  });

  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* abaikan */ } }
  };

  function rupiah(n) {
    return "Rp" + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  /* ---------- 1. Saklar "Tampilkan istilah teknis" (bawaan MENYALA, disinkronkan & diingat) ---------- */
  var toggles = Array.prototype.slice.call(document.querySelectorAll(".tech-toggle input"));
  function setTech(on) {
    doc.classList.toggle("hide-tech", !on);
    toggles.forEach(function (t) { t.checked = on; });
  }
  if (toggles.length) {
    setTech(store.get("hp-tech") !== "0");
    toggles.forEach(function (t) {
      t.addEventListener("change", function () {
        setTech(t.checked);
        store.set("hp-tech", t.checked ? "1" : "0");
      });
    });
  }

  /* ---------- 2. Hitung klik tombol kontak, mis. DM Instagram (tanpa data pribadi) ---------- */
  var beaconUrl = doc.getAttribute("data-beacon");
  document.addEventListener("click", function (ev) {
    var link = ev.target.closest && ev.target.closest("a[data-track]");
    if (!link || !beaconUrl || !navigator.sendBeacon) return;
    var data = new FormData();
    data.append("t", link.getAttribute("data-track"));
    try { navigator.sendBeacon(beaconUrl, data); } catch (e) { /* abaikan */ }
  });

  /* ---------- 3. Menu bawah: tandai bagian yang sedang dilihat ---------- */
  var spyLinks = Array.prototype.slice.call(document.querySelectorAll(".bottom-nav [data-spy]"));
  var spyMap = {};
  spyLinks.forEach(function (a) { spyMap[a.getAttribute("data-spy")] = a; });
  var spySections = Object.keys(spyMap).map(function (id) { return document.getElementById(id); }).filter(Boolean);
  if (spySections.length && "IntersectionObserver" in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        spyLinks.forEach(function (a) { a.removeAttribute("aria-current"); });
        spyMap[e.target.id].setAttribute("aria-current", "location");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    spySections.forEach(function (s) { spy.observe(s); });
  }

  /* ---------- 4. Demo kasir di mockup HP ---------- */
  var demo = document.querySelector("[data-pos]");
  if (demo) {
    var cart = {};
    var order = [];
    var cartEl = demo.querySelector("[data-cart]");
    var totalEl = demo.querySelector("[data-total]");
    var payBtn = demo.querySelector("[data-pay]");
    var resetBtn = demo.querySelector("[data-reset]");
    var receiptWrap = demo.querySelector("[data-receipt]");
    var receiptLines = demo.querySelector("[data-receipt-lines]");
    var receiptTotal = demo.querySelector("[data-receipt-total]");
    var receiptTime = demo.querySelector("[data-receipt-time]");
    var live = demo.querySelector("[data-live]");

    var total = function () {
      return order.reduce(function (sum, name) { return sum + cart[name].qty * cart[name].price; }, 0);
    };
    var el = function (tag, cls, text) {
      var n = document.createElement(tag);
      if (cls) n.className = cls;
      if (text != null) n.textContent = text;
      return n;
    };
    var render = function () {
      cartEl.textContent = "";
      if (!order.length) {
        cartEl.appendChild(el("li", "empty", "Ketuk barang di atas untuk menambah"));
      }
      order.forEach(function (name) {
        var item = cart[name];
        var li = el("li");
        var left = el("span", null, name + " ");
        left.appendChild(el("span", "qty", "×" + item.qty));
        li.appendChild(left);
        li.appendChild(el("span", null, rupiah(item.qty * item.price)));
        cartEl.appendChild(li);
      });
      totalEl.textContent = rupiah(total());
      payBtn.disabled = !order.length;
    };
    demo.querySelectorAll("[data-item]").forEach(function (btn) {
      btn.disabled = false;
      btn.addEventListener("click", function () {
        var name = btn.getAttribute("data-name");
        var price = parseInt(btn.getAttribute("data-price"), 10) || 0;
        if (!cart[name]) { cart[name] = { qty: 0, price: price }; order.push(name); }
        cart[name].qty += 1;
        render();
        if (live) live.textContent = name + " ditambahkan. Total " + rupiah(total());
      });
    });
    resetBtn.addEventListener("click", function () { cart = {}; order = []; render(); });
    payBtn.addEventListener("click", function () {
      if (!order.length) return;
      receiptLines.textContent = "";
      order.forEach(function (name) {
        var item = cart[name];
        var row = el("div", "row");
        row.appendChild(el("span", null, item.qty + "× " + name));
        row.appendChild(el("span", null, rupiah(item.qty * item.price)));
        receiptLines.appendChild(row);
      });
      receiptTotal.textContent = rupiah(total());
      var now = new Date();
      receiptTime.textContent = now.toLocaleDateString("id-ID") + " " + now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
      receiptWrap.hidden = false;
      var close = receiptWrap.querySelector("button");
      if (close) close.focus();
    });
    receiptWrap.querySelector("button").addEventListener("click", function () {
      receiptWrap.hidden = true; cart = {}; order = []; render(); payBtn.focus();
    });
    render();
  }

  /* ---------- 5. Kalkulator: berapa toko → paket paling hemat ---------- */
  var calc = document.querySelector("[data-calc]");
  var calcData = document.getElementById("calc-data");
  if (calc && calcData) {
    var cfg;
    try { cfg = JSON.parse(calcData.textContent); } catch (e) { cfg = null; }
    if (cfg && cfg.packages && cfg.packages.length) {
      var input = calc.querySelector("input");
      var out = calc.querySelector("[data-calc-out]");
      var update = function () {
        var n = Math.max(1, Math.min(99, parseInt(input.value, 10) || 1));
        var options = cfg.packages.map(function (p) {
          var extra = Math.max(0, n - p.outlets);
          return { name: p.name, extra: extra, cost: p.price + extra * cfg.outletPrice };
        });
        var best = options.reduce(function (a, b) { return b.cost < a.cost ? b : a; });
        out.textContent = "";
        options.forEach(function (o) {
          var row = el2("div", "calc-row" + (o === best ? " best" : ""));
          var label = "Paket " + o.name + (o.extra ? " + " + o.extra + " toko tambahan" : "");
          row.appendChild(el2("span", null, label));
          row.appendChild(el2("b", null, rupiah(o.cost) + "/bulan"));
          out.appendChild(row);
        });
      };
      var el2 = function (tag, cls, text) {
        var n = document.createElement(tag);
        if (cls) n.className = cls;
        if (text != null) n.textContent = text;
        return n;
      };
      calc.querySelectorAll("[data-step]").forEach(function (b) {
        b.addEventListener("click", function () {
          input.value = Math.max(1, Math.min(99, (parseInt(input.value, 10) || 1) + parseInt(b.getAttribute("data-step"), 10)));
          update();
        });
      });
      input.addEventListener("input", update);
      update();
    }
  }

  /* ---------- 6. Animasi muncul saat di-scroll ---------- */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (r) { io.observe(r); });
  } else {
    reveals.forEach(function (r) { r.classList.add("is-in"); });
  }
})();
