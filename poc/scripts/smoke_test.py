"""Smoke test: validates the POC environment without running heavy ML.

Checks (in order):
  1. python version
  2. docker present
  3. project layout intact
  4. (if container running) TorchServe /ping
  5. (if container running) drawn_humanoid_detector model registered
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    results: list[bool] = []

    results.append(check(
        "python >= 3.9",
        sys.version_info >= (3, 9),
        f"running {sys.version.split()[0]}",
    ))

    docker = shutil.which("docker")
    results.append(check("docker installed", docker is not None, docker or "not found"))

    expected = [
        "docker-compose.yml",
        "docker/Dockerfile",
        "src/pipeline.py",
        "src/tracks/animated_drawings.py",
    ]
    missing = [p for p in expected if not (ROOT / p).exists()]
    results.append(check(
        "project layout intact",
        not missing,
        ("missing: " + ", ".join(missing)) if missing else "all files present",
    ))

    container_running = False
    if docker:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", "memory-app-ad"],
            capture_output=True, text=True,
        )
        container_running = result.returncode == 0 and result.stdout.strip() == "true"

    if not container_running:
        print("[SKIP] live checks (container not running — run `docker compose up -d` first)")
    else:
        try:
            with urllib.request.urlopen("http://localhost:8080/ping", timeout=5) as r:
                body = r.read().decode()
            results.append(check("torchserve /ping", '"Healthy"' in body, body.strip()))
        except urllib.error.URLError as e:
            results.append(check("torchserve /ping", False, str(e)))

        try:
            with urllib.request.urlopen("http://localhost:8081/models", timeout=5) as r:
                models_body = r.read().decode()
            ok = "drawn_humanoid_detector" in models_body
            results.append(check("detector model registered", ok))
        except urllib.error.URLError as e:
            results.append(check("detector model registered", False, str(e)))

    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
