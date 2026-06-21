import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image


Image.MAX_IMAGE_PIXELS = None


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class PlanImportResult:
    plan_id: str
    success: bool
    stdout: str
    stderr: str


def import_plan_pdf(
    project_root: Path,
    filename: str,
    contents: bytes,
    run_command: RunCommand = subprocess.run,
) -> PlanImportResult:
    if not filename or not filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF files are accepted.")

    import_dir = project_root / "data" / "imports"
    import_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = import_dir / Path(filename).name
    pdf_path.write_bytes(contents)

    plan_id = pdf_path.stem
    script = project_root / "scripts" / "run_pipeline_on_pdfs.py"
    result = run_command(
        [sys.executable, str(script), "--pdf", str(pdf_path)],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )

    publish_rendered_page(project_root, plan_id)
    write_plan_metadata(project_root, plan_id)

    return PlanImportResult(
        plan_id=plan_id,
        success=result.returncode == 0,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def publish_rendered_page(project_root: Path, plan_id: str) -> None:
    rendered_page = project_root / "outputs" / "rendered" / f"{plan_id}.png"
    if not rendered_page.is_file():
        return

    pages_dir = project_root / "data" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rendered_page, pages_dir / rendered_page.name)


def write_plan_metadata(project_root: Path, plan_id: str) -> None:
    page_path = project_root / "data" / "pages" / f"{plan_id}.png"
    if not page_path.is_file():
        return

    with Image.open(page_path) as image:
        width, height = image.size

    metadata_dir = project_root / "data" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f"{plan_id}_metadata.json"

    metadata = {
        "plan_id": plan_id,
        "file_path": f"data/pages/{plan_id}.png",
        "image_width_px": width,
        "image_height_px": height,
        "source_type": "rendered_png",
        "original_pdf_available": (project_root / "data" / "imports" / f"{plan_id}.pdf").is_file(),
        "scale_text_visible": _load_scale_text(project_root, plan_id),
        "contains_red_markups": True,
        "notes": "",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _load_scale_text(project_root: Path, plan_id: str) -> str:
    config_path = project_root / "data" / "config" / f"{plan_id}_config.json"
    if not config_path.is_file():
        return "unknown"

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "unknown"

    scale = config.get("scale")
    return f"M1:{scale}" if scale else "unknown"
