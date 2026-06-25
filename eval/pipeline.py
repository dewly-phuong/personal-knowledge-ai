import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from eval.dataset_manifest import (
    MANIFEST_FILE,
    build_manifest,
    load_manifest,
    sync_adapters,
    validate_manifest,
    write_manifest,
)


DEFAULT_DATASETS_DIR = Path(__file__).parent / "datasets"
DEFAULT_RESULT_DIR = Path(__file__).parent / "result"
DEFAULT_REPORTS_DIR = Path(__file__).parent / "reports"
DEFAULT_RULES = Path(__file__).parent / "configs" / "release-gates.yaml"
CODE_BASED_PYTEST_ARGS = [
    "eval/test_parallel_function_calling.py",
]
LLM_JUDGE_PYTEST_ARGS = [
    "eval/test_single_turn.py",
    "eval/test_multi_turn.py",
    "eval/test_conversation_dataset.py",
]
DEFAULT_PYTEST_ARGS = [*CODE_BASED_PYTEST_ARGS, *LLM_JUDGE_PYTEST_ARGS]


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command.replace("-", "_")
    return globals()[f"_cmd_{command}"](args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluation pipeline CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-dataset")
    _add_dataset_args(build)

    validate = subparsers.add_parser("validate-dataset")
    validate.add_argument("--manifest", default=str(DEFAULT_DATASETS_DIR / MANIFEST_FILE))

    sync = subparsers.add_parser("sync-adapters")
    _add_dataset_args(sync)

    run = subparsers.add_parser("run")
    _add_dataset_args(run)
    run.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    run.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR))
    run.add_argument("--rules", default=str(DEFAULT_RULES))
    run.add_argument("--skip-gate", action="store_true")
    run.add_argument("--pytest-args", nargs="*", default=DEFAULT_PYTEST_ARGS)

    gate = subparsers.add_parser("gate")
    gate.add_argument("--scores", default=str(DEFAULT_RESULT_DIR / "scores.jsonl"))
    gate.add_argument("--rules", default=str(DEFAULT_RULES))
    gate.add_argument("--run-id", default="latest")
    return parser


def _add_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--datasets-dir", default=str(DEFAULT_DATASETS_DIR))
    parser.add_argument("--manifest", default=MANIFEST_FILE)


def _cmd_build_dataset(args: argparse.Namespace) -> int:
    datasets_dir = Path(args.datasets_dir)
    manifest_path = _manifest_path(datasets_dir, args.manifest)
    records = build_manifest(datasets_dir)
    errors = write_manifest(records, manifest_path)
    if errors:
        _print_errors("Dataset manifest invalid", errors)
        return 1
    print(f"Wrote {len(records)} eval cases to {manifest_path}")
    return 0


def _cmd_validate_dataset(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    records = load_manifest(manifest_path)
    errors = validate_manifest(records)
    if errors:
        _print_errors("Dataset manifest invalid", errors)
        return 1
    print(f"Dataset manifest valid: {len(records)} cases")
    return 0


def _cmd_sync_adapters(args: argparse.Namespace) -> int:
    datasets_dir = Path(args.datasets_dir)
    manifest_path = _manifest_path(datasets_dir, args.manifest)
    records = load_manifest(manifest_path)
    try:
        sync_adapters(records, datasets_dir)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Synced adapters from {manifest_path}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    datasets_dir = Path(args.datasets_dir)
    manifest_path = _manifest_path(datasets_dir, args.manifest)
    result_dir = Path(args.result_dir)
    reports_dir = Path(args.reports_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    records = load_manifest(manifest_path)
    errors = validate_manifest(records)
    if errors:
        _print_errors("Dataset manifest invalid", errors)
        return 1

    sync_adapters(records, datasets_dir)
    run_config_path = _freeze_config(result_dir, manifest_path, args.pytest_args)
    print(f"Frozen run config: {run_config_path}")

    for pytest_args in _pytest_phases(args.pytest_args):
        pytest_result = subprocess.run([sys.executable, "-m", "pytest", *pytest_args])
        if pytest_result.returncode != 0:
            return pytest_result.returncode

    report_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.generate_report",
            "--scores",
            str(result_dir / "scores.jsonl"),
            "--traces",
            str(result_dir / "traces.jsonl"),
            "--out",
            str(reports_dir),
        ]
    )
    if report_result.returncode != 0:
        return report_result.returncode

    if args.skip_gate:
        return 0
    return _cmd_gate(
        argparse.Namespace(
            scores=str(result_dir / "scores.jsonl"),
            rules=args.rules,
            run_id="latest",
        )
    )


def _cmd_gate(args: argparse.Namespace) -> int:
    gate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.gate",
            "--scores",
            args.scores,
            "--rules",
            args.rules,
            "--run-id",
            args.run_id,
        ]
    )
    return int(gate_result.returncode)


def _freeze_config(
    result_dir: Path, manifest_path: Path, pytest_args: list[str]
) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = result_dir / f"run_config-{stamp}.json"
    config = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "pytest_args": pytest_args,
        "model": os.getenv("EVAL_MODEL", "app.agent default"),
        "judge_model": os.getenv("EVAL_JUDGE_MODEL", "eval.judge default"),
        "prompt_version": os.getenv("PROMPT_VERSION", "unknown"),
    }
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _pytest_phases(pytest_args: list[str]) -> list[list[str]]:
    if pytest_args == DEFAULT_PYTEST_ARGS:
        return [CODE_BASED_PYTEST_ARGS, LLM_JUDGE_PYTEST_ARGS]
    return [pytest_args]


def _manifest_path(datasets_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() or path.parent != Path(".") else datasets_dir / path


def _print_errors(title: str, errors: list[str]) -> None:
    print(title, file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
