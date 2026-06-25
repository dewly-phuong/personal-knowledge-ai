"""
Markdown and HTML report builders for eval results.
Kept separate from generate_report.py to stay under 200 lines per file.
"""

from collections import defaultdict

WARN_THRESHOLD = 0.80


# ── Helpers ───────────────────────────────────────────────────────────────────


def avg(lst):
    return sum(lst) / len(lst) if lst else 0.0


def bar(score, width=8):
    f = round(score * width)
    return "█" * f + "░" * (width - f)


def icon(ok):
    return "✅" if ok else "❌"


def short(text, n=120):
    if not text:
        return ""
    text = text.replace("|", "│").replace("\n", " ").strip()
    return text[:n] + "…" if len(text) > n else text


def score_color(score: float) -> str:
    if score >= 0.8:
        return "#22c55e"
    if score >= 0.6:
        return "#f59e0b"
    return "#ef4444"


def aggregate(records: list[dict]) -> dict:
    """Compute per-metric pass/fail stats across records."""
    stats = defaultdict(lambda: {"passed": 0, "total": 0, "scores": []})
    for r in records:
        for m in r["metrics"]:
            s = stats[m["name"]]
            s["total"] += 1
            s["passed"] += int(m["passed"])
            s["scores"].append(m["score"])
    return dict(stats)


# ── Markdown ──────────────────────────────────────────────────────────────────


def build_markdown(
    single: list[dict],
    multi: list[dict],
    generated_at: str,
    conversation: list[dict] | None = None,
    parallel: list[dict] | None = None,
    diagnostics: dict | None = None,
) -> str:
    sections = [
        (single, "Single-turn"),
        (multi, "Multi-turn"),
        (conversation or [], "Unified conversation"),
        (parallel or [], "Parallel function calling"),
    ]
    all_records = [record for records, _ in sections for record in records]
    n_tests = len(all_records)
    n_passed = sum(1 for r in all_records if r["passed"])
    overall = n_passed / n_tests if n_tests else 0

    lines = [
        "# Eval report",
        "",
        f"**Create at:** {generated_at}  ",
        f"**Tổng tests:** {n_passed}/{n_tests} passed ({overall:.0%})  ",
        "",
    ]
    if diagnostics:
        lines.extend(_diagnostic_lines(diagnostics))

    for records, title in sections:
        if not records:
            continue
        n = len(records)
        np_ = sum(1 for r in records if r["passed"])
        stats = aggregate(records)

        lines += [
            "---",
            "",
            f"## {title} — {np_}/{n} passed ({np_ / n:.0%})",
            "",
            "### Tổng hợp theo metric",
            "",
            "| Metric | Avg | Pass rate | Trạng thái |",
            "|--------|-----|-----------|------------|",
        ]
        for name, s in sorted(stats.items()):
            a = avg(s["scores"])
            rate = s["passed"] / s["total"]
            flag = "🟢 OK" if rate >= WARN_THRESHOLD else "🔴 Cần xem lại"
            lines.append(
                f"| {name} | {bar(a)} {a:.2f} "
                f"| {s['passed']}/{s['total']} ({rate:.0%}) | {flag} |"
            )

        lines += ["", "### Chi tiết từng test case", ""]
        for r in records:
            status = icon(r["passed"])
            header = f"#### {status} {r['id']}  `{r['duration']:.1f}s`"
            if r.get("input"):
                header += f"\n\n> **Input:** {short(r['input'], 100)}"
            lines.append(header)
            summary = r.get("summary") or {}
            if summary:
                turn_avg = summary.get("turn_average_score")
                conv_score = summary.get("conversation_score")
                if turn_avg is not None or conv_score is not None:
                    parts = []
                    if turn_avg is not None:
                        parts.append(f"Average turn score: **{float(turn_avg):.2f}**")
                    if conv_score is not None:
                        parts.append(f"Conversation score: **{float(conv_score):.2f}**")
                    lines.append("")
                    lines.append(" | ".join(parts))
            lines.append("")
            lines.append("| Metric | Score | Threshold | Pass | Lý do |")
            lines.append("|--------|-------|-----------|------|-------|")
            for m in r["metrics"]:
                lines.append(
                    f"| {m['name']} | {m['score']:.2f} "
                    f"| {m['threshold']} | {icon(m['passed'])} "
                    f"| {short(m['reason'], 100)} |"
                )
            lines.append("")

        failed_metrics = [
            (r["id"], m) for r in records for m in r["metrics"] if not m["passed"]
        ]
        if failed_metrics:
            lines += [
                f"### Metrics cần điều tra ({len(failed_metrics)} lần fail)",
                "",
                "| Test | Metric | Score | Lý do |",
                "|------|--------|-------|-------|",
            ]
            for tid, m in failed_metrics:
                lines.append(
                    f"| {tid} | {m['name']} | {m['score']:.2f} "
                    f"| {short(m['reason'], 110)} |"
                )
            lines.append("")

    return "\n".join(lines)


def _diagnostic_lines(diagnostics: dict) -> list[str]:
    lines = [
        "## Diagnostic summary",
        "",
        "### Failure modes",
        "",
    ]
    lines.extend(_counter_lines(diagnostics.get("failure_modes") or {}))
    lines.extend(["", "### Improvement targets", ""])
    lines.extend(_counter_lines(diagnostics.get("targets") or {}))
    lines.extend(["", "### Tool usage", ""])
    lines.extend(_counter_lines(diagnostics.get("tools") or {}))
    lines.extend(["", "### Collections", ""])
    lines.extend(_counter_lines(diagnostics.get("collections") or {}))
    lines.extend(["", "### Failure details", ""])
    lines.extend(_failed_case_lines(diagnostics.get("failed_cases") or []))
    lines.append("")
    return lines


def _counter_lines(values: dict[str, int]) -> list[str]:
    if not values:
        return ["Không có failure mode được ghi nhận."]
    lines = ["| Name | Count |", "|------|-------|"]
    for name, count in sorted(values.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {name} | {count} |")
    return lines


def _failed_case_lines(cases: list[dict]) -> list[str]:
    if not cases:
        return ["Không có failed trace để phân tích."]

    lines: list[str] = []
    for case in cases:
        lines.extend(
            [
                f"#### {case.get('id') or '<unknown>'}",
                "",
                f"- Question: {short(case.get('question'), 180)}",
                "- Failure modes: "
                + _join_or_none(case.get("failure_modes") or []),
                "- Improvement targets: "
                + _join_or_none(case.get("targets") or []),
                f"- Suggested fix: {case.get('suggested_fix') or 'Inspect trace.'}",
            ]
        )
        batches = case.get("tool_batches") or []
        if batches:
            lines.append("- Tool batches:")
            for index, batch in enumerate(batches, start=1):
                lines.append(f"  - Batch {index}: {', '.join(batch)}")
        outputs = case.get("tool_outputs") or []
        if outputs:
            lines.append("- Tool outputs:")
            for output in outputs:
                lines.append(f"  - {short(output, 180)}")
        final_answer = case.get("final_answer")
        if final_answer:
            lines.append(f"- Final answer: {short(final_answer, 220)}")
        lines.append("")
    return lines


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def build_html(
    single: list[dict],
    multi: list[dict],
    generated_at: str,
    conversation: list[dict] | None = None,
    parallel: list[dict] | None = None,
    diagnostics: dict | None = None,
) -> str:
    from eval._html_report import build_html as _build_html

    return _build_html(
        single,
        multi,
        generated_at,
        conversation or [],
        parallel or [],
        diagnostics=diagnostics,
    )
