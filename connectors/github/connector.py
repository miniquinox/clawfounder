"""
GitHub connector — Repos, commits, issues, and PRs via the GitHub API.
"""

import os
import json
from pathlib import Path

SUPPORTS_MULTI_ACCOUNT = True


def is_connected() -> bool:
    """Return True if GITHUB_TOKEN is set."""
    return bool(os.environ.get("GITHUB_TOKEN"))


TOOLS = [
    {
        "name": "github_list_repos",
        "description": "List your GitHub repositories. Returns name, description, language, and last updated date.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max repos to return (default: 10)",
                },
            },
        },
    },
    {
        "name": "github_get_commits",
        "description": "Get recent commits for a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository name in 'owner/repo' format (e.g., 'miniquinox/clawfounder')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max commits to return (default: 5)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_list_issues",
        "description": "List open issues for a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max issues to return (default: 10)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_create_issue",
        "description": "Create a new issue on a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "title": {
                    "type": "string",
                    "description": "Issue title",
                },
                "body": {
                    "type": "string",
                    "description": "Issue body (markdown)",
                },
            },
            "required": ["repo", "title"],
        },
    },
]


def _resolve_env_key(account_id=None):
    """Resolve the env var name for the given account."""
    if account_id is None or account_id == "default":
        return "GITHUB_TOKEN"
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            registry = json.loads(accounts_file.read_text())
            for acct in registry.get("accounts", {}).get("github", []):
                if acct["id"] == account_id and "env_key" in acct:
                    return acct["env_key"]
        except Exception:
            pass
    return f"GITHUB_TOKEN_{account_id.upper()}"


def _get_github(account_id=None):
    try:
        from github import Github
    except ImportError:
        raise ImportError("PyGithub not installed. Run: bash connectors/github/install.sh")

    env_key = _resolve_env_key(account_id)
    token = os.environ.get(env_key)
    if not token:
        raise ValueError(f"{env_key} not set. Add it to your .env file.")
    return Github(token)


def _list_repos(max_results: int = 10, account_id=None) -> str:
    g = _get_github(account_id)
    repos = []
    for repo in g.get_user().get_repos(sort="updated")[:max_results]:
        repos.append({
            "name": repo.full_name,
            "description": repo.description or "",
            "language": repo.language or "Unknown",
            "updated": repo.updated_at.isoformat() if repo.updated_at else "",
            "stars": repo.stargazers_count,
        })
    return json.dumps(repos, indent=2)


def _get_commits(repo: str, max_results: int = 5, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    commits = []
    for commit in r.get_commits()[:max_results]:
        commits.append({
            "sha": commit.sha[:8],
            "message": commit.commit.message.split("\n")[0],
            "author": commit.commit.author.name,
            "date": commit.commit.author.date.isoformat() if commit.commit.author.date else "",
        })
    return json.dumps(commits, indent=2)


def _list_issues(repo: str, max_results: int = 10, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    issues = []
    for issue in r.get_issues(state="open")[:max_results]:
        issues.append({
            "number": issue.number,
            "title": issue.title,
            "author": issue.user.login if issue.user else "Unknown",
            "labels": [l.name for l in issue.labels],
            "created": issue.created_at.isoformat() if issue.created_at else "",
        })
    return json.dumps(issues, indent=2)


def _create_issue(repo: str, title: str, body: str = "", account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    issue = r.create_issue(title=title, body=body)
    return f"Issue created: #{issue.number} — {issue.title} ({issue.html_url})"


def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        if tool_name == "github_list_repos":
            return _list_repos(args.get("max_results", 10), account_id=account_id)
        elif tool_name == "github_get_commits":
            return _get_commits(args["repo"], args.get("max_results", 5), account_id=account_id)
        elif tool_name == "github_list_issues":
            return _list_issues(args["repo"], args.get("max_results", 10), account_id=account_id)
        elif tool_name == "github_create_issue":
            return _create_issue(args["repo"], args["title"], args.get("body", ""), account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"GitHub error: {e}"
