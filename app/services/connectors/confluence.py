import datetime
import re
from app.services.connectors.base import BaseConnector, Document

try:
    from atlassian import Confluence
except ImportError:
    Confluence = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

class ConfluenceConnector(BaseConnector):
    def __init__(self, url: str, username: str, token: str, space_key: str):
        """
        url: Confluence instance URL (e.g. https://your-domain.atlassian.net)
        username: Confluence login email
        token: Confluence API token
        space_key: Key of the space to fetch
        """
        self.url = url.rstrip("/") if url else ""
        self.username = username
        self.token = token
        self.space_key = space_key

    def fetch_documents(self) -> list[Document]:
        documents = []
        if not Confluence:
            print("atlassian-python-api is not installed.")
            return documents
        if not self.url or not self.space_key:
            return documents

        try:
            confluence = Confluence(
                url=self.url,
                username=self.username,
                password=self.token,
                cloud=True,
            )

            # Fetch pages up to a limit of 100 pages
            pages = confluence.get_all_pages_from_space(
                self.space_key, start=0, limit=100, expand="body.storage,version,history"
            )

            for page in pages:
                page_id = page.get("id")
                title = page.get("title")

                # Get detailed body
                body_storage = page.get("body", {}).get("storage", {}).get("value", "")
                
                # HTML tag stripping
                if BeautifulSoup:
                    soup = BeautifulSoup(body_storage, "html.parser")
                    content_text = soup.get_text(separator="\n")
                else:
                    # Fallback simple regex stripping if bs4 is missing
                    content_text = re.sub("<[^<]+?>", "", body_storage)

                # Get last update timestamp
                history = page.get("history", {})
                last_updated = history.get("lastUpdated", {}).get("when")
                if not last_updated:
                    last_updated = datetime.datetime.now(datetime.timezone.utc).isoformat()

                # Source URL construct
                source_url = f"{self.url}/wiki/spaces/{self.space_key}/pages/{page_id}"
                
                # Path construct
                safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
                path = f"{self.space_key}/{safe_title}.md"

                documents.append(
                    Document(
                        content=f"# {title}\n\n{content_text}",
                        source_url=source_url,
                        path=path,
                        source_type="confluence",
                        last_modified=last_updated,
                    )
                )
        except Exception as e:
            print(f"Error fetching documents from Confluence: {e}")

        return documents
