import unittest
import os
from unittest.mock import patch
from dotenv import load_dotenv

from app.services.embedding import (
    GeminiEmbeddingService,
    ModernBERTEmbeddingService,
    get_embedding_service,
)


class TestEmbeddingService(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")

    def test_gemini_embedding_service_single(self):
        """Test single text embedding from GeminiEmbeddingService."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not found in .env")

        service = GeminiEmbeddingService(api_key=self.api_key)
        vector = service.embed_text("test query")

        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 768)
        self.assertTrue(all(isinstance(x, float) for x in vector))

    def test_gemini_embedding_service_empty(self):
        """Test empty string fallback to zero vector."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not found in .env")

        service = GeminiEmbeddingService(api_key=self.api_key)
        vector = service.embed_text("")
        self.assertEqual(len(vector), 768)
        self.assertEqual(vector, [0.0] * 768)

        # Test spacing string
        vector_spaces = service.embed_text("   ")
        self.assertEqual(vector_spaces, [0.0] * 768)

    def test_gemini_embedding_service_batch(self):
        """Test batch embedding from GeminiEmbeddingService."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not found in .env")

        service = GeminiEmbeddingService(api_key=self.api_key)
        texts = ["hello", "", "world"]
        vectors = service.embed_batch(texts)

        self.assertEqual(len(vectors), 3)
        self.assertEqual(len(vectors[0]), 768)
        self.assertEqual(vectors[1], [0.0] * 768)
        self.assertEqual(len(vectors[2]), 768)

    def test_get_embedding_service_fallback(self):
        """Test get_embedding_service fallback when key is missing or invalid."""
        # Use patch to simulate environment without GOOGLE_API_KEY and GEMINI_API_KEY
        with patch.dict(os.environ, {}, clear=True):
            # Since load_dotenv is called in embedding.py, patch os.environ directly
            service = get_embedding_service(api_key=None)
            self.assertIsInstance(service, ModernBERTEmbeddingService)


if __name__ == "__main__":
    unittest.main()
