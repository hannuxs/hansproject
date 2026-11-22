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
