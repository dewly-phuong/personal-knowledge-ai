"""
Generate synthetic golden datasets.

Run once before eval tests:
    uv run python eval/generate_datasets.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from eval.dataset_generation import generate_multi_turn, generate_single_turn  # noqa: E402
from eval.judge import GeminiJudge  # noqa: E402

DATASETS_DIR = Path(__file__).parent / "datasets"


def _build_synthesizer(judge):
    from deepeval.synthesizer import Synthesizer
    from deepeval.synthesizer.config import StylingConfig

    return Synthesizer(
        model=judge,
        async_mode=False,
        styling_config=StylingConfig(
            scenario=(
                "Nhân viên hoặc developer tại TechVision AI đang hỏi trợ lý AI nội bộ "
                "về hệ thống, kiến trúc kỹ thuật, chính sách HR, hoặc quy trình công ty."
            ),
            task=(
                "Trả lời các câu hỏi thực tế cụ thể về dịch vụ, hạ tầng, chính sách "
                "và pipeline của TechVision AI."
            ),
            input_format=(
                "Một câu hỏi ngắn gọn bằng tiếng Việt về một sự kiện cụ thể, "
                "chi tiết kỹ thuật, hoặc quy định tại TechVision AI."
            ),
            expected_output_format=(
                "Câu trả lời chính xác, thực tế bằng tiếng Việt, có trích dẫn nguồn tài liệu, "
                "hệ thống, hoặc mục chính sách liên quan."
            ),
        ),
    )


def _write_json(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate eval golden datasets.")
    parser.add_argument("--single", type=int, default=20)
    parser.add_argument("--multi", type=int, default=20)
    args = parser.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    judge = GeminiJudge()

    single_records = generate_single_turn(_build_synthesizer(judge), n=args.single)
    st_path = DATASETS_DIR / "single_turn_goldens.json"
    _write_json(st_path, single_records)
    print(f"Saved {len(single_records)} single-turn goldens → {st_path}")

    multi_records = generate_multi_turn(judge, n=args.multi)
    mt_path = DATASETS_DIR / "multi_turn_goldens.json"
    _write_json(mt_path, multi_records)
    print(f"Saved {len(multi_records)} multi-turn goldens → {mt_path}")


if __name__ == "__main__":
    main()
