import os
import re
import datetime
import google.generativeai as genai

class WikiCompiler:
    def __init__(self, api_key: str, wiki_dir: str = "wiki", model_name: str = "gemini-2.5-flash"):
        """
        api_key: Gemini API Key
        wiki_dir: Root directory of wiki files (default: wiki)
        model_name: Model used for compilation (default: gemini-2.5-flash)
        """
        self.wiki_dir = wiki_dir
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
        # Read WIKI_SCHEMA if it exists in the workspace
        schema_path = "WIKI_SCHEMA.md"
        if os.path.exists(schema_path):
            try:
                with open(schema_path, "r", encoding="utf-8") as f:
                    self.schema_content = f.read()
            except Exception:
                self.schema_content = self._default_schema()
        else:
            self.schema_content = self._default_schema()

    def _default_schema(self) -> str:
        return "Adhere to standard Markdown, front matter, and internal linking double bracket conventions [[wiki/category/page-slug]]."

    def _get_entity_slug(self, name: str) -> str:
        """Converts entity name to a slug (lowercase, dashes)."""
        slug = name.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "-", slug)
        return slug

    def _get_entity_path(self, name: str, entity_type: str) -> str:
        """Maps entity to its markdown path under the wiki directory structure."""
        slug = self._get_entity_slug(name)
        type_folder = {
            "SERVICE": "services",
            "PIPELINE": "pipelines",
            "CONCEPT": "concepts",
            "ARTIFACT": "decisions",
            "DATABASE": "services",
            "PERSON": "person",
            "ORGANIZATION": "person",
        }.get(entity_type, "concepts")
        
        return os.path.join(self.wiki_dir, type_folder, f"{slug}.md")

    def compile_entity_page(
        self,
        entity_name: str,
        entity_type: str,
        raw_doc_content: str,
        source_url: str,
    ) -> tuple[str, str]:
        """
        Creates or updates a wiki page for the given entity, merging new details from raw_doc_content.
        Returns (file_path, compiled_markdown).
        """
        file_path = self._get_entity_path(entity_name, entity_type)
        existing_content = ""
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            except Exception as e:
                print(f"Error reading existing page {file_path}: {e}")

        date_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        prompt = f"""You are a disciplined wiki maintainer. Read and strictly follow the schema:
<wiki_schema>
{self.schema_content}
</wiki_schema>

You need to compile or merge information for the entity:
- Entity Name: {entity_name}
- Entity Type: {entity_type}

New document to ingest details from:
<document>
{raw_doc_content}
<source_url>{source_url}</source_url>
</document>

Existing wiki page content (if any, empty if new page):
<existing_page>
{existing_content}
</existing_page>

Tasks:
1. Merge the new details from the document into the existing page content. Do not drop existing information unless it is directly contradicted by the new source.
2. If this is a new page, write a clean, well-formatted markdown file following the schema.
3. Ensure the YAML front matter block is present at the absolute top of the page. It must track the source URLs and last updated timestamp:
---
source_urls:
  - "{source_url}"
last_updated: "{date_str}"
entities:
  - "{self._get_entity_slug(entity_name)}"
---
If updating an existing page, merge the new `source_url` into the list (ensuring no duplicates) and update `last_updated`.
4. Add [[wiki/category/slug]] backlinks for other related entities mentioned on this page.
5. If there is a direct contradiction between the new document and existing content, do not delete the old content; instead, insert a warning callout like:
> [!WARNING] [CONFLICT: source-a says X, source-b says Y]

Output only the complete, valid raw markdown code block contents (no surrounding markdown code blocks like ```markdown ... ```, just start directly with the YAML front matter `---`).
"""
        try:
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            
            # Clean any surrounding triple backticks the model might output
            if content.startswith("```markdown"):
                content = content[11:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            # Write to file
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return file_path, content
        except Exception as e:
            print(f"Error compiling entity page {entity_name}: {e}")
            return file_path, existing_content

    def generate_index_page(self):
        """
        Scans the wiki folder and programmatically generates the wiki/index.md page.
        """
        index_path = os.path.join(self.wiki_dir, "index.md")
        
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
            folder_path = os.path.join(self.wiki_dir, folder)
            if os.path.exists(folder_path):
                files = sorted([f for f in os.listdir(folder_path) if f.endswith(".md")])
                if files:
                    lines.append(f"## {label}")
                    for file in files:
                        file_path = os.path.join(folder_path, file)
                        title = file[:-3].replace("-", " ").title()
                        desc = ""
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                text = f.read()
                                h1_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
                                if h1_match:
                                    title = h1_match.group(1).strip()
                                
                                body = text
                                if text.startswith("---"):
                                    parts = text.split("---", 2)
                                    if len(parts) >= 3:
                                        body = parts[2]
                                for line in body.split("\n"):
                                    line_clean = line.strip()
                                    if (
                                        line_clean
                                        and not line_clean.startswith("#")
                                        and not line_clean.startswith("[")
                                    ):
                                        desc = line_clean
                                        if len(desc) > 80:
                                            desc = desc[:77] + "..."
                                        break
                        except Exception:
                            pass
                        
                        relative_wiki_link = f"[[wiki/{folder}/{file[:-3]}]]"
                        if desc:
                            lines.append(f"* {relative_wiki_link} - {desc}")
                        else:
                            lines.append(f"* {relative_wiki_link}")
                    lines.append("")
        
        os.makedirs(self.wiki_dir, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Main Wiki Index updated at: {index_path}")
