"""
MongoDB query tool for structured company data.
"""

import json
import os
import threading

from langchain_core.tools import tool

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


def _run_mongo_query(
    collection: str,
    filter_json: str = "",
    projection_json: str = "",
    limit: int = 100,
) -> str:
    """Core MongoDB query logic — usable by both the tool and knowledge_search."""
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
def mongodb_query(
    collection: str, filter_json: str, projection_json: str = None, limit: int = 100
) -> str:
    """
    Query structured company data from MongoDB.

    NOTE: Prefer using `knowledge_search` instead, which combines wiki, graph, AND MongoDB
    in a single call. Use this tool directly only when you need a standalone MongoDB query
    without any wiki/graph context.

    USE WHEN: any question requiring exact numbers, records, or statistics.
    Topics: employees, headcount, salary/payroll, attendance, KPIs, OKRs, revenue, costs,
            projects, bug tracking, sprint tickets, CRM customers, AI model registry, infrastructure costs.

    DO NOT USE for qualitative explanations of how things work — use knowledge_search instead.
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
    Some CSV-backed numeric-looking values may be imported as strings in MongoDB.
    For month/year filters on CSV-backed collections, prefer string values (e.g. "9", "2024")
    or stable string fields such as period/date. If a numeric query returns no records,
    retry once with string values before concluding data is unavailable.

    6. 'attendance_october_2024': Daily employee attendance for October 2024.
       - Fields: employee_id, full_name, date (YYYY-MM-DD), day_of_week, checkin_time (HH:MM),
         checkout_time (HH:MM), work_hours, status, note
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
       - Fields: month (string "1"-"12"), year (string), period (YYYY-MM), product_visionchat_starter_vnd,
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

    Args:
        collection (str): One of the 13 collections listed above.
        filter_json (str): A valid JSON string for the MongoDB query filter.
                           Example for late employees: '{"status": {"$regex": "Muon"}}'
        projection_json (str, optional): JSON string for field projection. Use {"_id": 0} to hide IDs.
        limit (int, optional): Max documents to return. Defaults to 100. Max is 1000.
    """
    return _run_mongo_query(
        collection=collection,
        filter_json=filter_json or "",
        projection_json=projection_json or "",
        limit=limit,
    )
