from __future__ import annotations

import argparse
import pathlib
from typing import Any

from eval.production_feedback import (
    candidate_regressions_from_feedback,
    read_documents_file,
    write_candidates_jsonl,
)


DEFAULT_OUT = pathlib.Path("eval/datasets/production_regression_candidates.jsonl")
DEFAULT_DB = "personal_knowledge_ai"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mongo_uri:
        feedbacks, steps = _load_chainlit_docs_from_mongo(
            args.mongo_uri,
            args.mongo_db,
            limit=args.limit,
        )
    else:
        if not args.feedbacks or not args.steps:
            raise SystemExit("--feedbacks and --steps are required without --mongo-uri")
        feedbacks = read_documents_file(pathlib.Path(args.feedbacks))
        steps = read_documents_file(pathlib.Path(args.steps))

    traces = read_documents_file(pathlib.Path(args.traces)) if args.traces else []
    candidates = candidate_regressions_from_feedback(
        feedbacks,
        steps,
        traces,
        limit=args.limit,
    )
    out = pathlib.Path(args.out)
    write_candidates_jsonl(out, candidates)
    print(f"Wrote {len(candidates)} regression candidates to {out}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export low-rated or commented Chainlit feedback into eval regression "
            "candidate JSONL."
        )
    )
    parser.add_argument("--feedbacks", help="Local cl_feedbacks JSON/JSONL export")
    parser.add_argument("--steps", help="Local cl_steps JSON/JSONL export")
    parser.add_argument("--traces", help="Optional Langfuse/eval traces JSON/JSONL export")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help=f"Output path, default {DEFAULT_OUT}")
    parser.add_argument(
        "--mongo-uri",
        default=None,
        help="Read cl_feedbacks and cl_steps directly from MongoDB",
    )
    parser.add_argument("--mongo-db", default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=100)
    return parser


def _load_chainlit_docs_from_mongo(
    mongo_uri: str,
    mongo_db: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from pymongo import MongoClient

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[mongo_db]
    feedbacks = list(db["cl_feedbacks"].find({}, {"_id": 0}).limit(limit * 5))
    thread_ids = sorted(
        {feedback.get("threadId") for feedback in feedbacks if feedback.get("threadId")}
    )
    if not thread_ids:
        return feedbacks, []
    steps = list(
        db["cl_steps"]
        .find({"threadId": {"$in": thread_ids}}, {"_id": 0})
        .sort("createdAt", 1)
    )
    return feedbacks, steps


if __name__ == "__main__":
    raise SystemExit(main())
