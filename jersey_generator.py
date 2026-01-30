import concurrent.futures
import contextlib
import io
import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

import generate as standard_generator
import curved_generate as curved_generator

try:
    import easygui  # Optional prompt for worker count
except Exception:  # pragma: no cover - GUI module may be unavailable on headless runs
    easygui = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_ROOT = os.path.join(BASE_DIR, "bin")

# Ensure both engines share the same output target so files land together.
standard_generator.OUTPUT_DIR = OUTPUT_DIR
curved_generator.OUTPUT_DIR = OUTPUT_DIR


@dataclass
class RowJob:
    index: int
    row: pd.Series
    order: curved_generator.JerseyOrder
    team_folder: str
    coords: Dict
    use_curved: bool


@dataclass
class JobResult:
    job: RowJob
    pipeline: str
    success: bool
    message: str
    captured_log: str


def select_csv_path() -> Optional[str]:
    path = standard_generator.get_csv_path()
    if not path:
        print("[ERROR] No CSV file selected. Exiting.")
    return path


def read_input_csv(csv_path: str) -> pd.DataFrame:
    df = standard_generator.read_csv_with_fallback(csv_path)
    return df.dropna(how="all")


def prepare_output_dir() -> None:
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def requires_curved_pipeline(coords: Dict) -> bool:
    nameplate = coords.get("NamePlate") or {}
    has_curve = "curve" in nameplate and bool(nameplate["curve"])
    border_keys = ("NumberBorder", "FrontNumberBorder", "BackNumberBorder")
    has_number_border = any(key in coords for key in border_keys)
    return bool(has_curve and has_number_border)


def build_job(index: int, row: pd.Series) -> Optional[RowJob]:
    try:
        order = curved_generator.build_order(row)
    except ValueError as exc:
        print(f"[WARN] Skipping row {index}: {exc}")
        return None

    try:
        team_folder = curved_generator.locate_team_folder(order)
    except FileNotFoundError as exc:
        print(f"[WARN] Skipping row {index}: {exc}")
        return None

    try:
        coords = curved_generator.load_coords_json(team_folder)
    except Exception as exc:
        print(f"[WARN] Skipping row {index}: unable to load coords.json - {exc}")
        return None

    use_curved = requires_curved_pipeline(coords)
    return RowJob(index=index, row=row, order=order, team_folder=team_folder, coords=coords, use_curved=use_curved)


def collect_jobs(df: pd.DataFrame) -> List[RowJob]:
    jobs: List[RowJob] = []
    for idx, row in df.iterrows():
        job = build_job(idx, row)
        if job:
            jobs.append(job)
    return jobs


def is_youth_row(row: pd.Series) -> bool:
    value = str(row.get("Mens or Youth", "")).strip().lower()
    return value == "youth"


def apply_standard_youth_overlays(row: pd.Series, youth_overlay) -> None:
    if youth_overlay is None:
        return
    name_value = str(row.get("Name", "")).strip()
    if not name_value:
        return
    for suffix in ("-1.png", "-2.png", "-3.png"):
        target_path = os.path.join(OUTPUT_DIR, f"{name_value}{suffix}")
        if os.path.exists(target_path):
            standard_generator.apply_overlay_to_file(target_path, youth_overlay)


def process_standard_pipeline(job: RowJob, youth_overlay) -> None:
    standard_generator.process_front(job.row, job.team_folder, job.coords)
    standard_generator.process_back(job.row, job.team_folder, job.coords)
    front_path = os.path.join(OUTPUT_DIR, f"{job.row['Name']}-3.png")
    back_path = os.path.join(OUTPUT_DIR, f"{job.row['Name']}-2.png")
    standard_generator.process_combo(job.row, front_path, back_path)
    if is_youth_row(job.row):
        apply_standard_youth_overlays(job.row, youth_overlay)


def execute_job(job: RowJob, youth_overlay) -> JobResult:
    pipeline_name = "Curved" if job.use_curved else "Standard"
    log_buffer = io.StringIO()
    with contextlib.redirect_stdout(log_buffer):
        try:
            if job.use_curved:
                curved_generator.process_order(job.order, youth_overlay)
            else:
                process_standard_pipeline(job, youth_overlay)
            message = "Completed"
            return JobResult(job=job, pipeline=pipeline_name, success=True, message=message, captured_log=log_buffer.getvalue())
        except Exception as exc:
            return JobResult(
                job=job,
                pipeline=pipeline_name,
                success=False,
                message=str(exc),
                captured_log=log_buffer.getvalue(),
            )


def emit_result(result: JobResult, verbose: bool = False) -> None:
    status = "✓" if result.success else "✗"
    identifier = f"Row {result.job.index} ({result.order.name})"
    print(f"{status} {identifier} – {result.pipeline}: {result.message}")
    if (verbose or not result.success) and result.captured_log.strip():
        print("    └─ Captured output:")
        for line in result.captured_log.strip().splitlines():
            print(f"       {line}")


def resolve_worker_count(job_count: int) -> int:
    job_count = max(1, job_count)
    cpu_default = max(1, os.cpu_count() or 1)
    default_workers = min(cpu_default, job_count)

    env_value = os.environ.get("JERSEY_WORKERS")
    if env_value:
        try:
            env_workers = int(env_value)
            if env_workers > 0:
                return min(env_workers, job_count)
        except ValueError:
            print(f"[WARN] Invalid JERSEY_WORKERS value '{env_value}', falling back to prompt/default.")

    if easygui and job_count > 1:
        user_value = easygui.integerbox(
            "How many worker threads should we use?",
            "Worker Count",
            default=default_workers,
            lowerbound=1,
            upperbound=max(1, job_count),
        )
        if user_value:
            return int(user_value)

    return default_workers


def main() -> None:
    csv_path = select_csv_path()
    if not csv_path:
        return

    df = read_input_csv(csv_path)
    jobs = collect_jobs(df)
    if not jobs:
        print("[ERROR] No valid rows to process. Exiting.")
        return

    prepare_output_dir()
    youth_overlay = curved_generator.load_youth_overlay()
    if youth_overlay is None:
        overlay_path = os.path.join(ASSETS_ROOT, "youth.png")
        if os.path.exists(overlay_path):
            try:
                from PIL import Image

                youth_overlay = Image.open(overlay_path).convert("RGBA")
            except Exception as exc:
                print(f"[WARN] Unable to load youth overlay from fallback path {overlay_path}: {exc}")

    worker_count = resolve_worker_count(len(jobs))
    verbose_logs = os.environ.get("JERSEY_VERBOSE", "0").lower() in {"1", "true", "yes"}

    print(f"Processing {len(jobs)} jobs with {worker_count} thread(s)...")
    results: List[JobResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_job = {executor.submit(execute_job, job, youth_overlay): job for job in jobs}
        for future in concurrent.futures.as_completed(future_to_job):
            result = future.result()
            results.append(result)
            emit_result(result, verbose=verbose_logs)

    standard_total = sum(1 for r in results if not r.job.use_curved)
    curved_total = len(results) - standard_total
    successes = sum(1 for r in results if r.success)
    failures = len(results) - successes

    print("\nRun complete:")
    print(f"  Standard generator rows: {standard_total}")
    print(f"  Curved generator rows:   {curved_total}")
    print(f"  Successful jobs:         {successes}")
    print(f"  Failed jobs:             {failures}")


if __name__ == "__main__":
    main()
