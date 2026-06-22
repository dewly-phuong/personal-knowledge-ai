"""
generate_report.py

Đọc single_turn_results.json + multi_turn_results.json và sinh:
  - reports/report.md   — báo cáo Markdown đầy đủ
  - reports/report.html — báo cáo HTML (mở trình duyệt)

Chạy:
    python generate_report.py \
        --single single_turn_results.json \
        --multi  multi_turn_results.json

    # Hoặc chỉ một file:
    python generate_report.py --single single_turn_results.json
"""

import argparse
import json
import pathlib
import sys
from collections import defaultdict
from datetime import datetime, timezone

from litellm import uuid

# ─── Ngưỡng pass-rate để cảnh báo ────────────────────────────────────────────
WARN_THRESHOLD = 0.80

# ─── Helpers ─────────────────────────────────────────────────────────────────

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


# ─── Parse ────────────────────────────────────────────────────────────────────

def parse_file(path: pathlib.Path, label: str) -> list[dict]:
    """
    Trả về list các test-record chuẩn hóa:
    {
      "id":       "ST001",
      "label":    "single" | "multi",
      "passed":   bool,
      "duration": float,
      "input":    str | None,   # chỉ có ở single-turn
      "metrics":  [{"name", "score", "threshold", "passed", "reason"}]
    }
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for r in raw.get("results", []):
        rid = r["id"].split("[")[-1].rstrip("]")
        tc  = (r.get("deepeval_test_cases") or [{}])[0]

        # metrics_data có thể nằm ở result hoặc test_case
        metrics_raw = tc.get("metrics_data") or []

        metrics = [
            {
                "name":      m["name"],
                "score":     float(m.get("score") or 0),
                "threshold": float(m.get("threshold") or 0),
                "passed":    bool(m.get("success", False)),
                "reason":    (m.get("reason") or "").strip(),
            }
            for m in metrics_raw
        ]

        records.append({
            "id":       rid,
            "label":    label,
            "passed":   r.get("outcome") == "passed",
            "duration": float(r.get("duration_s") or 0),
            "input":    tc.get("input"),       # None ở multi-turn
            "metrics":  metrics,
        })
    return records


# ─── Aggregate ────────────────────────────────────────────────────────────────

def aggregate(records: list[dict]) -> dict:
    """Thống kê theo metric."""
    stats = defaultdict(lambda: {"passed": 0, "total": 0, "scores": []})
    for r in records:
        for m in r["metrics"]:
            s = stats[m["name"]]
            s["total"]  += 1
            s["passed"] += int(m["passed"])
            s["scores"].append(m["score"])
    return dict(stats)


# ─── Markdown ─────────────────────────────────────────────────────────────────

def build_markdown(single: list[dict], multi: list[dict],
                   generated_at: str) -> str:
    all_records = single + multi
    n_tests  = len(all_records)
    n_passed = sum(1 for r in all_records if r["passed"])
    overall  = n_passed / n_tests if n_tests else 0

    lines = [
        f"# Eval report",
        f"",
        f"**Create at:** {generated_at}  ",
        f"**Tổng tests:** {n_passed}/{n_tests} passed ({overall:.0%})  ",
        f"",
    ]

    # ── Section cho từng loại ────────────────────────────────────────────────
    for records, title in [(single, "Single-turn"), (multi, "Multi-turn")]:
        if not records:
            continue
        n  = len(records)
        np = sum(1 for r in records if r["passed"])
        stats = aggregate(records)

        lines += [
            f"---",
            f"",
            f"## {title} — {np}/{n} passed ({np/n:.0%})",
            f"",
            f"### Tổng hợp theo metric",
            f"",
            f"| Metric | Avg | Pass rate | Trạng thái |",
            f"|--------|-----|-----------|------------|",
        ]

        for name, s in sorted(stats.items()):
            a    = avg(s["scores"])
            rate = s["passed"] / s["total"]
            flag = "🟢 OK" if rate >= WARN_THRESHOLD else "🔴 Cần xem lại"
            lines.append(
                f"| {name} | {bar(a)} {a:.2f} "
                f"| {s['passed']}/{s['total']} ({rate:.0%}) | {flag} |"
            )

        # ── Chi tiết từng test ───────────────────────────────────────────────
        lines += ["", "### Chi tiết từng test case", ""]

        for r in records:
            status = icon(r["passed"])
            header = f"#### {status} {r['id']}  `{r['duration']:.1f}s`"
            if r.get("input"):
                header += f"\n\n> **Input:** {short(r['input'], 100)}"
            lines.append(header)
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

        # ── Tóm tắt fail ────────────────────────────────────────────────────
        failed_metrics = [
            (r["id"], m)
            for r in records
            for m in r["metrics"]
            if not m["passed"]
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


# ─── HTML ────────────────────────────────────────────────────────────────────

def score_color(score: float) -> str:
    if score >= 0.8:  return "#22c55e"   # green
    if score >= 0.6:  return "#f59e0b"   # amber
    return "#ef4444"                      # red

def build_html(single: list[dict], multi: list[dict],
               generated_at: str) -> str:
    all_records = single + multi
    n_tests  = len(all_records)
    n_passed = sum(1 for r in all_records if r["passed"])
    overall  = n_passed / n_tests if n_tests else 0

    def metric_rows_html(records):
        stats = aggregate(records)
        rows  = ""
        for name, s in sorted(stats.items()):
            a    = avg(s["scores"])
            rate = s["passed"] / s["total"]
            col  = score_color(a)
            flag = "🟢 OK" if rate >= WARN_THRESHOLD else "🔴 Xem lại"
            rows += (
                f"<tr>"
                f"<td>{name}</td>"
                f"<td><span style='color:{col};font-weight:600'>{a:.2f}</span></td>"
                f"<td>{s['passed']}/{s['total']} ({rate:.0%})</td>"
                f"<td>{flag}</td>"
                f"</tr>"
            )
        return rows

    def detail_rows_html(records):
        html = ""
        for r in records:
            bg   = "#f0fdf4" if r["passed"] else "#fef2f2"
            ico  = "✅" if r["passed"] else "❌"
            inp  = f"<div class='input-text'>→ {short(r['input'], 120)}</div>" if r.get("input") else ""
            mrows = ""
            for m in r["metrics"]:
                col = score_color(m["score"])
                mrows += (
                    f"<tr>"
                    f"<td>{m['name']}</td>"
                    f"<td style='color:{col};font-weight:600'>{m['score']:.2f}</td>"
                    f"<td>{m['threshold']}</td>"
                    f"<td>{'✅' if m['passed'] else '❌'}</td>"
                    f"<td class='reason'>{short(m['reason'], 130)}</td>"
                    f"</tr>"
                )
            html += f"""
            <details style='background:{bg};border:1px solid #e5e7eb;border-radius:8px;margin:6px 0;padding:8px 12px'>
              <summary style='cursor:pointer;font-weight:600;list-style:none'>
                {ico} {r['id']} <span style='color:#6b7280;font-size:13px;font-weight:400'>({r['duration']:.1f}s)</span>
              </summary>
              {inp}
              <table style='margin-top:8px'><thead><tr>
                <th>Metric</th><th>Score</th><th>Threshold</th><th>Pass</th><th>Lý do</th>
              </tr></thead><tbody>{mrows}</tbody></table>
            </details>"""
        return html

    def section_html(records, title):
        if not records:
            return ""
        n  = len(records)
        np = sum(1 for r in records if r["passed"])
        return f"""
        <section>
          <h2>{title} <span style='color:#6b7280;font-size:16px;font-weight:400'>{np}/{n} passed ({np/n:.0%})</span></h2>
          <h3>Tổng hợp theo metric</h3>
          <table><thead><tr><th>Metric</th><th>Avg score</th><th>Pass rate</th><th>Trạng thái</th></tr></thead>
          <tbody>{metric_rows_html(records)}</tbody></table>
          <h3 style='margin-top:20px'>Chi tiết từng test case</h3>
          {detail_rows_html(records)}
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eval report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         font-size: 14px; color: #111; background: #f9fafb; padding: 24px; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin: 28px 0 10px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; }}
  h3 {{ font-size: 14px; font-weight: 600; margin: 16px 0 6px; color: #374151; }}
  .meta {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
  .summary-cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0 24px; }}
  .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 10px;
           padding: 14px 20px; min-width: 140px; }}
  .card-val {{ font-size: 28px; font-weight: 700; }}
  .card-lbl {{ font-size: 12px; color: #6b7280; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; font-size: 13px; }}
  th {{ background: #f3f4f6; text-align: left; padding: 8px 12px; font-weight: 600; }}
  td {{ padding: 7px 12px; border-top: 1px solid #f3f4f6; vertical-align: top; }}
  .reason {{ color: #4b5563; font-size: 12px; }}
  .input-text {{ font-size: 12px; color: #4b5563; margin: 6px 0 0; font-style: italic; }}
  section {{ margin-bottom: 40px; }}
</style>
</head>
<body>
<div class="container">
  <h1>Eval report</h1>
  <p class="meta">Create at {generated_at}</p>
  <div class="summary-cards">
    <div class="card">
      <div class="card-val" style="color:{'#22c55e' if overall>=0.8 else '#ef4444'}">{overall:.0%}</div>
      <div class="card-lbl">Overall pass rate</div>
    </div>
    <div class="card">
      <div class="card-val">{n_passed}/{n_tests}</div>
      <div class="card-lbl">Tests passed</div>
    </div>
    <div class="card">
      <div class="card-val">{len(single)}</div>
      <div class="card-lbl">Single-turn</div>
    </div>
    <div class="card">
      <div class="card-val">{len(multi)}</div>
      <div class="card-lbl">Multi-turn</div>
    </div>
  </div>
  {section_html(single, "Single-turn")}
  {section_html(multi,  "Multi-turn")}
</div>
</body>
</html>"""


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", help="Đường dẫn single_turn_results.json")
    ap.add_argument("--multi",  help="Đường dẫn multi_turn_results.json")
    ap.add_argument("--out",    default="eval/reports", help="Thư mục output (default: reports)")
    args = ap.parse_args()

    if not args.single and not args.multi:
        ap.print_help()
        sys.exit(1)

    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)

    single = parse_file(pathlib.Path(args.single), "single") if args.single else []
    multi  = parse_file(pathlib.Path(args.multi),  "multi")  if args.multi  else []

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    rid = uuid.uuid4().hex[:8]

    if not args.single:
        subname = "-multi-turn"
    elif not args.multi:
        subname = "-single-turn"
    else:
        subname = ""

    md_path   = out / f"report{subname}-{rid}.md"
    html_path = out / f"report{subname}-{rid}.html"
 
    md_path.write_text(build_markdown(single, multi, now), encoding="utf-8")
    html_path.write_text(build_html(single, multi, now),   encoding="utf-8")

    # ── Terminal summary ─────────────────────────────────────────────────────
    all_records = single + multi
    n_tests  = len(all_records)
    n_passed = sum(1 for r in all_records if r["passed"])
    stats    = aggregate(all_records)

    print(f"\n{'='*56}")
    print(f"  EVAL SUMMARY")
    print(f"{'='*56}")
    print(f"  Tests : {n_passed}/{n_tests} passed ({n_passed/n_tests:.0%})")
    print(f"{'─'*56}")
    print(f"  {'Metric':<34} {'Avg':>5}  {'Pass':>8}")
    print(f"{'─'*56}")
    for name, s in sorted(stats.items()):
        a    = avg(s["scores"])
        rate = s["passed"] / s["total"]
        flag = "" if rate >= WARN_THRESHOLD else "  ← xem lại"
        print(f"  {name:<34} {a:>5.2f}  {s['passed']}/{s['total']} ({rate:.0%}){flag}")
    print(f"{'='*56}")
    print(f"  Markdown : {out/'report.md'}")
    print(f"  HTML     : {out/'report.html'}")
    print(f"{'='*56}\n")


if __name__ == "__main__":
    main()