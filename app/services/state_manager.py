import os
import json
import datetime
from typing import Dict, Any, List


class StateManager:
    def __init__(self, file_path: str = "graph/state.json"):
        self.file_path = file_path
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Loads state from JSON file or returns default state structure."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if isinstance(state, dict) and "files" in state:
                        return state
            except Exception as e:
                print(
                    f"Error loading state from {self.file_path}: {e}. Initializing default state."
                )

        # Ensure parent folder exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        return {
            "version": 1,
            "last_run": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "files": {},
        }

    def save(self):
        """Saves current state to JSON file."""
        self.state["last_run"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"Error saving state to {self.file_path}: {e}")

    def is_modified(self, source_url: str, last_modified: str) -> bool:
        """
        Returns True if the document has been modified since the last run,
        or if it has never been processed.
        """
        files_state = self.state.get("files", {})
        if source_url not in files_state:
            return True

        stored_timestamp = files_state[source_url].get("last_modified")
        return stored_timestamp != last_modified

    def update_state(
        self, source_url: str, last_modified: str, entities_mentioned: List[str]
    ):
        """Updates the stored state for a source document."""
        if "files" not in self.state:
            self.state["files"] = {}

        self.state["files"][source_url] = {
            "last_modified": last_modified,
            "entities_mentioned": list(set(entities_mentioned)),
        }
