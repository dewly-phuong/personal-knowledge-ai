import os
import threading
import torch
from typing import List, Protocol

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


_SERVICE_CACHE: dict[tuple[str, str | None], "EmbeddingService"] = {}
_SERVICE_LOCK = threading.Lock()


class EmbeddingService(Protocol):
    def embed_text(self, text: str) -> List[float]:
        """Embeds a single text string into a 768-dimensional float list."""
        ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts."""
        ...


class ModernBERTEmbeddingService:
    def __init__(self, model_name: str = "Alibaba-NLP/gte-modernbert-base"):
        """
        model_name: Hugging Face model path (default: Alibaba-NLP/gte-modernbert-base)
        """
        if not SentenceTransformer:
            raise ImportError(
                "sentence-transformers is not installed. Please run 'uv add sentence-transformers torch'"
            )

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading embedding model '{model_name}' on device '{self.device}'...")
        self.model = SentenceTransformer(
            model_name, trust_remote_code=True, device=self.device
        )
        print("Embedding model loaded successfully.")

    def embed_text(self, text: str) -> List[float]:
        """Embeds a single text string into a 768-dimensional float list."""
        if not text.strip():
            return [0.0] * 768

        # sentence-transformers returns a numpy array which we convert to list
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts."""
        if not texts:
            return []

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()


class GeminiEmbeddingService:
    def __init__(self, api_key: str = None, model_name: str = "gemini-embedding-2"):
        """
        api_key: Gemini API Key. If not provided, will read GOOGLE_API_KEY or GEMINI_API_KEY from environment.
        model_name: Name of the Gemini embedding model (default: gemini-embedding-2).
        """
        if not genai:
            raise ImportError(
                "google-genai is not installed. Please install it using 'uv add google-genai'"
            )

        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "Gemini API key must be provided or set in environment variables (GOOGLE_API_KEY or GEMINI_API_KEY)."
            )

        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    def embed_text(self, text: str) -> List[float]:
        """Embeds a single text string into a 768-dimensional float list."""
        if not text.strip():
            return [0.0] * 768

        try:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            return response.embeddings[0].values
        except Exception as e:
            raise RuntimeError(f"Gemini embedding generation failed: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of texts using types.Content wrapping to force individual document processing."""
        if not texts:
            return []

        results = [[0.0] * 768 for _ in range(len(texts))]
        non_empty_indices = []
        non_empty_contents = []

        for idx, text in enumerate(texts):
            if text.strip():
                non_empty_indices.append(idx)
                non_empty_contents.append(
                    types.Content(parts=[types.Part.from_text(text=text)])
                )

        if non_empty_contents:
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=non_empty_contents,
                    config=types.EmbedContentConfig(output_dimensionality=768),
                )
                for i, emb in enumerate(response.embeddings):
                    original_idx = non_empty_indices[i]
                    results[original_idx] = emb.values
            except Exception as e:
                raise RuntimeError(
                    f"Gemini batch embedding generation failed: {e}"
                ) from e

        return results


def get_embedding_service(api_key: str = None) -> EmbeddingService:
    """
    Factory function to instantiate and cache the embedding service.
    First tries to use GeminiEmbeddingService. If missing key, initialization error,
    or connection error, falls back to ModernBERTEmbeddingService (local).
    """
    gemini_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    cache_key = ("gemini", gemini_key) if gemini_key else ("modernbert", None)
    if service := _SERVICE_CACHE.get(cache_key):
        return service

    with _SERVICE_LOCK:
        if service := _SERVICE_CACHE.get(cache_key):
            return service
        service = _create_embedding_service(gemini_key)
        _SERVICE_CACHE[cache_key] = service
        return service


def clear_embedding_service_cache() -> None:
    with _SERVICE_LOCK:
        _SERVICE_CACHE.clear()


def _create_embedding_service(gemini_key: str | None) -> EmbeddingService:
    if gemini_key:
        try:
            print("Attempting to initialize Gemini Embedding service...")
            service = GeminiEmbeddingService(api_key=gemini_key)
            # Perform a quick verification call to ensure connectivity and key validity
            _ = service.embed_text("test")
            print("Gemini Embedding service initialized successfully.")
            return service
        except Exception as e:
            print(
                f"Failed to initialize Gemini Embedding service: {e}. Falling back to local model."
            )
    else:
        print(
            "GOOGLE_API_KEY/GEMINI_API_KEY not found in environment. Falling back to local model."
        )

    try:
        print("Initializing local ModernBERT Embedding service...")
        return ModernBERTEmbeddingService()
    except Exception as e:
        print(f"Error initializing local ModernBERT embedding service: {e}")
        raise
