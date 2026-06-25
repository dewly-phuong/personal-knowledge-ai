import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_FILE = "eval_suite.json"


@dataclass(frozen=True)
class SuiteSpec:
    suite: str
    filename: str
    file_format: str
    required_fields: tuple[str, ...]
    metrics: tuple[str, ...]
    risk_level: str = "medium"
    tags: tuple[str, ...] = ("golden",)
    split: str = "test"


SUITE_SPECS: dict[str, SuiteSpec] = {
    "single_turn": SuiteSpec(
        suite="single_turn",
        filename="single_turn_goldens.json",
        file_format="json",
        required_fields=("input", "expected_output"),
        metrics=(
            "answer_relevancy",
            "faithfulness",
            "graph_reasoning",
            "domain_faithfulness",
            "tool_correctness",
        ),
    ),
    "multi_turn": SuiteSpec(
        suite="multi_turn",
        filename="multi_turn_goldens.json",
        file_format="json",
        required_fields=("scenario", "expected_outcome", "turns"),
        metrics=(
            "answer_relevancy",
            "faithfulness",
            "tool_correctness",
            "conversation_completeness",
            "knowledge_retention",
        ),
    ),
    "conversation": SuiteSpec(
        suite="conversation",
        filename="conversation_goldens.json",
        file_format="json",
        required_fields=("scenario", "turns", "ground_truth_output"),
        metrics=(
            "answer_relevancy",
            "faithfulness",
            "tool_correctness",
            "unified_domain_faithfulness",
            "unified_conversation_faithfulness",
            "knowledge_retention",
        ),
    ),
    "parallel_function_calling": SuiteSpec(
        suite="parallel_function_calling",
        filename="parallel_function_calling_questions.json",
        file_format="json",
        required_fields=("question", "expected_parallel_group_1"),
        metrics=(
            "required_tool_coverage",
            "parallel_batch_compliance",
            "sequential_tool_coverage",
        ),
        risk_level="high",
        tags=("golden", "tool_calling", "parallel"),
    ),
    "production_replay": SuiteSpec(
        suite="production_replay",
        filename="production_regression_candidates.jsonl",
        file_format="jsonl",
        required_fields=("question",),
        metrics=(
            "task_success",
            "faithfulness",
            "tool_correctness",
            "human_review",
        ),
        risk_level="high",
        tags=("production", "regression", "human_review"),
        split="production_audit",
    ),
}


def build_manifest(datasets_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec in SUITE_SPECS.values():
        path = datasets_dir / spec.filename
        if not path.exists():
            continue
        for payload in _read_records(path, spec.file_format):
            if not payload:
                continue
            records.append(_manifest_record(payload, spec))
    return records


def validate_manifest(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        case_id = str(record.get("id") or f"<record {index}>")
        suite = record.get("suite")
        payload = record.get("payload")

        if case_id in seen_ids:
            errors.append(f"{case_id}: duplicate id")
        seen_ids.add(case_id)

        if not suite:
            errors.append(f"{case_id}: missing suite")
            continue
        spec = SUITE_SPECS.get(str(suite))
        if spec is None:
            errors.append(f"{case_id}: unknown suite {suite}")
            continue

        if not isinstance(payload, dict):
            errors.append(f"{case_id}: payload must be an object")
            continue

        for field in spec.required_fields:
            if field not in payload:
                errors.append(f"{case_id}: payload missing {field}")

        if record.get("risk_level") not in {"low", "medium", "high", "critical"}:
            errors.append(f"{case_id}: invalid risk_level {record.get('risk_level')}")
    return errors


def write_manifest(records: list[dict[str, Any]], path: Path) -> list[str]:
    errors = validate_manifest(records)
    if errors:
        return errors
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return []


def sync_adapters(records: list[dict[str, Any]], datasets_dir: Path) -> None:
    errors = validate_manifest(records)
    if errors:
        raise ValueError("Invalid manifest:\n" + "\n".join(errors))

    datasets_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = {
        suite: [] for suite in SUITE_SPECS
    }
    for record in records:
        grouped[str(record["suite"])].append(record["payload"])

    for suite, spec in SUITE_SPECS.items():
        path = datasets_dir / spec.filename
        payloads = grouped[suite]
        if spec.file_format == "jsonl":
            lines = [json.dumps(item, ensure_ascii=False) for item in payloads]
            path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        else:
            path.write_text(
                json.dumps(payloads, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_record(payload: dict[str, Any], spec: SuiteSpec) -> dict[str, Any]:
    case_id = str(payload.get("id") or _fallback_id(spec, len(str(payload))))
    return {
        "id": case_id,
        "suite": spec.suite,
        "risk_level": _risk_level(payload, spec),
        "tags": list(dict.fromkeys([*spec.tags, *_payload_tags(payload)])),
        "metrics": list(spec.metrics),
        "source_dataset": spec.filename,
        "split": spec.split,
        "human_label": payload.get("human_label"),
        "payload": payload,
    }


def _risk_level(payload: dict[str, Any], spec: SuiteSpec) -> str:
    value = payload.get("risk_level") or payload.get("difficulty")
    if value in {"low", "medium", "high", "critical"}:
        return str(value)
    if value == "hard":
        return "high"
    if value == "easy":
        return "low"
    return spec.risk_level


def _payload_tags(payload: dict[str, Any]) -> list[str]:
    tags = payload.get("tags") or []
    if isinstance(tags, str):
        return [tags]
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    return []


def _fallback_id(spec: SuiteSpec, suffix: int) -> str:
    prefix = {
        "single_turn": "ST",
        "multi_turn": "MT",
        "conversation": "CV",
        "parallel_function_calling": "PFC",
        "production_replay": "PROD",
    }[spec.suite]
    return f"{prefix}-{suffix}"


def _read_records(path: Path, file_format: str) -> list[dict[str, Any]]:
    if file_format == "jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data
