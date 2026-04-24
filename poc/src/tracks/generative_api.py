"""Track B: generative image-to-video API (fal.ai gateway, Kling backend).

Used as a *comparison* track in the POC. Not the main path because:
  - cost scales per generation (~$0.05–$0.40 / second of output)
  - non-deterministic; the same drawing yields a different motion each run,
    which breaks the app's "this is *our* character living in our house"
    consistency requirement
  - typical max length is 5–10s, no looping primitive

Useful for: "first time the drawing wakes up" cinematic moments,
or for non-humanoid drawings (animals, vehicles, abstract shapes) that
Animated Drawings can't rig.
"""

from __future__ import annotations

import base64
import os
import time
import urllib.request
from pathlib import Path

# Lazy import so the rest of the POC works without the fal client installed.
def _client():
    try:
        import fal_client  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "fal_client not installed. run: pip install fal-client"
        ) from e
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY environment variable not set.")
    return fal_client


def animate(
    image_path: Path,
    output_dir: Path,
    prompt: str = "the character in the drawing comes alive, gentle bouncing motion, transparent background",
    model: str = "fal-ai/kling-video/v2/standard/image-to-video",
    duration_seconds: int = 5,
) -> Path:
    fal = _client()

    image_b64 = base64.b64encode(image_path.read_bytes()).decode()
    image_data_url = f"data:image/png;base64,{image_b64}"

    print(f"submitting to {model} ...")
    handler = fal.submit(
        model,
        arguments={
            "image_url": image_data_url,
            "prompt": prompt,
            "duration": str(duration_seconds),
        },
    )

    # Poll until ready.
    started = time.time()
    while True:
        status = handler.status(with_logs=False)
        if status.__class__.__name__ == "Completed":
            break
        if time.time() - started > 600:
            raise RuntimeError("generation timed out after 10min")
        time.sleep(5)

    result = handler.get()
    video_url = result["video"]["url"]

    out_path = output_dir / f"{image_path.stem}.mp4"
    urllib.request.urlretrieve(video_url, out_path)
    return out_path
