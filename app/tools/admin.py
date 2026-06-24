"""
Admin / maintenance tools: lint_wiki.
"""

import datetime
import os
import re
from typing import Dict, List

from langchain_core.tools import tool


@tool
def lint_wiki() -> str:
    """
    Audits the wiki pages for consistency, orphans, and conflict tags.
    Returns a markdown health audit report.
    """
    wiki_dir = "wiki"
    if not os.path.exists(wiki_dir):
        return "Wiki directory does not exist. No files to audit."

    pages = [
        os.path.join(root, fname)
        for root, _, files in os.walk(wiki_dir)
        for fname in files
        if fname.endswith(".md")
    ]

    conflict_pages: List[str] = []
    incoming: Dict[str, List[str]] = {os.path.normpath(p): [] for p in pages}
    outgoing: Dict[str, List[str]] = {os.path.normpath(p): [] for p in pages}

    for page in pages:
        norm_page = os.path.normpath(page)
        try:
            with open(page, "r", encoding="utf-8") as f:
                content = f.read()
            if "[CONFLICT]" in content:
                conflict_pages.append(page)
            for link in re.findall(r"\[\[([^\]]+)\]\]", content):
                slug = link.lower().strip().replace(" ", "-")
                for p in pages:
                    if os.path.splitext(os.path.basename(p))[0] == slug:
                        target = os.path.normpath(p)
                        outgoing[norm_page].append(target)
                        if target in incoming:
                            incoming[target].append(norm_page)
                        break
        except Exception:
            pass

    orphan_pages = [
        p
        for p in pages
        if os.path.basename(p) not in ("index.md", "log.md")
        and not incoming.get(os.path.normpath(p))
    ]

    report = [
        "# Wiki Health Audit Report",
        f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Wiki Pages Audited: {len(pages)}",
        "",
        "## Conflict Tags",
    ]
    if conflict_pages:
        report.append(
            "The following pages contain active `[CONFLICT]` tags that require manual resolution:"
        )
        report.extend(
            f"- [{os.path.basename(cp)}](file://{os.path.abspath(cp)})"
            for cp in conflict_pages
        )
    else:
        report.append("✅ No pages with active `[CONFLICT]` tags found.")
    report += ["", "## Orphan Pages"]
    if orphan_pages:
        report.append(
            "The following pages are not linked from any other page in the wiki:"
        )
        report.extend(
            f"- [{os.path.basename(op)}](file://{os.path.abspath(op)})"
            for op in orphan_pages
        )
    else:
        report.append("✅ No orphan pages found.")
    report.append("")
    return "\n".join(report)
