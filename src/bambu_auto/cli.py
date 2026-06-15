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
def balance() -> None:
    """Meshy 서버에서 실제 크레딧 잔액 조회 (API 키 유효성 검증)."""
    from bambu_auto.services.meshy.client import MeshyClient

    cfg, db, guard = _bootstrap()
    client = MeshyClient(cfg.secrets.meshy_api_key, cfg.settings.meshy, guard)
    try:
        data = client.balance()
        console.print("[green]✓ API 키 유효[/green]")
        console.print(data)
    except Exception as e:
        console.print(f"[red]✗ Balance 조회 실패:[/red] {e}")
        raise typer.Exit(1)
    finally:
        client.close()


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

    # Anthropic (CAD 트랙)
    akey = cfg.secrets.anthropic_api_key
    if not akey:
        warn("ANTHROPIC_API_KEY 미설정 — CAD 트랙(파라메트릭) 사용 시 필수")
    elif not akey.startswith("sk-ant-"):
        warn(f"ANTHROPIC_API_KEY 형식 의심 (예상 sk-ant-…, got {akey[:6]!r})")
    else:
        ok(f"ANTHROPIC_API_KEY set ({akey[:10]}…{akey[-4:]})")

    # CAD libs
    try:
        import build123d  # noqa: F401
        ok("build123d (CAD 트랙) 사용 가능")
    except ImportError:
        warn("build123d 미설치 — `uv sync` 필요")

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
    no_bg: bool = typer.Option(False, "--no-bg", help="배경 제거 건너뛰기(rembg)"),
) -> None:
    """작업 제출. --run 주면 즉시 파이프라인 실행 (Meshy 호출은 인터넷 필요)."""
    from bambu_auto.core.job import Job, SourceType
    from bambu_auto.core.repository import JobRepository

    cfg, db, _ = _bootstrap()
    job = Job(
        source_type=SourceType(source_type),
        source_payload={"source": source, "remove_bg": not no_bg},
        material=material,
        quality=quality,
        target_printer=None if printer == "auto" else printer,
    )
    JobRepository(db).save(job)
    console.print(f"[green]Queued[/green] job {job.id} (state={job.state.value})")
    if run:
        _run_job(cfg, db, job.id)


def _run_job(cfg: AppConfig, db: Database, job_id: str) -> None:
    """파이프라인 실행 (CLI 래퍼 — 공용 runner.run_job 사용)."""
    from bambu_auto.core.runner import JobNotFound, run_job

    try:
        job = run_job(cfg, db, job_id,
                      on_progress=lambda m: console.print(f"[cyan]{m}[/cyan]"))
    except JobNotFound:
        console.print(f"[red]Job {job_id} not found[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Failed[/red] {job_id}: {e}")
        raise typer.Exit(1) from e

    console.print(f"[green]Done[/green] {job.id} -> {job.state.value}")
    if job.gcode_path:
        console.print(f"  G-code: {job.gcode_path}")


@app.command()
def cad(
    spec: str = typer.Argument(..., help="자연어 CAD 스펙 (예: 'MX 1u 키캡, A 음각')"),
    material: str = typer.Option("pla"),
    quality: str = typer.Option("standard"),
    printer: str = typer.Option("auto", help="auto | p2s | a1"),
    run: bool = typer.Option(False, "--run", help="제출 후 즉시 파이프라인 실행"),
    model: str = typer.Option(
        "claude-sonnet-4-6", "--model",
        help="Claude 모델 (claude-sonnet-4-6 권장, claude-opus-4-7 정밀)",
    ),
    param: list[str] = typer.Option(
        [], "--param", "-p",
        help="치수 key=value (반복 가능). 예: -p cap_mm=18 -p letter=A",
    ),
    max_attempts: int = typer.Option(3, "--attempts"),
) -> None:
    """CAD 트랙 작업 제출. Claude → build123d → STL → slice.

    Meshy 미사용 → 크레딧 0. 키캡·마운트·박스 같은 규격 부품에 적합.
    """
    from bambu_auto.core.job import Job, SourceType
    from bambu_auto.core.repository import JobRepository

    cfg, db, _ = _bootstrap()
    if not cfg.secrets.anthropic_api_key:
        console.print(
            "[red]ANTHROPIC_API_KEY 누락[/red] — .env에 키를 설정해야 CAD 트랙 사용 가능"
        )
        raise typer.Exit(1)

    params: dict[str, str | float] = {}
    for kv in param:
        if "=" not in kv:
            console.print(f"[yellow]⚠ --param 무시[/yellow] (key=value 형식 아님): {kv}")
            continue
        k, v = kv.split("=", 1)
        try:
            params[k.strip()] = float(v)
        except ValueError:
            params[k.strip()] = v.strip()

    job = Job(
        source_type=SourceType.CAD,
        source_payload={
            "prompt": spec,
            "cad_params": params or None,
            "cad_model": model,
            "cad_max_attempts": max_attempts,
        },
        material=material,
        quality=quality,
        target_printer=None if printer == "auto" else printer,
    )
    JobRepository(db).save(job)
    console.print(
        f"[green]Queued[/green] CAD job {job.id} (model={model}, params={params or '-'})"
    )
    if run:
        _run_job(cfg, db, job.id)


@app.command()
def process(job_id: str) -> None:
    """기존 NEW 작업을 파이프라인에 태움 (재개 포함)."""
    cfg, db, _ = _bootstrap()
    _run_job(cfg, db, job_id)


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    """웹 대시보드 실행. 브라우저에서 제출·다운로드 (CLI 대체)."""
    import uvicorn

    from bambu_auto.web.app import create_app

    cfg = AppConfig.load()
    console.print(f"[green]웹 대시보드[/green] http://{host}:{port}  "
                  f"(같은 네트워크에서 접속 가능)")
    uvicorn.run(create_app(cfg), host=host, port=port, log_level="info")


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
