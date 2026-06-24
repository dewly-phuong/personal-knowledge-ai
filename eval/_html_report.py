from eval._report_builders import aggregate, avg, score_color, short


def metric_rows_html(records: list[dict]) -> str:
    rows = ""
    for name, stats in sorted(aggregate(records).items()):
        average = avg(stats["scores"])
        rate = stats["passed"] / stats["total"]
        flag = "🟢 OK" if rate >= 0.8 else "🔴 Xem lại"
        rows += (
            f"<tr><td>{name}</td>"
            f"<td><span style='color:{score_color(average)};font-weight:600'>"
            f"{average:.2f}</span></td>"
            f"<td>{stats['passed']}/{stats['total']} ({rate:.0%})</td>"
            f"<td>{flag}</td></tr>"
        )
    return rows


def detail_rows_html(records: list[dict]) -> str:
    html = ""
    for record in records:
        html += _record_detail_html(record)
    return html


def section_html(records: list[dict], title: str) -> str:
    if not records:
        return ""
    passed = sum(1 for record in records if record["passed"])
    total = len(records)
    return f"""
    <section>
      <h2>{title} <span style='color:#6b7280;font-size:16px;font-weight:400'>{passed}/{total} passed ({passed / total:.0%})</span></h2>
      <h3>Tổng hợp theo metric</h3>
      <table><thead><tr><th>Metric</th><th>Avg score</th><th>Pass rate</th><th>Trạng thái</th></tr></thead>
      <tbody>{metric_rows_html(records)}</tbody></table>
      <h3 style='margin-top:20px'>Chi tiết từng test case</h3>
      {detail_rows_html(records)}
    </section>"""


def build_html(
    single: list[dict],
    multi: list[dict],
    generated_at: str,
    conversation: list[dict] | None = None,
) -> str:
    conversation = conversation or []
    all_records = single + multi + conversation
    n_tests = len(all_records)
    n_passed = sum(1 for record in all_records if record["passed"])
    overall = n_passed / n_tests if n_tests else 0
    overall_color = "#22c55e" if overall >= 0.8 else "#ef4444"
    return f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eval report</title><style>{_css()}</style></head><body><div class="container">
  <h1>Eval report</h1><p class="meta">Create at {generated_at}</p>
  <div class="summary-cards">
    <div class="card"><div class="card-val" style="color:{overall_color}">{overall:.0%}</div><div class="card-lbl">Overall pass rate</div></div>
    <div class="card"><div class="card-val">{n_passed}/{n_tests}</div><div class="card-lbl">Tests passed</div></div>
    <div class="card"><div class="card-val">{len(single)}</div><div class="card-lbl">Single-turn</div></div>
    <div class="card"><div class="card-val">{len(multi)}</div><div class="card-lbl">Multi-turn</div></div>
    <div class="card"><div class="card-val">{len(conversation)}</div><div class="card-lbl">Unified conversation</div></div>
  </div>{section_html(single, "Single-turn")}{section_html(multi, "Multi-turn")}{section_html(conversation, "Unified conversation")}
</div></body></html>"""


def _record_detail_html(record: dict) -> str:
    bg = "#f0fdf4" if record["passed"] else "#fef2f2"
    icon = "✅" if record["passed"] else "❌"
    inp = (
        f"<div class='input-text'>→ {short(record['input'], 120)}</div>"
        if record.get("input")
        else ""
    )
    summary = _summary_html(record.get("summary") or {})
    metric_rows = "".join(_metric_detail_row(metric) for metric in record["metrics"])
    return f"""
    <details style='background:{bg};border:1px solid #e5e7eb;border-radius:8px;margin:6px 0;padding:8px 12px'>
      <summary style='cursor:pointer;font-weight:600;list-style:none'>
        {icon} {record["id"]} <span style='color:#6b7280;font-size:13px;font-weight:400'>({record["duration"]:.1f}s)</span>
      </summary>
      {inp}
      {summary}
      <table style='margin-top:8px'><thead><tr>
        <th>Metric</th><th>Score</th><th>Threshold</th><th>Pass</th><th>Lý do</th>
      </tr></thead><tbody>{metric_rows}</tbody></table>
    </details>"""


def _summary_html(summary: dict) -> str:
    if not summary:
        return ""
    parts = []
    if summary.get("turn_average_score") is not None:
        parts.append(f"Average turn score: <b>{float(summary['turn_average_score']):.2f}</b>")
    if summary.get("conversation_score") is not None:
        parts.append(f"Conversation score: <b>{float(summary['conversation_score']):.2f}</b>")
    if not parts:
        return ""
    return f"<div class='input-text'>{' · '.join(parts)}</div>"


def _metric_detail_row(metric: dict) -> str:
    return (
        f"<tr><td>{metric['name']}</td>"
        f"<td style='color:{score_color(metric['score'])};font-weight:600'>"
        f"{metric['score']:.2f}</td>"
        f"<td>{metric['threshold']}</td>"
        f"<td>{'✅' if metric['passed'] else '❌'}</td>"
        f"<td class='reason'>{short(metric['reason'], 130)}</td></tr>"
    )


def _css() -> str:
    return """
*{box-sizing:border-box;margin:0;padding:0} body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;color:#111;background:#f9fafb;padding:24px}
.container{max-width:960px;margin:0 auto} h1{font-size:24px;margin-bottom:4px} h2{font-size:18px;margin:28px 0 10px;border-bottom:2px solid #e5e7eb;padding-bottom:6px}
h3{font-size:14px;font-weight:600;margin:16px 0 6px;color:#374151}.meta{color:#6b7280;font-size:13px;margin-bottom:20px}.summary-cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 24px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:14px 20px;min-width:140px}.card-val{font-size:28px;font-weight:700}.card-lbl{font-size:12px;color:#6b7280;margin-top:2px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;font-size:13px} th{background:#f3f4f6;text-align:left;padding:8px 12px;font-weight:600}
td{padding:7px 12px;border-top:1px solid #f3f4f6;vertical-align:top}.reason{color:#4b5563;font-size:12px}.input-text{font-size:12px;color:#4b5563;margin:6px 0 0;font-style:italic} section{margin-bottom:40px}
"""
