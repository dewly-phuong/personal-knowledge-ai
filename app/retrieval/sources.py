from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from app.retrieval.contracts import SearchContext, SourceResult
from app.retrieval.registry import KnowledgeSourceRegistry

MAX_GRAPH_NODES = 12
MAX_GRAPH_EDGES = 20
MAX_MONGO_COLLECTIONS = 2
MAX_MONGO_RECORDS_PER_COLLECTION = 5
MAX_MONGO_STRING_CHARS = 160
MAX_MONGO_FALLBACK_FIELDS = 8

_COLLECTION_ALIASES: dict[str, list[str]] = {
    "employees": ["nhan su", "nhân sự", "employee", "staff", "headcount"],
    "projects": ["du an", "dự án", "project", "budget", "progress"],
    "bug_tracker": ["bug", "incident", "loi", "lỗi", "patch", "release"],
    "kpi_okr": ["kpi", "okr", "objective", "muc tieu", "mục tiêu"],
    "org_chart": ["org", "organization", "bao cao", "báo cáo", "manager"],
    "attendance_october_2024": [
        "attendance",
        "cham cong",
        "chấm công",
        "remote",
        "muon",
        "muộn",
        "nghi phep",
        "nghỉ phép",
    ],
    "payroll_september_2024": ["payroll", "salary", "luong", "lương", "compensation"],
    "revenue_2024": [
        "revenue",
        "doanh thu",
        "mrr",
        "arr",
        "customer",
        "khach hang",
        "khách hàng",
    ],
    "infrastructure_costs_sep2024": [
        "cost",
        "chi phi",
        "chi phí",
        "cloud",
        "infrastructure",
        "ha tang",
        "hạ tầng",
    ],
    "recruitment_pipeline": [
        "recruitment",
        "tuyen dung",
        "tuyển dụng",
        "candidate",
        "ung vien",
        "ứng viên",
    ],
    "crm_customers": [
        "crm",
        "customer",
        "khach hang",
        "khách hàng",
        "contract",
        "hop dong",
        "hợp đồng",
    ],
    "sprint_tickets": ["sprint", "ticket", "jira", "task", "blocked"],
    "model_registry": ["model", "registry", "ai model", "ml model", "visionchat nlp"],
}

_MONGO_FIELD_ALLOWLIST: dict[str, list[str]] = {
    "employees": [
        "id",
        "full_name",
        "department",
        "position",
        "status",
        "manager_id",
    ],
    "projects": [
        "code",
        "name",
        "status",
        "phase",
        "progress_percent",
        "budget_vnd",
        "spent_vnd",
    ],
    "bug_tracker": [
        "id",
        "title",
        "project_code",
        "severity",
        "priority",
        "status",
        "assignee_id",
    ],
    "kpi_okr": ["id", "department", "year", "quarter", "objective", "key_results"],
    "org_chart": ["employee_id", "role", "reports_to", "team_size"],
    "attendance_october_2024": [
        "employee_id",
        "full_name",
        "date",
        "checkin_time",
        "checkout_time",
        "work_hours",
        "status",
        "note",
    ],
    "payroll_september_2024": [
        "employee_id",
        "full_name",
        "department",
        "position",
        "level",
        "total_gross",
        "net_salary",
        "status",
    ],
    "revenue_2024": [
        "period",
        "total_revenue_vnd",
        "total_mrr_vnd",
        "active_customers",
        "new_customers",
        "churned_customers",
        "net_revenue_retention_pct",
        "note",
    ],
    "infrastructure_costs_sep2024": [
        "provider",
        "service_category",
        "service_name",
        "environment",
        "project",
        "total_cost_vnd",
        "owner_team",
        "note",
    ],
    "recruitment_pipeline": [
        "candidate_id",
        "full_name",
        "position",
        "department",
        "level",
        "offer_accepted",
        "join_date",
        "status",
    ],
    "crm_customers": [
        "customer_id",
        "company_name",
        "industry",
        "tier",
        "status",
        "mrr_vnd",
        "products",
        "health_score",
    ],
    "sprint_tickets": [
        "ticket_id",
        "project",
        "sprint",
        "type",
        "title",
        "priority",
        "assignee_name",
        "status",
        "blocked",
    ],
    "model_registry": [
        "model_id",
        "model_name",
        "version",
        "task",
        "status",
        "champion",
        "accuracy",
        "f1_score",
        "latency_p99_ms",
        "note",
    ],
}


def _is_empty_text(text: str) -> bool:
    stripped = text.strip()
    return (
        not stripped
        or stripped == "[]"
        or stripped == "No wiki pages found."
        or stripped == "No matches found."
        or stripped.startswith("No records found")
    )


class WikiKnowledgeSource:
    name = "wiki"

    def __init__(self, service=None):
        self._service = service

    async def search(self, query: str, context: SearchContext) -> SourceResult:
        if self._service is None:
            from app.services.wiki_search import WikiSearchService

            self._service = WikiSearchService()

        text = self._service.search(query)
        if _is_empty_text(text):
            return SourceResult.empty(self.name, summary="No wiki data found.")
        return SourceResult.ok(
            self.name,
            data={"text": text},
            summary="Wiki returned matching snippets.",
        )


class GraphKnowledgeSource:
    name = "graph"

    def __init__(self, store=None):
        self._store = store

    async def search(self, query: str, context: SearchContext) -> SourceResult:
        if self._store is None:
            from app.services.graph_store import GraphStore

            self._store = GraphStore()

        candidate = self._find_candidate(query)
        if not candidate:
            return SourceResult.empty(self.name, summary="No graph entity matched.")

        subgraph = self._store.get_subgraph(candidate, hops=2)
        if not subgraph or not subgraph.get("nodes"):
            return SourceResult.empty(
                self.name,
                summary="Graph entity matched but no graph data was found.",
                metadata={"entity": candidate},
            )
        compact = _compact_subgraph(subgraph)
        return SourceResult.ok(
            self.name,
            data=compact,
            summary="Graph returned an entity neighborhood.",
            metadata={
                "entity": candidate,
                "node_count": len(subgraph.get("nodes", [])),
                "edge_count": len(subgraph.get("edges", [])),
                "max_nodes": MAX_GRAPH_NODES,
                "max_edges": MAX_GRAPH_EDGES,
            },
        )

    def _find_candidate(self, query: str) -> str | None:
        query_norm = _normalize(query)
        best: tuple[int, str] | None = None
        for node in getattr(self._store.graph, "nodes", []):
            node_text = str(node)
            node_norm = _normalize(node_text)
            if not node_norm:
                continue
            score = 0
            if node_norm in query_norm:
                score = len(node_norm)
            else:
                node_terms = set(node_norm.split())
                query_terms = set(query_norm.split())
                overlap = len(node_terms & query_terms)
                if overlap and overlap / max(1, len(node_terms)) >= 0.5:
                    score = overlap
            if score and (best is None or score > best[0]):
                best = (score, node_text)
        return best[1] if best else None


class MongoKnowledgeSource:
    name = "mongodb"

    def __init__(
        self,
        list_collections: Callable[[], list[str]] | None = None,
        query_runner: Callable[..., str] | None = None,
    ):
        self._list_collections = list_collections
        self._query_runner = query_runner

    async def search(self, query: str, context: SearchContext) -> SourceResult:
        collections = self._collections()
        if not collections:
            return SourceResult.empty(
                self.name, summary="No MongoDB collections found."
            )

        candidates = self._candidate_collections(query, collections)[
            :MAX_MONGO_COLLECTIONS
        ]
        if not candidates:
            return SourceResult.empty(
                self.name,
                summary="No MongoDB collection matched the query.",
                metadata={"collections_available": collections},
            )

        matches: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        record_limit = min(max(1, context.limit), MAX_MONGO_RECORDS_PER_COLLECTION)
        for collection in candidates:
            output = self._runner()(
                collection=collection,
                filter_json="{}",
                projection_json="",
                limit=record_limit,
            )
            if _is_mongo_error(output):
                errors.append({"collection": collection, "error": output})
                continue
            if _is_empty_text(output):
                continue
            parsed = _parse_json_or_text(output)
            matches.append(
                {
                    "collection": collection,
                    **_compact_mongo_records(
                        collection=collection,
                        records=parsed,
                        max_records=record_limit,
                    ),
                }
            )

        if not matches:
            metadata: dict[str, Any] = {"collections_checked": candidates}
            if errors:
                metadata["errors"] = errors
                return SourceResult.error_result(
                    self.name,
                    summary="MongoDB query failed for all matched collections.",
                    error="; ".join(
                        f"{item['collection']}: {item['error']}" for item in errors
                    ),
                    metadata=metadata,
                )
            return SourceResult.empty(
                self.name,
                summary="No MongoDB records found.",
                metadata=metadata,
            )
        metadata = {
            "collections_checked": candidates,
            "max_collections": MAX_MONGO_COLLECTIONS,
            "max_records_per_collection": MAX_MONGO_RECORDS_PER_COLLECTION,
        }
        if errors:
            metadata["errors"] = errors
        return SourceResult.ok(
            self.name,
            data={"collections": matches},
            summary="MongoDB returned records.",
            metadata=metadata,
        )

    def _collections(self) -> list[str]:
        if self._list_collections is not None:
            return self._list_collections()
        from app.tools.mongodb import _get_mongo_db

        return _get_mongo_db().list_collection_names()

    def _runner(self) -> Callable[..., str]:
        if self._query_runner is not None:
            return self._query_runner
        from app.tools.mongodb import _run_mongo_query

        return _run_mongo_query

    def _candidate_collections(self, query: str, collections: list[str]) -> list[str]:
        query_terms = _terms(query)
        scored: list[tuple[int, str]] = []
        for collection in collections:
            collection_terms = _terms(collection)
            for alias in _COLLECTION_ALIASES.get(collection, []):
                collection_terms.update(_terms(alias))
            score = len(query_terms & collection_terms)
            if score:
                scored.append((score, collection))
        if scored:
            return [name for _, name in sorted(scored, reverse=True)[:5]]
        return []


class UploadKnowledgeSource:
    name = "uploads"

    def __init__(self, context_builder: Callable[..., str] | None = None):
        self._context_builder = context_builder

    async def search(self, query: str, context: SearchContext) -> SourceResult:
        if not context.session_id:
            return SourceResult.empty(self.name, summary="No active upload session.")
        builder = self._context_builder
        if builder is None:
            from app.services.upload_artifacts import build_session_upload_context

            builder = build_session_upload_context
        text = builder(context.session_id, upload_ids=context.upload_ids, query=query)
        if _is_empty_text(text):
            return SourceResult.empty(self.name, summary="No upload data found.")
        return SourceResult.ok(
            self.name,
            data={"text": text},
            summary="Uploaded files returned context.",
        )


def build_default_registry() -> KnowledgeSourceRegistry:
    return KnowledgeSourceRegistry(
        [
            WikiKnowledgeSource(),
            GraphKnowledgeSource(),
            MongoKnowledgeSource(),
            UploadKnowledgeSource(),
        ]
    )


def _compact_subgraph(subgraph: dict[str, Any]) -> dict[str, Any]:
    nodes = list(subgraph.get("nodes") or [])
    edges = list(subgraph.get("edges") or [])
    compact_nodes = [
        {
            "id": str(node.get("id", "")),
            "type": str(node.get("type", "CONCEPT")),
        }
        for node in nodes[:MAX_GRAPH_NODES]
        if isinstance(node, dict)
    ]
    compact_edges = [
        {
            "source": str(edge.get("source", "")),
            "predicate": str(edge.get("predicate", "")),
            "target": str(edge.get("target", "")),
        }
        for edge in edges[:MAX_GRAPH_EDGES]
        if isinstance(edge, dict)
    ]
    return {
        "nodes": compact_nodes,
        "edges": compact_edges,
        "omitted_nodes": max(0, len(nodes) - len(compact_nodes)),
        "omitted_edges": max(0, len(edges) - len(compact_edges)),
    }


def _is_mongo_error(output: str) -> bool:
    stripped = output.strip()
    return stripped.startswith("Error") or stripped.startswith("JSON Syntax Error")


def _compact_mongo_records(
    *, collection: str, records: Any, max_records: int
) -> dict[str, Any]:
    if not isinstance(records, list):
        records = [{"value": records}]

    compact_records = [
        _compact_mongo_record(collection, record)
        for record in records[:max_records]
        if isinstance(record, dict)
    ]
    return {
        "records": compact_records,
        "returned_records": len(compact_records),
        "omitted_records": max(0, len(records) - len(compact_records)),
    }


def _compact_mongo_record(collection: str, record: dict[str, Any]) -> dict[str, Any]:
    allowed_fields = _MONGO_FIELD_ALLOWLIST.get(collection)
    if allowed_fields:
        return {
            field: _compact_mongo_value(record[field])
            for field in allowed_fields
            if field in record
        }

    compact: dict[str, Any] = {}
    for field, value in record.items():
        if field == "_id":
            continue
        compact[field] = _compact_mongo_value(value)
        if len(compact) >= MAX_MONGO_FALLBACK_FIELDS:
            break
    return compact


def _compact_mongo_value(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_MONGO_STRING_CHARS:
        return value[: MAX_MONGO_STRING_CHARS - 3] + "..."
    if isinstance(value, list):
        return [_compact_mongo_value(item) for item in value[:5]]
    if isinstance(value, dict):
        return {
            str(key): _compact_mongo_value(item)
            for key, item in list(value.items())[:MAX_MONGO_FALLBACK_FIELDS]
        }
    return value


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-zA-ZÀ-ỹ]+", " ", value.lower()).strip()


def _terms(value: str) -> set[str]:
    terms = set(_normalize(value).split())
    terms.update(
        term[:-1] for term in list(terms) if len(term) > 3 and term.endswith("s")
    )
    return terms


def _parse_json_or_text(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
