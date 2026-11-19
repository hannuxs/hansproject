/* Struk: tombol "Cetak struk" dan cetak otomatis bila dibuka dengan ?cetak=1 (dari layar kasir). */
(function () {
  "use strict";
  var btn = document.querySelector("[data-print]");
  if (btn) btn.addEventListener("click", function () { window.print(); });
  if (/[?&]cetak=1(?:&|$)/.test(location.search)) {
    window.addEventListener("load", function () { setTimeout(function () { window.print(); }, 250); });
  }
})();
