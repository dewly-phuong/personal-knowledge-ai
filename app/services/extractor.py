import google.generativeai as genai
from app.models.graph import ExtractedGraph


class GraphExtractor:
    def __init__(self, api_key: str):
        """
        api_key: Gemini API Key
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ExtractedGraph,
            ),
        )

    def extract(self, document_content: str) -> ExtractedGraph:
        """
        Extracts entities and relations from document text.
        """
        if not document_content.strip():
            return ExtractedGraph(entities=[], relations=[])

        prompt = f"""Extract a knowledge graph from the document below.

<document>
{document_content}
</document>

Guidelines:
- Extract only entities that are central to what this document is about — skip incidental mentions.
- For each entity, write a one-sentence description grounded in this document.
  Descriptions are used later to disambiguate entities with similar names.
- Predicates should be short verb phrases (e.g., "depends on", "owned by", "deployed to").
- Every relation must connect two entities you extracted.
- For internal docs: SERVICE và PIPELINE entities quan trọng nhất.

Return valid JSON matching the ExtractedGraph schema.
"""
        try:
            response = self.model.generate_content(prompt)
            # Parse and validate the response
            return ExtractedGraph.model_validate_json(response.text)
        except Exception as e:
            print(f"Error during graph extraction: {e}")
            # Fallback returning empty graph
            return ExtractedGraph(entities=[], relations=[])
