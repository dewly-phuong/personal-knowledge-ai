import os

from app.services.connectors import (
    ConfluenceConnector,
    GitHubConnector,
    LocalFilesConnector,
)
from app.services.connectors.base import BaseConnector
from app.services.markitdown_converter import convert_office_files


def build_connector(
    source: str,
    dir_path: str | None = None,
    repo_name: str | None = None,
    space_key: str | None = None,
) -> BaseConnector:
    if source == "office":
        if not dir_path:
            raise ValueError("--dir is required for office source.")
        print("Converting office/PDF files to Markdown via MarkItDown...")
        conv = convert_office_files(src_dir=dir_path)
        print(
            f"Conversion result: converted={len(conv['converted'])} "
            f"skipped={len(conv['skipped'])} failed={len(conv['failed'])}"
        )
        for path in conv["failed"]:
            print(f"  [failed] {path}")
        return LocalFilesConnector(directory_path=os.path.join(dir_path, "converted"))

    if source == "local":
        if not dir_path:
            raise ValueError("--dir is required for local source.")
        return LocalFilesConnector(directory_path=dir_path)

    if source == "github":
        if not repo_name:
            raise ValueError("--repo is required for github source.")
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not found in .env.")
        return GitHubConnector(token=token, repo_name=repo_name)

    if source == "confluence":
        if not space_key:
            raise ValueError("--space is required for confluence source.")
        url = os.getenv("CONFLUENCE_URL")
        username = os.getenv("CONFLUENCE_USERNAME")
        token = os.getenv("CONFLUENCE_API_TOKEN")
        if not url or not username or not token:
            raise ValueError(
                "CONFLUENCE_URL, CONFLUENCE_USERNAME, and CONFLUENCE_API_TOKEN "
                "must be set in .env."
            )
        return ConfluenceConnector(
            url=url, username=username, token=token, space_key=space_key
        )

    raise ValueError(f"Unsupported source type: {source}")
