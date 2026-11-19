"""Membuat file konfigurasi WinSW dari templat (dipanggil service-install.bat).

    python scripts/make_service_xml.py web   <file-xml-tujuan> [service-mariadb]
    python scripts/make_service_xml.py caddy <file-xml-tujuan>
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr  # nosec B406 - hanya meng-escape teks saat MENULIS XML, tidak mem-parse

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "deploy" / "winsw" / "service.xml.template"


def build(kind: str, depends_on: str = "") -> str:
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    if kind == "web":
        values = {
            "id": "hansproject-web",
            "name": "HANS Project - Website",
            "description": "Website hansproject.app (Django + Waitress, hanya 127.0.0.1)",
            "executable": str(python),
            "arguments": f'"{ROOT / "manage.py"}" serve',
            "env": '<env name="PYTHONUTF8" value="1"/>',
        }
    elif kind == "caddy":
        caddy_dir = ROOT / "tools" / "caddy"
        values = {
            "id": "hansproject-caddy",
            "name": "HANS Project - Caddy (HTTPS)",
            "description": "Reverse proxy HTTPS untuk hansproject.app",
            "executable": str(caddy_dir / "caddy.exe"),
            "arguments": f'run --config "{ROOT / "deploy" / "caddy" / "Caddyfile"}" --adapter caddyfile',
            "env": f'<env name="XDG_DATA_HOME" value={quoteattr(str(caddy_dir / "data"))}/>'
                   f'<env name="XDG_CONFIG_HOME" value={quoteattr(str(caddy_dir / "config"))}/>',
        }
        depends_on = "hansproject-web"
    else:
        raise SystemExit("Jenis service harus 'web' atau 'caddy'.")

    out = {k: v if k == "env" else escape(v) for k, v in values.items()}
    out["workdir"] = escape(str(ROOT))
    out["logdir"] = escape(str(ROOT / "logs" / "service"))
    out["depends"] = f"<depend>{escape(depends_on)}</depend>" if depends_on else ""
    return TEMPLATE.read_text(encoding="utf-8").format(**out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    kind, target = argv[0], Path(argv[1])
    depends = argv[2] if len(argv) > 2 else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build(kind, depends), encoding="utf-8")
    print(f"[OK] Konfigurasi service dibuat: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
