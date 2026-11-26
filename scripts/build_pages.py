"""Assemble the self-contained GitHub Pages site in a new output directory."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

# Exact npm archives, verified against each release's published integrity hash.
PACKAGES = {
    "ort": (
        "onnxruntime-web/-/onnxruntime-web-1.20.1.tgz",
        "TePF6XVpLL1rWVMIl5Y9ACBQcyCNFThZON/jgElNd9Txb73CIEGlklhYR3UEr1cp5r0rbGI6nDwwrs79g7WjoA==",
        ["dist/ort.wasm.min.js", "dist/ort-wasm-simd-threaded.mjs",
         "dist/ort-wasm-simd-threaded.wasm"],
    ),
    "pyodide": (
        "pyodide/-/pyodide-0.26.4.tgz",
        "z2CHsjVlhhJi5tYBF0AYAfNEPo3zq/z+xOpFtk1tweJkRaTqU4UK/7pLvo8DBU2VDPH31vB3pSI+8fnoqrVrFg==",
        ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm",
         "pyodide-lock.json", "python_stdlib.zip"],
    ),
    "espeak": (
        "@spelling-creator/spellophone/-/spellophone-0.2.1.tgz",
        "VIqceoh9+mdm63S2pY1FGGVH5nateiLZY0PoD+ADFqKWl+zYLnY13zeywVDzc/w+hv9uLTItSC96sHbHBiNPtA==",
        ["dist/browser.js", "dist/core-w4y-vCu9.js", "wasm/espeak-ng.js",
         "wasm/espeak-ng.wasm", "espeak-ng-data/manifest.json",
         "espeak-ng-data/core.bin.gz", "espeak-ng-data/en_dict.gz", "LICENSE"],
    ),
}
WHEELS = {
    "b9/7b/4cabc76fcc21c3c7d5c671d8783984d30ac9d3bb387c4ba784fca3cdfa3a/pypinyin-0.55.0-py2.py3-none-any.whl":
        "d53b1e8ad2cdb815fb2cb604ed3123372f5a28c6f447571244aca36fc62a286f",
    "d6/5b/545e9267a1cc080c8a1be2746113a063e34bcdd0f5173fd665a5c13cb234/num2words-0.5.14-py3-none-any.whl":
        "1c8e5b00142fc2966fd8d685001e36c4a9911e070d1b120e1beb721fa1edb33d",
}


def download(url, path, algorithm, digest):
    if not path.exists() or hashlib.new(algorithm, path.read_bytes()).digest() != digest:
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                        "--retry", "3", "--max-time", "180", url, "-o", str(path)], check=True)
    if hashlib.new(algorithm, path.read_bytes()).digest() != digest:
        raise ValueError(f"Checksum mismatch: {url}")


def build(site, downloads):
    site.mkdir(parents=True, exist_ok=True)
    if any(site.iterdir()):
        raise ValueError(f"Use an empty output directory: {site}")
    for name in ["index.html", "app.js", "worker.js"]:
        shutil.copyfile(WEB / name, site / name)
    assets = site / "assets"
    shutil.copytree(WEB / "assets", assets)
    for name, (package, checksum, files) in PACKAGES.items():
        archive = downloads / (name + ".tgz")
        download("https://registry.npmjs.org/" + package, archive, "sha512", base64.b64decode(checksum))
        with tarfile.open(archive) as tar:
            for member in files:
                target = assets / name / member
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile("package/" + member).read())

    with ZipFile(assets / "frontend.zip", "w", ZIP_DEFLATED) as frontend:
        for name in ("__init__", "config", "text", "zh_text", "en_text"):
            relative = Path("tiny_voca") / (name + ".py")
            frontend.write(ROOT / "src" / relative, str(relative))
        for wheel, digest in WHEELS.items():
            path = downloads / Path(wheel).name
            download("https://files.pythonhosted.org/packages/" + wheel, path, "sha256", bytes.fromhex(digest))
            with ZipFile(path) as package:
                for entry in package.namelist():
                    if not entry.endswith("/"):
                        frontend.writestr(entry, package.read(entry))

    template = (WEB / "sw.js").read_text()
    digest = hashlib.sha256(template.encode())
    sizes = {}
    for path in sorted(site.rglob("*")):
        if path.is_file():
            url = path.relative_to(site).as_posix()
            sizes[url] = path.stat().st_size
            digest.update(url.encode() + hashlib.sha256(path.read_bytes()).digest())
    (site / "sw.js").write_text(template.replace("__VERSION__", digest.hexdigest()[:16])
                                .replace("/* FILE SIZES */ {}", json.dumps(sizes)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--downloads", type=Path, help="Reuse verified package downloads")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        downloads = args.downloads or Path(tmp)
        downloads.mkdir(parents=True, exist_ok=True)
        build(args.output, downloads)
