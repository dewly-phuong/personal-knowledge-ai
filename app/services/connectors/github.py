import datetime
from github import Github
from app.services.connectors.base import BaseConnector, Document

class GitHubConnector(BaseConnector):
    def __init__(self, token: str, repo_name: str):
        """
        token: GitHub personal access token (PAT)
        repo_name: Repository name in format "owner/repo"
        """
        self.token = token
        self.repo_name = repo_name

    def fetch_documents(self) -> list[Document]:
        documents = []
        if not self.token or not self.repo_name:
            return documents

        try:
            g = Github(self.token)
            repo = g.get_repo(self.repo_name)
            contents = repo.get_contents("")
            
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path))
                else:
                    path = file_content.path
                    path_lower = path.lower()
                    
                    # Target README.md and all files in docs/ folder ending with .md or .txt
                    is_readme = path_lower.endswith("readme.md")
                    is_in_docs = "docs/" in path_lower and path_lower.endswith((".md", ".txt"))
                    
                    if is_readme or is_in_docs:
                        try:
                            decoded = file_content.decoded_content.decode("utf-8")
                            
                            # Fetch last commit date for this specific file
                            commits = repo.get_commits(path=path)
                            if commits.totalCount > 0:
                                last_commit_date = commits[0].commit.committer.date
                                last_modified = last_commit_date.replace(
                                    tzinfo=datetime.timezone.utc
                                ).isoformat()
                            else:
                                last_modified = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            
                            documents.append(
                                Document(
                                    content=decoded,
                                    source_url=file_content.html_url,
                                    path=path,
                                    source_type="github",
                                    last_modified=last_modified,
                                )
                            )
                        except Exception as e:
                            print(f"Error downloading content for {path}: {e}")
        except Exception as e:
            print(f"Error connecting to GitHub repository {self.repo_name}: {e}")
            
        return documents
