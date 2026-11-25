"""Periksa mesin pembaca foto KK/KTP (dipanggil pasang-ocr.bat).

Keluar dengan kode:
  0 = PaddleOCR siap dan (bila diminta "--gpu") benar-benar berjalan di GPU NVIDIA
  1 = PaddleOCR siap tetapi hanya CPU (pada mode --gpu: GPU tidak bisa dipakai)
  2 = PaddleOCR tidak bisa dimuat
"""
from __future__ import annotations

import sys
import time


def main() -> int:
    want_gpu = "--gpu" in sys.argv
    try:
        import numpy as np
        import onnxruntime as ort
        from rapidocr_onnxruntime import RapidOCR
    except (ImportError, OSError) as exc:
        print(f"      PaddleOCR tidak bisa dimuat: {exc}")
        return 2
    if want_gpu:
        if "CUDAExecutionProvider" not in ort.get_available_providers():
            print("      Paket GPU tidak aktif.")
            return 1
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
        engine = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
    else:
        engine = RapidOCR()
    image = np.full((400, 1200, 3), 255, np.uint8)
    start = time.time()
    engine(image)
    providers = engine.text_det.infer.session.get_providers()
    on_gpu = providers[:1] == ["CUDAExecutionProvider"]
    print(f"      PaddleOCR siap: {'GPU NVIDIA (CUDA)' if on_gpu else 'CPU'} ({time.time() - start:.1f} detik pemanasan).")
    return 0 if (on_gpu or not want_gpu) else 1


if __name__ == "__main__":
    sys.exit(main())
