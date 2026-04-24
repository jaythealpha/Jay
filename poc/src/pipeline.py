"""Memory App POC — entrypoint.

Takes one drawing photo and produces an animated GIF of the character
extracted from it. Two backends:

  --track a   Meta Animated Drawings, running locally via Docker (default)
  --track b   Generative image-to-video API (fal.ai / Kling)

This script is a thin orchestrator. The heavy lifting lives in src/tracks/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Animate a child's drawing into a moving character (POC).",
    )
    parser.add_argument("input", type=Path, help="Path to the drawing photo (JPG/PNG).")
    parser.add_argument("output_dir", type=Path, help="Directory to write video.gif into.")
    parser.add_argument(
        "--track",
        choices=["a", "b"],
        default="a",
        help="a = Animated Drawings (local Docker), b = generative API.",
    )
    parser.add_argument(
        "--motion",
        default="dab",
        help="Track A only: BVH motion preset name (e.g. dab, wave_hello, jumping).",
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8080",
        help="Track A only: TorchServe URL.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.track == "a":
        from tracks.animated_drawings import animate as animate_a

        result = animate_a(
            image_path=args.input,
            output_dir=args.output_dir,
            motion=args.motion,
            server_url=args.server,
        )
    else:
        from tracks.generative_api import animate as animate_b

        result = animate_b(image_path=args.input, output_dir=args.output_dir)

    print(f"done: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
