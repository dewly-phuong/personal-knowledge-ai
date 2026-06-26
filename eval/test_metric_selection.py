import importlib


def test_tool_correctness_can_be_disabled_by_env(monkeypatch):
    monkeypatch.setenv("SKIP_TOOL_CORRECTNESS", "1")

    metric_selection = importlib.import_module("eval.metric_selection")

    assert metric_selection.tool_correctness_enabled() is False


def test_tool_correctness_enabled_by_default(monkeypatch):
    monkeypatch.delenv("SKIP_TOOL_CORRECTNESS", raising=False)

    metric_selection = importlib.import_module("eval.metric_selection")

    assert metric_selection.tool_correctness_enabled() is True
