import os
import httpx

class GitHubClient:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
        self.default_owner = os.environ.get("GITHUB_OWNER")
        self.default_repo = os.environ.get("GITHUB_REPO")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN is required")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    def dispatch(self, repository: str, workflow: str, inputs: dict, ref: str = "main") -> dict:
        owner, repo = repository.split("/", 1)
        url = f"{self.base}/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
        r = httpx.post(url, headers=self._headers(), json={"ref": ref, "inputs": {k: str(v) for k, v in inputs.items()}}, timeout=30)
        r.raise_for_status()
        return {"repository": repository, "workflow": workflow, "status": "dispatched", "ref": ref}
