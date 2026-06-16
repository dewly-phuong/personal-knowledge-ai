import uuid
from typing import List
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.services.embedding import EmbeddingService


class QdrantSyncManager:
    def __init__(
        self,
        url: str,
        api_key: str,
        embedding_service: EmbeddingService,
        collection_name: str = "wiki_pages",
    ):
        """
        url: Qdrant Cloud Cluster URL
        api_key: Qdrant API Key
        embedding_service: EmbeddingService instance
        collection_name: Qdrant collection name (default: wiki_pages)
        """
        self.client = QdrantClient(url=url, api_key=api_key)
        self.embedding_service = embedding_service
        self.collection_name = collection_name
        self._ensure_collection()

    def _ensure_collection(self):
        """Creates the Qdrant collection if it does not already exist."""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                print(f"Creating Qdrant collection '{self.collection_name}'...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                print("Collection created successfully.")
        except Exception as e:
            print(f"Error checking/creating Qdrant collection: {e}")

    def upsert_page(
        self, file_path: str, title: str, content: str, source_urls: List[str]
    ):
        """
        Embeds the page content and upserts the vector + payload to Qdrant Cloud.
        """
        try:
            # Extract content without YAML front matter for cleaner embeddings
            clean_content = content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    clean_content = parts[2].strip()

            # Compute embedding locally
            vector = self.embedding_service.embed_text(clean_content)

            # Generate stable UUID based on the file path to prevent duplicate point IDs
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, file_path))

            payload = {
                "path": file_path,
                "title": title,
                "content": clean_content,
                "source_urls": source_urls,
            }

            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
            print(f"  Upserted page to Qdrant: {file_path}")
        except Exception as e:
            print(f"  Error syncing {file_path} to Qdrant: {e}")
