"""
Citation resolution for Chainlit responses.

Parses [Nguồn: wiki/...] markers, reads front matter of cited wiki files,
and replaces them with clickable source URLs.
"""

import os
import re


def resolve_citations(text: str) -> str:
    """
    Parses references like [Nguồn: wiki/services/auth-service.md] in the text,
    reads the front matter of the cited file, and replaces it with its original
    clickable source URL (e.g. Confluence/GitHub link).
    """
    pattern = r"\[Nguồn:\s*(wiki/[^\]]+)\]"
    matches = re.findall(pattern, text)

    for rel_path in matches:
        abs_path = os.path.abspath(rel_path)
        if not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            source_url = None
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    yaml_text = parts[1]
                    doc_match = re.search(r"source_docs:\s*\[(.*?)\]", yaml_text)
                    if doc_match:
                        urls = [
                            u.strip().strip("'").strip('"')
                            for u in doc_match.group(1).split(",")
                            if u.strip()
                        ]
                        if urls:
                            source_url = urls[0]

            if source_url:
                basename = os.path.basename(rel_path)
                replacement = f"[Nguồn: {basename}]({source_url})"
                text = text.replace(f"[Nguồn: {rel_path}]", replacement)
        except Exception as e:
            print(f"Error parsing front matter for {rel_path}: {e}")

    return text
