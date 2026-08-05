"""Package the PyInstaller build into a distributable release artifact.

Usage:
    python packaging/package.py --version 1.0.0

Produces (under dist/):
  Windows: dist/WPTLDR-Setup-<ver>.exe      (Inno Setup, if ISCC.exe found)
           dist/WPTLDR-windows-x64-<ver>.zip (fallback)
  macOS:   dist/WPTLDR-macos-arm64-<ver>.zip
"""

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGING = ROOT / "packaging"


def _win64_zip(version: str) -> Path:
    out = DIST / f"WPTLDR-windows-x64-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted((DIST / "WPTLDR").rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(DIST))
    return out


def _macos_zip(version: str) -> Path:
    app = DIST / "WPTLDR.app"
    if not app.exists():
        raise SystemExit(f"missing {app} — run PyInstaller on macOS first")
    out = DIST / f"WPTLDR-macos-arm64-{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(app.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(DIST))
    return out


def _find_iscc() -> Path | None:
    for cand in (
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ):
        if cand.exists():
            return cand
    return shutil.which("ISCC.exe")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args()
    version = args.version

    if sys.platform.startswith("win"):
        iscc = _find_iscc()
        if iscc:
            out = DIST / f"WPTLDR-Setup-{version}.exe"
            subprocess.run(
                [str(iscc), str(PACKAGING / "WPTLDR.iss"),
                 f"/DMyAppVersion={version}"],
                check=True,
            )
            if not out.exists():
                raise SystemExit(f"installer not produced at {out}")
            artifact = out
        else:
            artifact = _win64_zip(version)
    elif sys.platform == "darwin":
        artifact = _macos_zip(version)
    else:
        raise SystemExit(f"unsupported platform: {sys.platform}")

    print(f"artifact: {artifact} ({artifact.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
