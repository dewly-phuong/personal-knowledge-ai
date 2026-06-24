"""
Shared Gemini judge model for DeepEval metrics.
Used by generate_datasets.py, test_single_turn.py, test_multi_turn.py.
"""

import os

from deepeval.models.base_model import DeepEvalBaseLLM


class GeminiJudge(DeepEvalBaseLLM):
    """Thin wrapper around ChatGoogleGenerativeAI (gemini-2.5-flash) for DeepEval."""

    def __init__(self):
        self._model = None
        super().__init__()

    def load_model(self):
        if self._model is None:
            from langchain_google_genai import ChatGoogleGenerativeAI

            self._model = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0,
                google_api_key=os.getenv("GOOGLE_API_KEY"),
            )
        return self._model

    def generate(self, prompt: str, schema=None):
        m = self.load_model()
        if schema is not None:
            return m.with_structured_output(schema).invoke(prompt)
        return m.invoke(prompt).content

    async def a_generate(self, prompt: str, schema=None):
        import asyncio

        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return "gemini-2.5-flash"
