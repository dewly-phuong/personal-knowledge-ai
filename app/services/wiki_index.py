import os


def generate_index_page(wiki_dir: str) -> None:
    index_path = os.path.join(wiki_dir, "index.md")
    categories = {
        "services": "Services (Microservices, Databases)",
        "pipelines": "Pipelines (Cron jobs, Workflows)",
        "concepts": "Concepts & Architectures",
        "decisions": "Architecture Decisions (ADRs)",
        "person": "People & Teams",
    }
    lines = [
        "# Internal Engineering Wiki Index\n",
        "Welcome to the compiled project knowledge base.\n",
    ]
    for folder, label in categories.items():
        _append_category(lines, wiki_dir, folder, label)
    os.makedirs(wiki_dir, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Main Wiki Index updated at: {index_path}")


def _append_category(lines: list[str], wiki_dir: str, folder: str, label: str) -> None:
    folder_path = os.path.join(wiki_dir, folder)
    if not os.path.exists(folder_path):
        return
    files = sorted([f for f in os.listdir(folder_path) if f.endswith(".md")])
    if not files:
        return
    lines.append(f"## {label}")
    for file in files:
        desc = _extract_description(os.path.join(folder_path, file))
        relative_wiki_link = f"[[wiki/{folder}/{file[:-3]}]]"
        lines.append(
            f"* {relative_wiki_link} - {desc}" if desc else f"* {relative_wiki_link}"
        )
    lines.append("")


def _extract_description(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return ""
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]
    for line in body.split("\n"):
        line_clean = line.strip()
        if line_clean and not line_clean.startswith(("#", "[")):
            return line_clean[:77] + "..." if len(line_clean) > 80 else line_clean
    return ""
