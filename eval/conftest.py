"""
eval/conftest.py

Pytest plugin tự động:
  - Ghi kết quả từng metric ra eval/reports/scores.jsonl sau mỗi test
  - In summary pass-rate cuối session
  - Không cần sửa gì trong test_single_turn.py hay test_multi_turn.py

Cấu trúc scores.jsonl (một dòng = một lần chạy test):
  {
    "run_id":  "20250620_143000",
    "test_id": "ST001",
    "file":    "test_single_turn",
    "passed":  true,
    "metrics": [
      {"name": "AnswerRelevancy", "score": 0.87, "passed": true, "reason": "..."},
      ...
    ]
  }
"""

import json
import pathlib
import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

REPORT_DIR = pathlib.Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)
SCORES_FILE = REPORT_DIR / "scores.jsonl"

# run_id duy nhất cho toàn bộ session pytest này
RUN_ID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Tích lũy để tính summary cuối session
_session_results: list[dict] = []


# ---------------------------------------------------------------------------
# Hook: chạy sau mỗi test case (call phase)
# ---------------------------------------------------------------------------

def pytest_runtest_logreport(report):
    """Ghi kết quả metric sau mỗi test vào scores.jsonl."""
    if report.when != "call":
        return

    # Tách test_id (ví dụ: ST001, MT002) từ nodeid
    # nodeid dạng: eval/test_single_turn.py::test_single_turn[ST001]
    nodeid = report.nodeid
    test_id = nodeid.split("[")[-1].rstrip("]") if "[" in nodeid else nodeid
    file_name = nodeid.split("::")[0].split("/")[-1].replace(".py", "")

    entry = {
        "run_id":  RUN_ID,
        "test_id": test_id,
        "file":    file_name,
        "passed":  report.passed,
        "metrics": [],
    }

    # deepeval gắn kết quả metric vào report.user_properties
    for key, val in getattr(report, "user_properties", []):
        if key == "deepeval_results":
            for r in val:
                entry["metrics"].append({
                    "name":   r.name,
                    "score":  round(float(r.score), 4),
                    "passed": bool(r.success),
                    "reason": (r.reason or "").strip(),
                })

    _session_results.append(entry)

    # Ghi ngay vào file (append) — không mất dữ liệu nếu session crash giữa chừng
    with open(SCORES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Hook: chạy một lần sau khi toàn bộ session kết thúc
# ---------------------------------------------------------------------------

def pytest_sessionfinish(session, exitstatus):
    """In summary pass-rate theo từng metric ra terminal."""
    if not _session_results:
        return

    # Tính pass-rate theo metric
    metric_stats: dict[str, dict] = defaultdict(lambda: {"passed": 0, "total": 0, "scores": []})
    for entry in _session_results:
        for m in entry["metrics"]:
            s = metric_stats[m["name"]]
            s["total"]  += 1
            s["passed"] += int(m["passed"])
            s["scores"].append(m["score"])

    total_tests  = len(_session_results)
    passed_tests = sum(1 for e in _session_results if e["passed"])

    print(f"\n{'='*60}")
    print(f"  EVAL SUMMARY — run {RUN_ID}")
    print(f"{'='*60}")
    print(f"  Tests : {passed_tests}/{total_tests} passed "
          f"({'%.0f' % (passed_tests/total_tests*100)}%)")
    print(f"{'─'*60}")
    print(f"  {'Metric':<32} {'Avg':>5}  {'Pass':>9}")
    print(f"{'─'*60}")

    for name, s in sorted(metric_stats.items()):
        avg  = sum(s["scores"]) / len(s["scores"])
        rate = s["passed"] / s["total"]
        flag = "" if rate >= 0.8 else "  ← cần xem lại"
        print(f"  {name:<32} {avg:>5.2f}  "
              f"{s['passed']}/{s['total']} ({rate:.0%}){flag}")

    print(f"{'='*60}")
    print(f"  Chi tiết: {SCORES_FILE}")
    print(f"{'='*60}\n")