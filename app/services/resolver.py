import google.generativeai as genai
from app.models.graph import Entity, ResolvedClusters, Cluster

class EntityResolver:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro"):
        """
        api_key: Gemini API Key
        model_name: Gemini model used for resolution (default: gemini-2.5-pro)
        """
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ResolvedClusters,
            ),
        )

    def resolve(self, entities: list[Entity]) -> ResolvedClusters:
        """
        Groups list of entities into resolved clusters with aliases and a canonical name.
        """
        if not entities:
            return ResolvedClusters(clusters=[])

        # Remove duplicate names before resolution to reduce prompt size
        unique_entities = {}
        for entity in entities:
            if entity.name not in unique_entities:
                unique_entities[entity.name] = entity
            else:
                # Append description if different
                if entity.description not in unique_entities[entity.name].description:
                    unique_entities[entity.name].description += f" / {entity.description}"

        entity_list_str = "\n".join(
            [
                f"- Name: {e.name} | Type: {e.type} | Description: {e.description}"
                for e in unique_entities.values()
            ]
        )

        prompt = f"""Below are entities extracted from several documents.
Some are different surface forms of the same real-world entity.

<entities>
{entity_list_str}
</entities>

Cluster them. Each input name must appear in exactly one cluster's aliases list.
Entities that are genuinely distinct get their own single-element cluster.
Use the descriptions to avoid merging entities that merely share a name (e.g., database instance name vs service name).
The canonical name should be the most complete, unambiguous form (e.g., 'Auth Service' instead of 'auth' or 'auth-service').

Return valid JSON matching the ResolvedClusters schema.
"""
        try:
            response = self.model.generate_content(prompt)
            return ResolvedClusters.model_validate_json(response.text)
        except Exception as e:
            print(f"Error during entity resolution: {e}")
            # Fallback: Return each unique entity in its own single-element cluster
            clusters = [
                Cluster(canonical=name, aliases=[name])
                for name in unique_entities.keys()
            ]
            return ResolvedClusters(clusters=clusters)
