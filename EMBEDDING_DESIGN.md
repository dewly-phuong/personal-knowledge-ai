# Embedding Service Upgrade: Gemini Embedding 2 with Auto-Fallback

## Understanding Summary
* **What is being built**: Integration of the new `gemini-embedding-2` model as the primary embedding service using the modern `google-genai` SDK.
* **Why it exists**: To replace the local GTE-ModernBERT model with a powerful, remote Google Gemini embedding service, improving stability, scalability, and ease of deployment.
* **Who it is for**: Developers and users of the Personal Knowledge AI application.
* **Key constraints**:
  * Use the new `google-genai` SDK instead of the deprecated `google.generativeai` package for this service.
  * Retrieve 768-dimensional embeddings to match the existing Qdrant collection config.
  * Keep implementation clean and modular, maintaining integration with Qdrant sync and ingestion CLI commands.
* **Explicit non-goals**:
  * Upgrading/modifying the existing extraction/synthesis steps that currently use the legacy `google.generativeai` SDK (unless required).
  * Supporting multiple arbitrary embedding models simultaneously for Qdrant sync.

## Assumptions
1. **API Credentials**: The existing `GOOGLE_API_KEY` (configured in `.env`) has access to the new `gemini-embedding-2` model.
2. **Dimension Compatibility**: We will restrict the Gemini Embedding 2 dimension to 768 using the SDK's `output_dimensionality=768` parameter.
3. **Dependencies**: `google-genai` is already installed in the `.venv` virtual environment and is ready to be imported and used.

## Decision Log
1. **Model Selection**: Selected `gemini-embedding-2` via the new `google-genai` SDK.
2. **Dimension Matching**: Restricted Gemini embeddings to 768 dimensions (`output_dimensionality=768`) to match the existing Qdrant collection size.
3. **Architecture Approach**: Configurable dual-provider architecture using environment variables.
4. **Fallback Strategy**: `get_embedding_service` will attempt to initialize and use `GeminiEmbeddingService` by default. If initialization fails (e.g., missing API key or offline status), it will automatically fall back to `ModernBERTEmbeddingService`.

## Final Design

### 1. Interface / Protocol Definition
We define a protocol class `EmbeddingService` in `app/services/embedding.py`:
```python
from typing import List, Protocol

class EmbeddingService(Protocol):
    def embed_text(self, text: str) -> List[float]:
        ...
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        ...
```

### 2. GeminiEmbeddingService Implementation
We create `GeminiEmbeddingService` inside `app/services/embedding.py` which:
- Dynamically imports `google.genai` and `google.genai.types`.
- Configures a Client using `GOOGLE_API_KEY`.
- Specifies `output_dimensionality=768` in the `EmbedContentConfig`.
- Gracefully handles empty texts by returning a list of 768 zeros.

### 3. Factory Function & Fallback
We implement `get_embedding_service()`:
- Tries to fetch `GOOGLE_API_KEY` from the environment.
- Tries to instantiate `GeminiEmbeddingService` and perform a quick check.
- If unsuccessful or key is missing, logs a warning and returns `ModernBERTEmbeddingService` (local GTE-ModernBERT).

### 4. Integration
Update `ingest.py` and `app/services/qdrant_sync.py` to use `get_embedding_service()`.
