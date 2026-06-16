import os
import datetime
from pathlib import Path
from app.services.connectors.base import BaseConnector, Document


class LocalFilesConnector(BaseConnector):
    def __init__(self, directory_path: str):
        self.directory_path = Path(directory_path).resolve()

    def fetch_documents(self) -> list[Document]:
        documents = []
        if not self.directory_path.exists():
            return documents

        for root, _, files in os.walk(self.directory_path):
            for file in files:
                if file.endswith((".md", ".txt")):
                    file_path = Path(root) / file
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        stat = file_path.stat()
                        mtime = datetime.datetime.fromtimestamp(
                            stat.st_mtime, datetime.timezone.utc
                        )
                        last_modified = mtime.isoformat()

                        relative_path = file_path.relative_to(self.directory_path)

                        documents.append(
                            Document(
                                content=content,
                                source_url=file_path.as_uri(),
                                path=str(relative_path),
                                source_type="local",
                                last_modified=last_modified,
                            )
                        )
                    except Exception as e:
                        # Log error and skip file
                        print(f"Error reading file {file_path}: {e}")

        return documents
