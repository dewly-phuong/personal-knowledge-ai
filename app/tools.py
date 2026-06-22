import os
import re
import json
import datetime
import threading
import uuid
import contextvars
from typing import List, Dict

from langchain_core.tools import tool

from app.core.redis import get_redis_client
from app.services.wiki_search import WikiSearchService
from app.services.graph_store import GraphStore

# Contextvars accumulator — lets callers (e.g. eval model_callback) collect
# retrieval chunks for a single agent.invoke() call without deepeval tracing.
_retrieval_accumulator: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "retrieval_accumulator", default=None
)


def start_retrieval_capture() -> None:
    """Reset and activate the per-invocation retrieval accumulator."""
    _retrieval_accumulator.set([])


def pop_retrieval_capture() -> List[str]:
    """Return accumulated retrieval chunks and deactivate the accumulator."""
    chunks = _retrieval_accumulator.get() or []
    _retrieval_accumulator.set(None)
    return chunks


def _register_retrieval(chunks: List[str]) -> None:
    """Append retrieval chunks to the active deepeval trace and/or local accumulator."""
    # Local accumulator (used by eval model_callback)
    acc = _retrieval_accumulator.get()
    if acc is not None:
        acc.extend(chunks)
    # deepeval trace (no-op when not tracing)
    try:
        from deepeval.tracing.tracing import current_trace_context
        from deepeval.tracing import update_current_trace

        trace = current_trace_context.get()
        if trace is not None:
            existing = getattr(trace, "retrieval_context", None) or []
            update_current_trace(retrieval_context=existing + chunks)
    except Exception:
        pass

_wiki = WikiSearchService()
_mongo_client = None
_mongo_lock = threading.Lock()


def _get_mongo_db():
    global _mongo_client
    if _mongo_client is None:
        with _mongo_lock:
            if _mongo_client is None:
                from pymongo import MongoClient

                _mongo_client = MongoClient(
                    os.getenv("MONGO_URI", "mongodb://localhost:27017/")
                )
    return _mongo_client["personal_knowledge_ai"]


@tool
def get_current_time():
    """Get the current time in the system. Use this whenever you are asked about the current time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def wiki_search(query: str) -> str:
    """
    Search across the compiled wiki pages using hybrid search (BM25 full-text + Qdrant vector cosine similarity).
    Use this when the user asks questions that require matching terms or reading documentation contents.
    IMPORTANT: If searching for information about a specific entity, project, service, pipeline, or object, 
    you MUST first call `graph_traverse` to retrieve its relationships from the knowledge graph before calling this tool.
    Returns the top 5 relevant snippets with their file paths.
    """
    result = _wiki.search(query)
    # Split on double-newline boundaries to register individual snippets
    chunks = [c.strip() for c in result.split("\n\n") if c.strip()]
    _register_retrieval(chunks)
    return result


@tool
def entity_search(entity_name: str, query: str) -> str:
    """
    Combined entity lookup: finds direct relationships for entity_name from the knowledge graph,
    then performs wiki search with query expanded by related entity names for higher recall.
    Use this instead of calling graph_traverse + wiki_search separately when investigating
    a specific entity, service, pipeline, project, or object.
    Returns a compact graph summary followed by top wiki snippets.
    """
    store = GraphStore()
    # 1-hop only for the graph context shown to agent (less noise);
    # 2-hop neighbor names still used for query expansion (higher recall)
    subg_1hop = store.get_subgraph(entity_name, hops=1)
    subg_2hop = store.get_subgraph(entity_name, hops=2)

    canonical = entity_name
    if not subg_1hop or not subg_1hop["nodes"]:
        all_nodes = list(store.graph.nodes)
        entity_lower = entity_name.lower().strip()

        # 1) exact case-insensitive
        matches = [n for n in all_nodes if n.lower().strip() == entity_lower]

        # 2) keyword overlap (≥50% of query words hit the node name)
        if not matches:
            entity_words = set(entity_lower.split())
            matches = [
                n for n in all_nodes
                if entity_words and
                len(entity_words & set(n.lower().split())) / len(entity_words) >= 0.5
            ]

        # 3) difflib fuzzy (cutoff 0.55 — loose enough for VN paraphrases)
        if not matches:
            from difflib import get_close_matches
            lower_map = {n.lower(): n for n in all_nodes}
            close = get_close_matches(entity_lower, list(lower_map), n=3, cutoff=0.55)
            matches = [lower_map[c] for c in close]

        if matches:
            canonical = matches[0]
            subg_1hop = store.get_subgraph(canonical, hops=1)
            subg_2hop = store.get_subgraph(canonical, hops=2)

    if subg_1hop and subg_1hop["nodes"]:
        # compact: "Source --[predicate]--> Target" per edge, skip self-referential noise
        edge_lines = [
            f"{e['source']} --[{e['predicate']}]--> {e['target']}"
            for e in subg_1hop["edges"]
        ]
        graph_context = f"Relations for '{canonical}': " + (
            " | ".join(edge_lines) if edge_lines else "no direct relations"
        )
        # 2-hop names for query expansion only
        neighbor_names = [n["id"] for n in subg_2hop["nodes"] if n["id"] != canonical]
        expanded_query = f"{query} {canonical} {' '.join(neighbor_names[:10])}"
    else:
        graph_context = f"'{entity_name}' not found in knowledge graph."
        expanded_query = f"{query} {entity_name}"

    search_results = _wiki.search(expanded_query)
    _register_retrieval([graph_context, search_results])
    return f"[Graph] {graph_context}\n\n[Wiki]\n{search_results}"


@tool
def graph_traverse(entity_name: str) -> str:
    """
    Retrieve relationships for a given entity from the knowledge graph up to 2 hops.
    Use this to traverse the dependencies, pipeline flows, or ownership of services/components.
    Always call this tool first when investigating a specific entity, service, pipeline, project, or object, 
    before using `wiki_search` to find detailed documentation.
    Returns entity details and serialized triples in the format (A) --[predicate]--> (B).
    """
    store = GraphStore()
    subg = store.get_subgraph(entity_name, hops=2)
    if not subg or not subg["nodes"]:
        all_nodes = list(store.graph.nodes)
        matches = [
            n for n in all_nodes if n.lower().strip() == entity_name.lower().strip()
        ]
        if matches:
            subg = store.get_subgraph(matches[0], hops=2)
        else:
            return f"Entity '{entity_name}' not found in the knowledge graph."

    node_descriptions = [
        f"- {n['id']} [{n['type']}]{' (' + n['description'] + ')' if n.get('description') else ''}"
        for n in subg["nodes"]
    ]
    triples = [
        f"  ({e['source']}) --[{e['predicate']}]--> ({e['target']})"
        for e in subg["edges"]
    ]
    result = (
        f"Subgraph for '{entity_name}' (up to 2 hops):\n\n"
        "Entities involved:\n" + "\n".join(node_descriptions) + "\n\n"
        "Relationships:\n"
        + ("\n".join(triples) if triples else "  No relations found.")
    )
    _register_retrieval([result])
    return result


# ── Ingestion helpers ─────────────────────────────────────────────────────────


def _run_ingest_async(task_id: str, source: str, path_or_repo: str) -> None:
    r = get_redis_client()
    task_key = f"ingest:task:{task_id}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        from ingest import run_ingest_pipeline

        if source == "local":
            result = run_ingest_pipeline(source=source, dir_path=path_or_repo)
        elif source == "github":
            result = run_ingest_pipeline(source=source, repo_name=path_or_repo)
        else:
            raise ValueError(f"Unsupported source: {source}")
        task_data = {
            "status": "SUCCESS",
            "started_at": now,
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": None,
            "summary": result.get("summary", "Ingestion run finished."),
        }
    except Exception as e:
        task_data = {
            "status": "FAILED",
            "started_at": now,
            "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error": str(e),
            "summary": "Ingestion failed with error.",
        }
    r.set(task_key, json.dumps(task_data), ex=7 * 86400)


def _schedule_ingest(source: str, path_or_repo: str, summary: str) -> str:
    """Creates a PENDING task in Redis and starts a daemon background thread. Returns task_id."""
    task_id = str(uuid.uuid4())
    r = get_redis_client()
    r.set(
        f"ingest:task:{task_id}",
        json.dumps(
            {
                "status": "PENDING",
                "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "finished_at": None,
                "error": None,
                "summary": summary,
            }
        ),
        ex=7 * 86400,
    )
    threading.Thread(
        target=_run_ingest_async, args=(task_id, source, path_or_repo), daemon=True
    ).start()
    return task_id


@tool
def ingest_source(source: str, path_or_repo: str) -> str:
    """
    Triggers an asynchronous ingestion run for a source.
    source: 'local' (requires directory path) or 'github' (requires 'owner/repo').
    path_or_repo: The directory path or github repo identifier.
    Returns a task ID that can be polled for status.
    """
    task_id = _schedule_ingest(
        source, path_or_repo, "Task scheduled in background thread."
    )
    return (
        f"Ingestion task scheduled successfully. Task ID: {task_id}. "
        "You can check status with the `/ingest/{task_id}` endpoint or let the user know."
    )


@tool
def sync_knowledge_base() -> str:
    """
    Manually triggers a full synchronization of the local knowledge base (raw/local directory).
    Use this when the user asks to sync, update, or refresh the knowledge base manually.
    Returns a task ID that can be polled for status.
    """
    task_id = _schedule_ingest(
        "local",
        "raw/local",
        "Manual knowledge base sync scheduled in background thread.",
    )
    return f"Manual knowledge base synchronization started. Task ID: {task_id}. You can track status with this ID."


@tool
def lint_wiki() -> str:
    """
    Audits the wiki pages for consistency, orphans, and conflict tags.
    Returns a markdown health audit report.
    """
    wiki_dir = "wiki"
    if not os.path.exists(wiki_dir):
        return "Wiki directory does not exist. No files to audit."

    pages = [
        os.path.join(root, fname)
        for root, _, files in os.walk(wiki_dir)
        for fname in files
        if fname.endswith(".md")
    ]

    conflict_pages: List[str] = []
    incoming: Dict[str, List[str]] = {os.path.normpath(p): [] for p in pages}
    outgoing: Dict[str, List[str]] = {os.path.normpath(p): [] for p in pages}

    for page in pages:
        norm_page = os.path.normpath(page)
        try:
            with open(page, "r", encoding="utf-8") as f:
                content = f.read()
            if "[CONFLICT]" in content:
                conflict_pages.append(page)
            for link in re.findall(r"\[\[([^\]]+)\]\]", content):
                slug = link.lower().strip().replace(" ", "-")
                for p in pages:
                    if os.path.splitext(os.path.basename(p))[0] == slug:
                        target = os.path.normpath(p)
                        outgoing[norm_page].append(target)
                        if target in incoming:
                            incoming[target].append(norm_page)
                        break
        except Exception:
            pass

    orphan_pages = [
        p
        for p in pages
        if os.path.basename(p) not in ("index.md", "log.md")
        and not incoming.get(os.path.normpath(p))
    ]

    report = [
        "# Wiki Health Audit Report",
        f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Wiki Pages Audited: {len(pages)}",
        "",
        "## Conflict Tags",
    ]
    if conflict_pages:
        report.append(
            "The following pages contain active `[CONFLICT]` tags that require manual resolution:"
        )
        report.extend(
            f"- [{os.path.basename(cp)}](file://{os.path.abspath(cp)})"
            for cp in conflict_pages
        )
    else:
        report.append("✅ No pages with active `[CONFLICT]` tags found.")
    report += ["", "## Orphan Pages"]
    if orphan_pages:
        report.append(
            "The following pages are not linked from any other page in the wiki:"
        )
        report.extend(
            f"- [{os.path.basename(op)}](file://{os.path.abspath(op)})"
            for op in orphan_pages
        )
    else:
        report.append("✅ No orphan pages found.")
    report.append("")
    return "\n".join(report)


@tool
def mongodb_query(
    collection: str, filter_json: str, projection_json: str = None, limit: int = 100
) -> str:
    """
    Query structured company data from MongoDB. Use this when you need exact facts about employees,
    projects, bug tracking, KPIs, organizational charts, payroll, attendance, CRM customers,
    sprint tickets, revenue, recruitment, AI model registry, or infrastructure costs.
    filter_json should use regular MongoDB query syntax. example: '{"status": {"$regex": "Muon", "$options": "i}}' to find late employees.

    Available Collections & Schemas:

    --- JSON-backed (master data) ---
    1. 'employees': Information about staff.
       - Fields: id, full_name, gender, date_of_birth, department, position, level, email, phone,
         start_date, employment_type, status, manager_id, office, avatar
    2. 'projects': Technical and business projects.
       - Fields: id, name, code, description, type, status, phase, priority, start_date, deadline,
         budget_vnd, spent_vnd, progress_percent, tech_stack, team, milestones, risks, kpi
       - IMPORTANT: project `name` field contains full names (e.g. "DataPulse – Business Intelligence Dashboard").
         Always use regex for name search: {"name": {"$regex": "DataPulse", "$options": "i"}}
         Or search by `code` field (exact, uppercase): {"code": "DATAPULSE"}
    3. 'bug_tracker': Reported software/system bugs.
       - Fields: id, title, description, project_code, severity, priority, status, reporter_id,
         assignee_id, created_at, closed_at, resolution
    4. 'kpi_okr': Department OKRs.
       - Fields: id, department, year, quarter, objective, key_results
    5. 'org_chart': Reporting structure.
       - Fields: id, employee_id, role, reports_to, team_size

    --- CSV-backed (operational/transactional data) ---
    CRITICAL: All field values below are stored EXACTLY as shown (including Vietnamese text).
    Do NOT translate or guess values. Use $regex for partial/case-insensitive matching when unsure.

    6. 'attendance_october_2024': Daily employee attendance for October 2024.
       - Fields: employee_id, full_name, date (YYYY-MM-DD), day_of_week, checkin_time (HH:MM),
         checkout_time (HH:MM), work_hours, status, note
       - status ENUM: "Dung gio" = "Duc giờ", late = "Muon 20 phut" or "Muon 35 phut",
         annual leave = "Nghi phep", sick leave = "Nghi om", WFH = "Remote"
       - status exact values: "Đúng giờ", "Muộn 20 phút", "Muộn 35 phút", "Nghỉ phép", "Nghỉ ốm", "Remote"
       - To find late employees: use filter {"status": {"$regex": "Muộn"}}
       - To find employees on leave: use filter {"status": {"$in": ["Nghỉ phép", "Nghỉ ốm"]}}

    7. 'payroll_september_2024': Payroll data for September 2024.
       - Fields: employee_id, full_name, department, position, level, base_salary_gross,
         meal_allowance, transport_allowance, phone_allowance, seniority_bonus, total_gross,
         bhxh_8pct, bhyt_1_5pct, bhtn_1pct, taxable_income, personal_deduction,
         dependent_deduction, tax_base, income_tax, net_salary, month, year, status
       - status ENUM: "Đã thanh toán" (paid)

    8. 'revenue_2024': Monthly revenue and business metrics for 2024.
        - Fields: month (int 1-12), year, period (YYYY-MM), product_visionchat_starter_vnd,
          product_visionchat_business_vnd, product_visionchat_enterprise_vnd, product_datapulse_vnd,
          product_custom_ai_consulting_vnd, total_new_arr_vnd, total_expansion_arr_vnd,
          total_churn_vnd, total_mrr_vnd, total_revenue_vnd, new_customers, churned_customers,
          active_customers, avg_contract_value_vnd, cac_vnd, ltv_vnd, gross_margin_pct,
          net_revenue_retention_pct, note

    9. 'infrastructure_costs_sep2024': Cloud infrastructure costs for September 2024.
        - Fields: month, year, provider, service_category, service_name, resource_id, environment,
          project, quantity, unit, unit_cost_usd, total_cost_usd, total_cost_vnd, owner_team, note
        - service_category ENUM: "Compute", "Database", "Cache", "Storage", "Network",
          "Monitoring", "Messaging", "Security", "CI/CD", "AI Tools", "Communication",
          "Design", "Documentation", "Domain & SSL", "Password Manager", "Project Management"
        - environment ENUM: "Production", "Staging", "All"

    --- XLSX-backed (company_data.xlsx, snake_case field names) ---
    10. 'recruitment_pipeline': Candidate hiring pipeline data (CSV + XLSX merged).
        - Fields: candidate_id, full_name, position, department, level, source, apply_date,
          cv_screen_date, cv_result, round1_date, round1_type, round1_result, round1_interviewer,
          round2_date, round2_type, round2_result, round2_interviewer, round3_date, round3_type,
          round3_result, round3_interviewer, offer_date, offer_salary_gross_vnd,
          candidate_expected_vnd, offer_accepted, join_date, status, reject_reason, note
        - status ENUM: "Active", "Offer Rejected", "Joined", "Rejected"

    11. 'crm_customers': CRM customer accounts and contracts (CSV + XLSX merged).
        - Fields: customer_id, company_name, industry, tier, contact_name, contact_title,
          contact_email, contact_phone, contract_value_vnd, contract_start, contract_end,
          status, mrr_vnd, products, account_manager, city, source, health_score,
          last_activity_date, note
        - tier ENUM: "Enterprise", "Business", "Starter"
        - status ENUM: "Active", "Churned", "At Risk"

    12. 'sprint_tickets': Jira-style sprint tickets and task tracking (CSV + XLSX merged).
        - Fields: ticket_id, project, sprint, type, title, priority, assignee_id,
          assignee_name, story_points, status, created_date, start_date, resolved_date,
          label, epic, blocked, blocked_reason, review_url
        - status ENUM: "Done", "In Progress", "To Do", "Blocked"
        - priority ENUM: "High", "Medium", "Low", "Critical"

    13. 'model_registry': Internal AI/ML model registry (CSV + XLSX merged).
        - Fields: model_id, model_name, version, type, framework, task, language, base_model,
          dataset_size, train_date, trained_by, f1_score, accuracy, precision, recall,
          latency_p50_ms, latency_p99_ms, model_size_mb, serving_endpoint, deployment_env,
          status, champion, experiment_id, note
        - status ENUM: "Active", "Retired", "Staging"
        - champion: True/False — whether this is the current production champion model
        - NOTE: All "villm-*" models (villm-intent-*, villm-ner-*) belong to the VisionChat product.
          To find VisionChat NLP models, query by model_name with regex: {"model_name": {"$regex": "villm"}}
          For overall VisionChat accuracy (combined metric), also check wiki/changelog via entity_search.

    Args:
        collection (str): One of the 13 collections listed above.
        filter_json (str): A valid JSON string for the MongoDB query filter.
                           Example for late employees: '{"status": {"$regex": "Muon"}}'
        projection_json (str, optional): JSON string for field projection. Use {"_id": 0} to hide IDs.
        limit (int, optional): Max documents to return. Defaults to 100. Max is 1000.
    """
    limit = min(max(1, limit), 1000)
    try:
        db = _get_mongo_db()

        allowed = db.list_collection_names()
        if collection not in allowed:
            return f"Error: Collection '{collection}' is invalid. Allowed collections: {', '.join(allowed)}."

        query_dict = json.loads(filter_json) if filter_json else {}
        proj_dict = json.loads(projection_json) if projection_json else None
        results = list(db[collection].find(query_dict, proj_dict).limit(limit))

        for r in results:
            if "_id" in r:
                r["_id"] = str(r["_id"])

        if not results:
            return f"No records found in collection '{collection}' matching query: {filter_json}"
        return json.dumps(results, ensure_ascii=False, indent=2)

    except json.JSONDecodeError as je:
        return f"JSON Syntax Error: Ensure filter_json and projection_json are valid JSON strings. Details: {je}"
    except Exception as e:
        return f"Error querying MongoDB: {e}"


@tool
def generate_chart(
    chart_type: str,
    title: str,
    labels: List[str],
    values: List[float],
    x_label: str = "",
    y_label: str = "",
) -> str:
    """
    Render a visual chart (pie, bar, or line) directly in the chat.
    Call this tool after you have already retrieved and aggregated the data.
    Pass the final computed label strings and numeric values directly — do not pass
    column names or field references.

    Args:
        chart_type: "pie", "bar", or "line"
        title: Chart title
        labels: List of category or x-axis label strings, e.g. ["Compute", "Database", "Storage"]
        values: List of numeric values matching each label, e.g. [1500.0, 800.0, 300.0]
        x_label: X-axis label (bar/line only, optional)
        y_label: Y-axis label (bar/line only, optional)
    """
    try:
        import plotly.graph_objects as go
        import plotly.io as pio

        chart_type = chart_type.lower().strip()
        if chart_type == "pie":
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.3,
                        textinfo="label+percent",
                    )
                ]
            )
        elif chart_type == "bar":
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=labels,
                        y=values,
                        text=[f"{v:,.2f}" for v in values],
                        textposition="auto",
                    )
                ]
            )
            fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
        elif chart_type == "line":
            fig = go.Figure(
                data=[
                    go.Scatter(
                        x=labels,
                        y=values,
                        mode="lines+markers",
                        text=[f"{v:,.2f}" for v in values],
                    )
                ]
            )
            fig.update_layout(xaxis_title=x_label, yaxis_title=y_label)
        else:
            return f"Error: Unsupported chart_type '{chart_type}'. Use 'pie', 'bar', or 'line'."

        fig.update_layout(title=title, template="plotly_white")
        return f"CHART_JSON:{pio.to_json(fig)}"
    except Exception as e:
        return f"Error generating chart: {e}"
