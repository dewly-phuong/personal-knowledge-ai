from app.agent import SYSTEM_PROMPT


def _parallel_requirements_block():
    return SYSTEM_PROMPT.split("<parallel_requirements>", 1)[1].split(
        "</parallel_requirements>", 1
    )[0]


def test_system_prompt_routes_hr_collections_in_first_parallel_batch():
    block = _parallel_requirements_block()

    assert "staff_directory" in block
    assert "compensation_runs_2026_03" in block
    assert "workday_status_2026_04" in block
    assert "không đợi employee_id" in block


def test_system_prompt_routes_board_summary_infra_in_first_parallel_batch():
    block = _parallel_requirements_block()

    assert "executive-level" in block.lower()
    assert "cloud_spend_2026_03" in block
    assert "incident_log" in block
    assert "rủi ro vận hành" in block


def test_parallel_requirements_examples_do_not_use_private_dataset_names():
    block = _parallel_requirements_block()
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
    ]

    for name in private_dataset_names:
        assert name not in block
