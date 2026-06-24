from app.agent import SYSTEM_PROMPT


def test_system_prompt_routes_hr_collections_in_first_parallel_batch():
    assert "attendance_october_2024" in SYSTEM_PROMPT
    assert "payroll_september_2024" in SYSTEM_PROMPT
    assert "không đợi employee_id" in SYSTEM_PROMPT


def test_system_prompt_routes_board_summary_infra_in_first_parallel_batch():
    assert "board-level" in SYSTEM_PROMPT.lower()
    assert "infrastructure_costs_sep2024" in SYSTEM_PROMPT
    assert "bug_tracker" in SYSTEM_PROMPT
    assert "rủi ro vận hành" in SYSTEM_PROMPT
