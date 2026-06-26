import os


def tool_correctness_enabled() -> bool:
    value = os.getenv("SKIP_TOOL_CORRECTNESS", "").strip().lower()
    return value not in {"1", "true", "yes", "on"}
