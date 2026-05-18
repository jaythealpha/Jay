"""OrcaSlicer CLI 래퍼.

OrcaSlicer는 헤드리스 슬라이싱을 지원:
    orca-slicer --load-settings "machine.json;process.json" \
                --slice 0 --export-3mf out.3mf model.stl

macOS 기본 경로:
    /Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer

실제 인자 문법은 OrcaSlicer 버전마다 다를 수 있어 settings.yaml에서
바이너리 경로·인자 템플릿을 오버라이드 가능하게 설계.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

MACOS_DEFAULT = "/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer"


class SlicerNotFound(RuntimeError):
    pass


class SlicingFailed(RuntimeError):
    pass


@dataclass
class SliceResult:
    output_3mf: Path
    stdout: str
    profile: str


def _resolve_binary(explicit: str | None) -> str:
    if explicit and Path(explicit).exists():
        return explicit
    if Path(MACOS_DEFAULT).exists():
        return MACOS_DEFAULT
    found = shutil.which("orca-slicer") or shutil.which("orcaslicer") or shutil.which("OrcaSlicer")
    if found:
        return found
    raise SlicerNotFound(
        "OrcaSlicer 실행 파일을 찾을 수 없음. macOS면 `brew install --cask orcaslicer`, "
        "또는 settings.yaml의 slicer.binary_path 지정."
    )


class OrcaSlicer:
    def __init__(self, binary_path: str | None = None, profile_dir: Path | None = None) -> None:
        self.binary = _resolve_binary(binary_path)
        self.profile_dir = profile_dir or Path("config/slicer_profiles")

    def slice(
        self,
        model_stl: Path,
        profile: str,
        out_dir: Path,
        timeout_sec: int = 300,
    ) -> SliceResult:
        """STL을 프로파일로 슬라이싱해서 .gcode.3mf 생성.

        프로파일은 scripts/build_profiles.py가 생성한 3종 사용:
          {profile}.machine.json / .process.json / .filament.json
        """
        machine = self.profile_dir / f"{profile}.machine.json"
        process = self.profile_dir / f"{profile}.process.json"
        filament = self.profile_dir / f"{profile}.filament.json"
        missing = [p.name for p in (machine, process, filament) if not p.exists()]
        if missing:
            raise SlicingFailed(
                f"슬라이서 프로파일 없음: {missing} (dir={self.profile_dir}). "
                f"맥에서 `uv run python scripts/build_profiles.py` 실행 필요."
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        out_3mf = out_dir / f"{model_stl.stem}.gcode.3mf"

        cmd = [
            self.binary,
            "--debug", "5",            # 최대 상세 로그 (호환성 비교 대상 확인)
            "--load-settings", f"{machine};{process}",
            "--load-filaments", str(filament),
            "--allow-newer-file",
            "--arrange", "1",
            "--orient", "1",
            "--slice", "0",
            "--export-3mf", str(out_3mf),
            str(model_stl),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_sec, check=False
            )
        except subprocess.TimeoutExpired as e:
            raise SlicingFailed(f"슬라이싱 타임아웃 ({timeout_sec}s)") from e

        if proc.returncode != 0 or not out_3mf.exists():
            blob = proc.stdout + "\n" + proc.stderr
            hints = [ln for ln in blob.splitlines()
                     if any(k in ln.lower() for k in
                            ("compatible", "error", "not found", "invalid",
                             "unsupported", "fail", "preset", "load_config",
                             "printer name", "process name"))]
            hint_txt = "\n".join(hints[-30:]) if hints else "(키워드 매칭 없음)"
            raise SlicingFailed(
                f"OrcaSlicer 실패 (rc={proc.returncode}).\n"
                f"--- 관련 로그 ---\n{hint_txt}\n"
                f"--- stdout tail ---\n{proc.stdout[-800:]}\n"
                f"--- stderr tail ---\n{proc.stderr[-800:]}"
            )
        return SliceResult(output_3mf=out_3mf, stdout=proc.stdout, profile=profile)
