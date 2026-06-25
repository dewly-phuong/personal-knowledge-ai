"""
generate_report.py

Đọc single_turn_results.json + multi_turn_results.json + conversation_results.json
hoặc scores.jsonl và sinh:
  - reports/report.md   — báo cáo Markdown đầy đủ
  - reports/report.html — báo cáo HTML (mở trình duyệt)

Chạy:
    python generate_report.py \\
        --single single_turn_results.json \\
        --multi  multi_turn_results.json \\
        --conversation conversation_results.json

    # Hoặc chỉ một file:
    python generate_report.py --single single_turn_results.json
    python generate_report.py --scores eval/result/scores.jsonl
"""

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

from litellm import uuid

from eval.diagnostic_report import diagnostic_summary, parse_traces_file
from eval._report_builders import aggregate, avg, build_html, build_markdown


# ── Parse ─────────────────────────────────────────────────────────────────────


def parse_file(path: pathlib.Path, label: str) -> list[dict]:
    """
    Trả về list các test-record chuẩn hóa:
    {
      "id":       "ST001",
      "label":    "single" | "multi",
      "passed":   bool,
      "duration": float,
      "input":    str | None,
      "metrics":  [{"name", "score", "threshold", "passed", "reason"}]
    }
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for r in raw.get("results", []):
        rid = r["id"].split("[")[-1].rstrip("]")
        tc = (r.get("deepeval_test_cases") or [{}])[0]
        metrics_raw = tc.get("metrics_data") or []
        metrics = [
            {
                "name": m["name"],
                "score": float(m.get("score") or 0),
                "threshold": float(m.get("threshold") or 0),
                "passed": bool(m.get("success", False)),
                "reason": (m.get("reason") or "").strip(),
            }
            for m in metrics_raw
        ]
        records.append(
            {
                "id": rid,
                "label": label,
                "passed": r.get("outcome") == "passed",
                "duration": float(r.get("duration_s") or 0),
                "input": _test_case_input(tc),
                "metrics": metrics,
            }
        )
    return records


def parse_scores_file(path: pathlib.Path, run_id: str = "latest") -> dict[str, list[dict]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        return {"single": [], "multi": [], "conversation": [], "parallel": []}

    if run_id == "latest":
        selected_run_id = rows[-1]["run_id"]
        rows = [row for row in rows if row.get("run_id") == selected_run_id]
    elif run_id != "all":
        rows = [row for row in rows if row.get("run_id") == run_id]

    grouped: dict[str, list[dict]] = {
        "single": [],
        "multi": [],
        "conversation": [],
        "parallel": [],
    }
    for row in rows:
        label = _label_from_pytest_file(row.get("file", ""))
        if label not in grouped:
            continue
        grouped[label].append(
            {
                "id": row.get("test_id", ""),
                "label": label,
                "passed": bool(row.get("passed")),
                "duration": float(row.get("duration") or 0),
                "input": row.get("input"),
                "summary": row.get("summary") or {},
                "metrics": [
                    {
                        "name": m.get("name", ""),
                        "score": float(m.get("score") or 0),
                        "threshold": float(m.get("threshold") or 0),
                        "passed": bool(m.get("passed")),
                        "reason": (m.get("reason") or "").strip(),
                    }
                    for m in row.get("metrics", [])
                ],
            }
        )
    return grouped


def _test_case_input(test_case: dict) -> str | None:
    if test_case.get("input"):
        return test_case["input"]
    turns = test_case.get("turns") or []
    for turn in turns:
        if turn.get("role") == "user" and turn.get("content"):
            return turn["content"]
    return None


def _label_from_pytest_file(file_name: str) -> str | None:
    if file_name == "test_single_turn":
        return "single"
    if file_name == "test_multi_turn":
        return "multi"
    if file_name == "test_conversation_dataset":
        return "conversation"
    if file_name == "test_parallel_function_calling":
        return "parallel"
    return None


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", help="Đường dẫn single_turn_results.json")
    ap.add_argument("--multi", help="Đường dẫn multi_turn_results.json")
    ap.add_argument("--conversation", help="Đường dẫn conversation_results.json")
    ap.add_argument("--scores", help="Đường dẫn scores.jsonl từ pytest/conftest")
    ap.add_argument("--traces", help="Đường dẫn traces.jsonl từ pytest/conftest")
    ap.add_argument(
        "--scores-run-id",
        default="latest",
        help="run_id trong scores.jsonl: latest, all, hoặc id cụ thể",
    )
    ap.add_argument(
        "--traces-run-id",
        default="latest",
        help="run_id trong traces.jsonl: latest, all, hoặc id cụ thể",
    )
    ap.add_argument(
        "--out", default="eval/reports", help="Thư mục output (default: reports)"
    )
    args = ap.parse_args()

    if (
        not args.single
        and not args.multi
        and not args.conversation
        and not args.scores
        and not args.traces
    ):
        ap.print_help()
        sys.exit(1)

    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)

    single = parse_file(pathlib.Path(args.single), "single") if args.single else []
    multi = parse_file(pathlib.Path(args.multi), "multi") if args.multi else []
    conversation = (
        parse_file(pathlib.Path(args.conversation), "conversation")
        if args.conversation
        else []
    )

    if args.scores:
        scores = parse_scores_file(pathlib.Path(args.scores), args.scores_run_id)
        single.extend(scores["single"])
        multi.extend(scores["multi"])
        conversation.extend(scores["conversation"])
        parallel = scores["parallel"]
    else:
        parallel = []

    traces = (
        parse_traces_file(pathlib.Path(args.traces), args.traces_run_id)
        if args.traces
        else []
    )

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    rid = uuid.uuid4().hex[:8]

    labels = [
        name
        for name, records in [
            ("single-turn", single),
            ("multi-turn", multi),
            ("conversation", conversation),
            ("parallel-function-calling", parallel),
        ]
        if records
    ]
    subname = "" if len(labels) != 1 else f"-{labels[0]}"

    diagnostics = diagnostic_summary(traces) if traces else {}

    md_path = out / f"report{subname}-{rid}.md"
    html_path = out / f"report{subname}-{rid}.html"

    md_path.write_text(
        build_markdown(
            single,
            multi,
            now,
            conversation,
            parallel=parallel,
            diagnostics=diagnostics,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        build_html(
            single,
            multi,
            now,
            conversation,
            parallel=parallel,
            diagnostics=diagnostics,
        ),
        encoding="utf-8",
    )

    # ── Terminal summary ─────────────────────────────────────────────────────
    all_records = single + multi + conversation + parallel
    n_tests = len(all_records)
    n_passed = sum(1 for r in all_records if r["passed"])
    stats = aggregate(all_records)
    pass_rate = n_passed / n_tests if n_tests else 0

    print(f"\n{'=' * 56}")
    print("  EVAL SUMMARY")
    print(f"{'=' * 56}")
    print(f"  Tests : {n_passed}/{n_tests} passed ({pass_rate:.0%})")
    print(f"{'─' * 56}")
    print(f"  {'Metric':<34} {'Avg':>5}  {'Pass':>8}")
    print(f"{'─' * 56}")
    for name, s in sorted(stats.items()):
        a = avg(s["scores"])
        rate = s["passed"] / s["total"]
        flag = "" if rate >= 0.80 else "  ← xem lại"
        print(f"  {name:<34} {a:>5.2f}  {s['passed']}/{s['total']} ({rate:.0%}){flag}")
    if traces:
        print(f"{'─' * 56}")
        print("  DIAGNOSTIC SUMMARY")
        print(f"{'─' * 56}")
        _print_counter("Failure modes", diagnostics["failure_modes"])
        _print_counter("Improvement targets", diagnostics["targets"])
    print(f"{'=' * 56}")
    print(f"  Markdown : {md_path}")
    print(f"  HTML     : {html_path}")
    print(f"{'=' * 56}\n")


def _print_counter(title: str, values: dict[str, int]) -> None:
    if not values:
        print(f"  {title:<20}: none")
        return
    rendered = ", ".join(
        f"{name}={count}"
        for name, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))
    )
    print(f"  {title:<20}: {rendered}")


if __name__ == "__main__":
    main()
