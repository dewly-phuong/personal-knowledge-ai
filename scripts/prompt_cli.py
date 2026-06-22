#!/usr/bin/env python3
"""Manage versioned system prompts in MongoDB.

Usage:
  python scripts/prompt_cli.py seed                      # import SYSTEM_PROMPT from agent.py
  python scripts/prompt_cli.py list
  python scripts/prompt_cli.py save --label "v2" --note "added rule X"
  python scripts/prompt_cli.py rollback --version 3
  python scripts/prompt_cli.py show --version 3
"""
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
_DB_NAME = "personal_knowledge_ai"
_COL = "system_prompts"


def _col():
    return MongoClient(_MONGO_URI, serverSelectionTimeoutMS=5000)[_DB_NAME][_COL]


def cmd_seed(args):
    from app.agent import SYSTEM_PROMPT
    col = _col()
    if col.find_one({}):
        print("Prompts already exist. Use 'save' to add a new version.")
        sys.exit(1)
    col.insert_one({
        "version": 1,
        "content": SYSTEM_PROMPT,
        "label": args.label or "initial",
        "note": "seeded from agent.py",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    })
    print("Seeded v1 [ACTIVE]")


def cmd_list(_args):
    docs = list(_col().find({}, {"content": 0}).sort("version", -1))
    if not docs:
        print("No prompts stored.")
        return
    for d in docs:
        active = " [ACTIVE]" if d.get("is_active") else ""
        ts = d["created_at"].strftime("%Y-%m-%d %H:%M") if "created_at" in d else "?"
        label = f"  {d.get('label', '')}" if d.get("label") else ""
        note = f"  # {d['note']}" if d.get("note") else ""
        print(f"v{d['version']}{active}  {ts}{label}{note}")


def cmd_save(args):
    col = _col()
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        print("Paste/type the prompt. End with a line containing only END:")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        content = "\n".join(lines)

    last = col.find_one({}, sort=[("version", -1)])
    version = (last["version"] + 1) if last else 1
    col.update_many({"is_active": True}, {"$set": {"is_active": False}})
    col.insert_one({
        "version": version,
        "content": content,
        "label": args.label or "",
        "note": args.note or "",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    })
    print(f"Saved as v{version} [ACTIVE]")


def cmd_rollback(args):
    col = _col()
    doc = col.find_one({"version": args.version})
    if not doc:
        print(f"v{args.version} not found.")
        sys.exit(1)
    col.update_many({"is_active": True}, {"$set": {"is_active": False}})
    col.update_one({"version": args.version}, {"$set": {"is_active": True}})
    print(f"Rolled back to v{args.version}")


def cmd_show(args):
    col = _col()
    doc = col.find_one({"version": args.version} if args.version else {"is_active": True})
    if not doc:
        print("Not found.")
        sys.exit(1)
    print(f"--- v{doc['version']} {'[ACTIVE]' if doc.get('is_active') else ''} ---")
    print(doc["content"])


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sd = sub.add_parser("seed")
    sd.add_argument("--label", default="initial")

    sub.add_parser("list")

    s = sub.add_parser("save")
    s.add_argument("--label", default="")
    s.add_argument("--note", default="")
    s.add_argument("--file", default=None, help="path to prompt file (txt/md)")

    r = sub.add_parser("rollback")
    r.add_argument("--version", type=int, required=True)

    sh = sub.add_parser("show")
    sh.add_argument("--version", type=int, default=None)

    args = p.parse_args()
    {"seed": cmd_seed, "list": cmd_list, "save": cmd_save, "rollback": cmd_rollback, "show": cmd_show}[args.cmd](args)


if __name__ == "__main__":
    main()
