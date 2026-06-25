import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GateDecision:
    passed: bool
    failures: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    metrics: dict[str, float]


METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "faithfulness_pass_rate": ("faithfulness", "domainfaithfulness"),
    "answer_relevance_pass_rate": ("answer relevancy", "answerrelevancy"),
    "answer_relevance": ("answer relevancy", "answerrelevancy"),
    "tool_correctness_pass_rate": (
        "tool correctness",
        "required tool coverage",
        "parallel batch compliance",
        "sequential tool coverage",
    ),
    "required_tool_coverage_pass_rate": ("required tool coverage",),
    "parallel_batch_pass_rate": ("parallel batch compliance",),
    "conversation_score_pass_rate": ("conversation score",),
}


def evaluate_gates(
    scores: list[dict[str, Any]], config: dict[str, Any]
) -> GateDecision:
    computed = _compute_gate_metrics(scores)
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    gates = (config.get("release_gates") or {})
    for section, rules in gates.items():
        if not isinstance(rules, dict):
            continue
        for metric_key, rule in rules.items():
            if not isinstance(rule, dict):
                continue
            item = _evaluate_rule(metric_key, rule, computed)
            if item is None:
                continue
            if section == "critical" and not item["passed"]:
                failures.append(item)
            elif section != "critical" and not item["passed"]:
                warnings.append(item)

    return GateDecision(
        passed=not failures,
        failures=failures,
        warnings=warnings,
        metrics=computed,
    )


def _compute_gate_metrics(scores: list[dict[str, Any]]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    if scores:
        metrics["task_success_rate"] = sum(
            1 for row in scores if bool(row.get("passed"))
        ) / len(scores)

    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in scores:
        for metric in row.get("metrics") or []:
            name = str(metric.get("name") or "")
            if not name:
                continue
            by_name.setdefault(_normalize(name), []).append(metric)

    for key, aliases in METRIC_ALIASES.items():
        matched = [
            metric
            for normalized_name, items in by_name.items()
            if any(alias in normalized_name for alias in aliases)
            for metric in items
        ]
        if matched:
            metrics[key] = sum(1 for metric in matched if metric.get("passed")) / len(
                matched
            )
            metrics[f"{key}_avg_score"] = sum(
                float(metric.get("score") or 0) for metric in matched
            ) / len(matched)

    return metrics


def _evaluate_rule(
    metric_key: str, rule: dict[str, Any], computed: dict[str, float]
) -> dict[str, Any] | None:
    if metric_key not in computed:
        return {
            "metric": metric_key,
            "passed": False,
            "actual": None,
            "rule": rule,
            "reason": "metric missing from scores",
        }

    actual = computed[metric_key]
    minimum = rule.get("min")
    maximum = rule.get("max")
    passed = True
    reasons: list[str] = []
    if minimum is not None and actual < float(minimum):
        passed = False
        reasons.append(f"{actual:.4f} < min {float(minimum):.4f}")
    if maximum is not None and actual > float(maximum):
        passed = False
        reasons.append(f"{actual:.4f} > max {float(maximum):.4f}")

    return {
        "metric": metric_key,
        "passed": passed,
        "actual": actual,
        "rule": rule,
        "reason": "; ".join(reasons) if reasons else "passed",
    }


def _normalize(name: str) -> str:
    return " ".join(name.lower().replace("_", " ").split())


def read_scores(path: Path, run_id: str = "latest") -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        return []
    if run_id == "latest":
        latest = rows[-1].get("run_id")
        return [row for row in rows if row.get("run_id") == latest]
    if run_id == "all":
        return rows
    return [row for row in rows if row.get("run_id") == run_id]


def load_gate_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(text)
        return parsed or {}
    except Exception:
        pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            raise ValueError(f"Unsupported YAML line: {raw_line}")
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value:
            current[key] = _parse_scalar(value)
        else:
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
    return root


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip('"').strip("'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply eval release gates.")
    parser.add_argument("--scores", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--run-id", default="latest")
    args = parser.parse_args(argv)

    decision = evaluate_gates(
        read_scores(Path(args.scores), args.run_id),
        load_gate_config(Path(args.rules)),
    )
    print(_format_decision(decision))
    return 0 if decision.passed else 1


def _format_decision(decision: GateDecision) -> str:
    lines = [
        "Release gate decision: " + ("PASS" if decision.passed else "FAIL"),
        "Computed metrics:",
    ]
    for key, value in sorted(decision.metrics.items()):
        lines.append(f"- {key}: {value:.4f}")
    if decision.failures:
        lines.append("Critical failures:")
        lines.extend(
            f"- {item['metric']}: {item['reason']}" for item in decision.failures
        )
    if decision.warnings:
        lines.append("Warnings:")
        lines.extend(
            f"- {item['metric']}: {item['reason']}" for item in decision.warnings
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
