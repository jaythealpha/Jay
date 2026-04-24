"""Track A: Meta Animated Drawings.

Strategy
--------
Meta's project ships a CLI (`image_to_animation.py`) that orchestrates the
whole pipeline (detect → segment → rig → animate) against a TorchServe
instance. The cleanest way to use it from outside the Docker container is to
exec the script *inside* the container with the user's input mounted.

We don't reimplement the pipeline; we shell out. That keeps the wrapper
thin and lets us upgrade the upstream commit without touching this file.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

CONTAINER = "memory-app-ad"
CONTAINER_INPUT = "/workspace/samples"
CONTAINER_OUTPUT = "/workspace/out"


def _ensure_container_running() -> None:
    """Fail fast with a useful message if the docker service isn't up."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise RuntimeError(
            f"container '{CONTAINER}' is not running. "
            "start it with: docker compose up -d"
        )


def animate(
    image_path: Path,
    output_dir: Path,
    motion: str = "dab",
    server_url: str = "http://localhost:8080",
) -> Path:
    """Run the full Animated Drawings pipeline on one image.

    Returns the path to the produced GIF.
    """
    _ensure_container_running()

    # The Animated Drawings repo expects the input image to live somewhere
    # readable inside the container. We mount ./samples and ./out, so we
    # stage the input there.
    host_samples = Path(__file__).resolve().parents[2] / "samples"
    host_out = Path(__file__).resolve().parents[2] / "out"
    host_samples.mkdir(parents=True, exist_ok=True)
    host_out.mkdir(parents=True, exist_ok=True)

    staged = host_samples / image_path.name
    if staged.resolve() != image_path.resolve():
        shutil.copy2(image_path, staged)

    container_in = f"{CONTAINER_INPUT}/{image_path.name}"
    container_out = f"{CONTAINER_OUTPUT}/{image_path.stem}"

    cmd = [
        "docker", "exec", CONTAINER,
        "python", "examples/image_to_animation.py",
        container_in,
        container_out,
        "--motion", motion,
    ]
    print(f"running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    produced = host_out / image_path.stem / "video.gif"
    if not produced.exists():
        raise RuntimeError(f"expected output not found: {produced}")

    final = output_dir / f"{image_path.stem}.gif"
    shutil.copy2(produced, final)
    return final
