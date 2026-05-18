"""bambu-auto CLI.

Phase 1 명령:
    bambu-auto init              # DB 초기화 + 환경 점검
    bambu-auto credits           # 현재 크레딧 사용량
    bambu-auto budget set        # 한도 변경 (config 파일 직접 수정 권장)
    bambu-auto doctor            # 환경/설정 헬스체크

Phase 2+ 명령 (스텁):
    bambu-auto submit IMAGE.jpg [--material pla] [--printer auto]
    bambu-auto status JOB_ID
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from bambu_auto.config import AppConfig
from bambu_auto.services.meshy.credits import CreditGuard
from bambu_auto.storage.db import Database

app = typer.Typer(help="Bambu Lab 3D print productization pipeline")
console = Console()


def _bootstrap() -> tuple[AppConfig, Database, CreditGuard]:
    cfg = AppConfig.load()
    db = Database(cfg.settings.storage.db_path)
    guard = CreditGuard(db, cfg.budgets)
    return cfg, db, guard


@app.command()
def init() -> None:
    """DB 초기화 + 데이터 디렉토리 생성."""
    cfg, db, _ = _bootstrap()
    data_dir = Path(cfg.settings.storage.data_dir)
    (data_dir / "assets").mkdir(parents=True, exist_ok=True)
    console.print(f"[green]OK[/green] DB ready at {db.path}")
    console.print(f"[green]OK[/green] Asset dir at {data_dir / 'assets'}")


@app.command()
def credits() -> None:
    """Meshy 크레딧 사용량 표시."""
    _, _, guard = _bootstrap()
    u = guard.usage()

    t = Table(title="Meshy 크레딧 사용량", show_header=True)
    t.add_column("항목", style="cyan")
    t.add_column("값", justify="right")

    t.add_row("월간 사용 (committed)", f"{u.monthly_used} crd")
    t.add_row("월간 예약 (reserved)", f"{u.reserved_now} crd")
    t.add_row("월간 한도", f"{u.monthly_cap} crd")
    t.add_row("월간 잔여", f"[bold]{u.monthly_remaining} crd[/bold]")
    t.add_row("월간 사용률", f"{u.monthly_ratio:.0%}")
    t.add_row("일간 사용", f"{u.daily_used} / {u.daily_cap} crd")
    console.print(t)

    for alert in guard.check_alerts():
        console.print(f"[yellow]⚠ {alert}[/yellow]")


@app.command()
def doctor() -> None:
    """환경/설정 헬스체크. 어떤 항목이 빠졌는지 알려줌."""
    cfg, db, _ = _bootstrap()
    ok = lambda msg: console.print(f"[green]✓[/green] {msg}")
    warn = lambda msg: console.print(f"[yellow]⚠[/yellow] {msg}")
    fail = lambda msg: console.print(f"[red]✗[/red] {msg}")

    # DB
    ok(f"DB at {db.path}")

    # Secrets
    key = cfg.secrets.meshy_api_key
    if not key:
        fail("MESHY_API_KEY missing (set in .env)")
    elif key.startswith("msy_your_") or key == "your_key_here" or "_here" in key:
        fail(f"MESHY_API_KEY looks like a placeholder ({key!r}). Replace in .env")
    elif not key.startswith("msy_"):
        warn(f"MESHY_API_KEY format unexpected (expected msy_*, got {key[:6]!r}...)")
    else:
        ok(f"MESHY_API_KEY set ({key[:8]}…{key[-4:]})")

    # Printers
    for name, p in cfg.printers.printers.items():
        if p.host and p.access_code:
            ok(f"Printer {name} ({p.model}) configured: {p.host}")
        else:
            warn(f"Printer {name} ({p.model}) host/access_code empty")

    # Operation costs sanity
    required = ["image_to_3d_untextured", "image_to_3d_textured", "text_to_3d_preview"]
    for op in required:
        if op in cfg.budgets.operation_costs:
            ok(f"Cost defined: {op} = {cfg.budgets.operation_costs[op]} crd")
        else:
            fail(f"Cost missing: {op} (add to budgets.yaml)")


@app.command()
def submit(
    source: str = typer.Argument(..., help="image path/URL or text prompt"),
    source_type: str = typer.Option("image", help="image | multi_image | web_url | text"),
    material: str = typer.Option("pla"),
    quality: str = typer.Option("standard"),
    printer: str = typer.Option("auto", help="auto | p2s | a1"),
    run: bool = typer.Option(False, "--run", help="제출 후 즉시 파이프라인 실행"),
) -> None:
    """작업 제출. --run 주면 즉시 파이프라인 실행 (Meshy 호출은 인터넷 필요)."""
    from bambu_auto.core.job import Job, SourceType
    from bambu_auto.core.repository import JobRepository

    cfg, db, _ = _bootstrap()
    job = Job(
        source_type=SourceType(source_type),
        source_payload={"source": source},
        material=material,
        quality=quality,
        target_printer=None if printer == "auto" else printer,
    )
    JobRepository(db).save(job)
    console.print(f"[green]Queued[/green] job {job.id} (state={job.state.value})")
    if run:
        _run_job(cfg, db, job.id)


def _run_job(cfg: AppConfig, db: Database, job_id: str) -> None:
    """파이프라인 실행. Meshy/슬라이서 실제 의존성 연결."""
    import json

    from bambu_auto.adapters.sources.image import ImageSourceAdapter
    from bambu_auto.core.job import Job, SourceType
    from bambu_auto.core.pipeline import Pipeline
    from bambu_auto.core.repository import JobRepository
    from bambu_auto.services.meshy.client import MeshyClient
    from bambu_auto.services.meshy.credits import CreditGuard
    from bambu_auto.services.slicer.orca import OrcaSlicer

    repo = JobRepository(db)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        console.print(f"[red]Job {job_id} not found[/red]")
        raise typer.Exit(1)

    job = Job(
        id=row["id"],
        source_type=SourceType(row["source_type"]),
        source_payload=json.loads(row["source_payload"]),
        material=row["material"],
        quality=row["quality"],
        target_printer=row["target_printer"],
    )

    guard = CreditGuard(db, cfg.budgets)
    meshy = MeshyClient(cfg.secrets.meshy_api_key, cfg.settings.meshy, guard)
    try:
        slicer = OrcaSlicer()
    except Exception as e:
        console.print(f"[yellow]⚠ OrcaSlicer 미준비: {e}[/yellow]")
        console.print("[dim]슬라이싱 전 단계까지만 실행됩니다.[/dim]")
        slicer = None  # type: ignore

    if job.source_type != SourceType.IMAGE:
        console.print("[red]Phase 2는 image 소스만 지원[/red]")
        raise typer.Exit(1)

    adapter = ImageSourceAdapter(job.source_payload["source"])
    pipe = Pipeline(cfg, repo, meshy, slicer)
    try:
        pipe.run(job, adapter)
        console.print(f"[green]Done[/green] {job.id} -> {job.state.value}")
        if job.gcode_path:
            console.print(f"  G-code: {job.gcode_path}")
    except Exception as e:
        console.print(f"[red]Failed[/red] {job.id} at {job.state.value}: {e}")
        raise typer.Exit(1)
    finally:
        meshy.close()


@app.command()
def process(job_id: str) -> None:
    """기존 NEW 작업을 파이프라인에 태움 (재개 포함)."""
    cfg, db, _ = _bootstrap()
    _run_job(cfg, db, job_id)


@app.command(name="list")
def list_jobs(limit: int = 20) -> None:
    """최근 작업 목록."""
    _, db, _ = _bootstrap()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id, state, source_type, material, target_printer, created_at "
            "FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    t = Table(title=f"Recent jobs (last {limit})")
    for col in ["id", "state", "source", "material", "printer", "created"]:
        t.add_column(col)
    for r in rows:
        t.add_row(r["id"], r["state"], r["source_type"], r["material"],
                  r["target_printer"] or "auto", r["created_at"][:19])
    console.print(t)


if __name__ == "__main__":
    app()
