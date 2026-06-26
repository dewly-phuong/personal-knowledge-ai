from app.agent import SYSTEM_PROMPT


def test_system_prompt_requires_general_knowledge_search():
    assert "knowledge_search" in SYSTEM_PROMPT
    assert "searches every configured knowledge source in parallel" in SYSTEM_PROMPT
    assert "call `knowledge_search` before answering" in SYSTEM_PROMPT


def test_system_prompt_describes_normalized_source_statuses():
    assert "status `ok`, `empty`, or `error`" in SYSTEM_PROMPT
    assert "data = null" in SYSTEM_PROMPT
    assert "Do not invent or estimate missing internal data" in SYSTEM_PROMPT


def test_system_prompt_does_not_use_specific_dataset_names():
    private_dataset_names = [
        "VisionChat",
        "NLU Service",
        "DataPulse",
        "AI Research",
        "Phòng Kỹ thuật",
        "revenue_2024",
        "infrastructure_costs_sep2024",
        "bug_tracker",
        "payroll_september_2024",
        "attendance_october_2024",
        "sprint_tickets",
        "kpi_okr",
        "model_registry",
        "filter_json",
    ]

    for name in private_dataset_names:
        assert name not in SYSTEM_PROMPT
