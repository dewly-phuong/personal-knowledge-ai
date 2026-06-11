# WIKI_SCHEMA

This document defines the rules and structure for compiling raw documents into our internal wiki. Both the compiler LLM and the query agent must adhere to this specification.

---

## 1. Page Subdirectories (Classifications)

All compiled wiki pages must be stored in one of the following directories based on their classification:

* `wiki/services/{name}.md`
  * **Description**: Microservices, databases, internal apps, and third-party APIs.
  * **Content**: Purpose, owners/team, repository link, running environments, APIs, dependencies, and troubleshooting runbooks.
  * **Conventions**: Must link dependencies via `[[wiki/services/other-service]]`.
* `wiki/pipelines/{name}.md`
  * **Description**: Scheduled jobs, CI/CD pipelines, data processing workflows, and sync tasks.
  * **Content**: Sequence steps, triggers (cron/event), failure modes, rollback procedures, and related services.
  * **Conventions**: Must link to the executing or affected service.
* `wiki/concepts/{name}.md`
  * **Description**: Domain logic terms, business rules, architectural patterns, and reusable tools.
  * **Content**: Technical definition, architectural design, consumers, and related concepts.
* `wiki/decisions/{YYYY-MM-DD}-{slug}.md`
  * **Description**: Architecture Decision Records (ADRs).
  * **Content**: Context and problem statement, options considered, the chosen decision with rationale, and trade-offs.
* `wiki/person/{name}.md`
  * **Description**: Team members, subject matter experts, and owners.
  * **Content**: Contact details, expertise areas, system ownerships, and recent architecture decisions.

---

## 2. Page Structure & Front Matter

Every compiled markdown file (except `wiki/index.md` and `wiki/log.md`) must begin with a YAML front matter block containing tracking metadata:

```yaml
---
source_urls:
  - "https://github.com/org/repo/blob/main/README.md"
last_updated: "YYYY-MM-DDTHH:MM:SSZ"
entities:
  - "auth-service"
---
```

### Headings Hierarchy
- Standardize on a single `#` heading matching the canonical name of the entity.
- Use `##` and `###` for sub-sections.

---

## 3. Ingestion Rules

1. **Incremental Updates**: Do not overwrite pages completely unless content has fundamentally changed. Update sections or merge details.
2. **Backlinks**: Always add backlinks using double square brackets (e.g., `[[wiki/services/auth-service]]`) to connect pages.
3. **Contradictions**: If new ingestion sources contradict existing wiki page content:
   - Do not delete the old content immediately.
   - Insert a warning callout: `> [!WARNING] [CONFLICT: source-a says X, source-b says Y]`.
4. **Stale Pages**: If a source document or codebase is deleted, mark the page header with `[STALE]` instead of deleting the file. Do not refer to stale pages in active search indexing.
