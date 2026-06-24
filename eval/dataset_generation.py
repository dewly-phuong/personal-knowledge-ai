import sys
from pathlib import Path
from typing import List

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from eval._scenarios import (  # noqa: E402
    ENTITY_SOURCE_FILES,
    KNOWN_ENTITIES,
    MONGODB_KEYWORDS,
    MT_SCENARIOS,
    WIKI_DOCS,
)


def classify_tools(input_text: str, source_file: str) -> list[dict]:
    text_lower = input_text.lower()
    if any(keyword in text_lower for keyword in MONGODB_KEYWORDS):
        return [{"name": "mongodb_query"}]

    fname = Path(source_file).name
    if fname in ENTITY_SOURCE_FILES or any(e in text_lower for e in KNOWN_ENTITIES):
        return [{"name": "entity_search"}]
    return [{"name": "wiki_search"}]


def classify_multi_turn_tools(input_text: str) -> list[dict]:
    text_lower = input_text.lower()
    tools: list[str] = []

    if any(e in text_lower for e in KNOWN_ENTITIES) or any(
        keyword in text_lower
        for keyword in [
            "bot-engine",
            "knowledge-base-indexer",
            "nlu service",
            "rag engine",
            "response generator",
            "datapulse",
            "hotfix",
            "visionchat",
            "okr q3",
            "incident p1",
        ]
    ):
        tools.append("entity_search")

    if any(keyword in text_lower for keyword in MONGODB_KEYWORDS) or any(
        keyword in text_lower
        for keyword in [
            "active",
            "assignee",
            "aws costs",
            "budget",
            "candidate",
            "churn",
            "client",
            "completion",
            "contract",
            "cost",
            "customer",
            "deadline",
            "enterprise",
            "gross margin",
            "health data",
            "implementation",
            "mrr",
            "nps",
            "operational costs",
            "progress",
            "python developer",
            "score",
            "sessions",
            "sprint",
            "ticket",
            "velocity",
        ]
    ):
        tools.append("mongodb_query")

    if not tools and any(
        keyword in text_lower
        for keyword in [
            "ci/cd",
            "leave",
            "nghỉ phép",
            "phòng nhân sự",
            "policy",
            "policies",
            "process",
            "quy trình",
            "wfh",
            "work from home",
        ]
    ):
        tools.append("wiki_search")

    if not tools and not any(
        keyword in text_lower
        for keyword in ["thank", "cảm ơn", "thanks", "okay", "understand"]
    ):
        tools.append("wiki_search")

    return [{"name": name} for name in dict.fromkeys(tools)]


def generate_single_turn(synthesizer, n: int = 5) -> list[dict]:
    contexts, sources = chunk_docs()
    per_ctx = max(2, -(-n // len(contexts)))
    print(f"Generating ~{per_ctx} goldens per context from {len(contexts)} docs ...")
    goldens = synthesizer.generate_goldens_from_contexts(
        contexts=contexts,
        source_files=sources,
        include_expected_output=True,
        max_goldens_per_context=per_ctx,
    )
    print(f"Generated {len(goldens)} single-turn goldens")
    return [_single_turn_record(i, golden) for i, golden in enumerate(goldens, 1)]


def generate_multi_turn(
    judge, n: int = 5, max_turns_per_scenario: int = 5
) -> list[dict]:
    from deepeval.dataset import ConversationalGolden
    from deepeval.simulator import ConversationSimulator

    scenarios = MT_SCENARIOS[:n]
    if len(scenarios) < n:
        print(f"Warning: only {len(MT_SCENARIOS)} scenarios defined.")
    goldens = [
        ConversationalGolden(
            scenario=s["scenario"],
            expected_outcome=s["expected_outcome"],
            user_description=s["user_description"],
        )
        for s in scenarios
    ]
    print(
        f"Simulating {len(goldens)} multi-turn conversations "
        f"(max {max_turns_per_scenario} turns each) ..."
    )
    simulator = ConversationSimulator(
        model_callback=make_agent_callback(),
        simulator_model=judge,
        async_mode=False,
    )
    test_cases = simulator.simulate(
        conversational_goldens=goldens,
        max_user_simulations=max_turns_per_scenario,
    )
    print(f"Simulated {len(test_cases)} conversations")
    return [
        _multi_turn_record(i, test_case, spec)
        for i, (test_case, spec) in enumerate(zip(test_cases, scenarios), 1)
    ]


def chunk_docs(chunk_size: int = 1200) -> tuple[list[list[str]], list[str]]:
    contexts, sources = [], []
    for path in WIKI_DOCS:
        text = Path(path).read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3 :].strip()
        contexts.append(
            [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
        )
        sources.append(path)
    return contexts, sources


def make_agent_callback():
    from app.agent import create_conversational_agent
    from app.tools import pop_retrieval_capture, start_retrieval_capture
    from deepeval.test_case import Turn

    agent = create_conversational_agent()

    def model_callback(input: str, turns: List[Turn]) -> Turn:
        messages = [{"role": turn.role, "content": turn.content} for turn in turns]
        start_retrieval_capture()
        result = agent.invoke({"messages": messages})
        retrieval_ctx = pop_retrieval_capture()
        for msg in reversed(result.get("messages", [])):
            if type(msg).__name__ == "AIMessage":
                content = _message_content(msg)
                if content:
                    return Turn(
                        role="assistant",
                        content=content,
                        retrieval_context=retrieval_ctx or None,
                    )
        return Turn(
            role="assistant", content="", retrieval_context=retrieval_ctx or None
        )

    return model_callback


def _single_turn_record(index: int, golden) -> dict:
    source_files = (golden.additional_metadata or {}).get("context_source_files", [])
    source_file = source_files[0] if source_files else ""
    return {
        "id": f"ST{index:03d}",
        "input": golden.input,
        "expected_output": golden.expected_output,
        "context": golden.context or [],
        "additional_metadata": golden.additional_metadata or {},
        "expected_tools": classify_tools(golden.input, source_file),
    }


def _multi_turn_record(index: int, test_case, spec: dict) -> dict:
    return {
        "id": f"MT{index:03d}",
        "scenario": spec["scenario"],
        "expected_outcome": spec["expected_outcome"],
        "user_description": spec["user_description"],
        "turns": [
            {
                "role": turn.role,
                "content": turn.content,
                "retrieval_context": turn.retrieval_context or [],
                "expected_tools": classify_multi_turn_tools(turn.content)
                if turn.role == "user"
                else [],
            }
            for turn in (test_case.turns or [])
        ],
    }


def _message_content(msg) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return content
