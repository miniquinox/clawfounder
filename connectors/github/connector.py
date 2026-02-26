"""
GitHub connector — Full GitHub management via the PyGithub API.

Supports repos, commits, issues, PRs, branches, file content,
workflow runs, notifications, search, labels, and releases.
"""

import os
import json
import base64
from pathlib import Path

SUPPORTS_MULTI_ACCOUNT = True


def is_connected() -> bool:
    """Return True if GITHUB_TOKEN is set."""
    return bool(os.environ.get("GITHUB_TOKEN"))


# ─── Tool Definitions ──────────────────────────────────────────

TOOLS = [
    # ── Repos ──────────────────────────────────────────────────
    {
        "name": "github_list_repos",
        "description": "List your GitHub repositories. Returns name, description, language, stars, and last updated date.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max repos to return (default: 10)",
                },
                "visibility": {
                    "type": "string",
                    "enum": ["all", "public", "private"],
                    "description": "Filter by visibility (default: all)",
                },
            },
        },
    },
    {
        "name": "github_get_repo",
        "description": "Get detailed info about a single GitHub repository: description, topics, stats, default branch, open issues/PR counts, and more.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_get_file",
        "description": "Read the content of a file from a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "path": {
                    "type": "string",
                    "description": "File path within the repo (e.g., 'README.md', 'src/main.py')",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch, tag, or commit SHA (default: repo default branch)",
                },
            },
            "required": ["repo", "path"],
        },
    },
    {
        "name": "github_list_branches",
        "description": "List branches for a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max branches to return (default: 20)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_list_releases",
        "description": "List releases for a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max releases to return (default: 10)",
                },
            },
            "required": ["repo"],
        },
    },
    # ── Commits ────────────────────────────────────────────────
    {
        "name": "github_get_commit",
        "description": "Get full details of a single commit: message, author, stats, and list of files changed with patches.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "sha": {
                    "type": "string",
                    "description": "Commit SHA (full or abbreviated)",
                },
            },
            "required": ["repo", "sha"],
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
                    "description": "Repository in 'owner/repo' format",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (default: repo default branch)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max commits to return (default: 5)",
                },
            },
            "required": ["repo"],
        },
    },
    # ── Issues ─────────────────────────────────────────────────
    {
        "name": "github_list_issues",
        "description": "List issues for a GitHub repository. Excludes pull requests.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Filter by state (default: open)",
                },
                "labels": {
                    "type": "string",
                    "description": "Comma-separated label names to filter by",
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
        "name": "github_get_issue",
        "description": "Get full details of a GitHub issue including body and comments.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "number": {
                    "type": "integer",
                    "description": "Issue number",
                },
            },
            "required": ["repo", "number"],
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
                "labels": {
                    "type": "string",
                    "description": "Comma-separated labels to apply",
                },
                "assignees": {
                    "type": "string",
                    "description": "Comma-separated GitHub usernames to assign",
                },
            },
            "required": ["repo", "title"],
        },
    },
    {
        "name": "github_comment_issue",
        "description": "Add a comment to a GitHub issue or pull request.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "number": {
                    "type": "integer",
                    "description": "Issue or PR number",
                },
                "body": {
                    "type": "string",
                    "description": "Comment body (markdown)",
                },
            },
            "required": ["repo", "number", "body"],
        },
    },
    {
        "name": "github_manage_labels",
        "description": "Add or remove labels on a GitHub issue or pull request.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "number": {
                    "type": "integer",
                    "description": "Issue or PR number",
                },
                "add": {
                    "type": "string",
                    "description": "Comma-separated labels to add",
                },
                "remove": {
                    "type": "string",
                    "description": "Comma-separated labels to remove",
                },
            },
            "required": ["repo", "number"],
        },
    },
    # ── Pull Requests ──────────────────────────────────────────
    {
        "name": "github_list_prs",
        "description": "List pull requests for a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Filter by state (default: open)",
                },
                "head": {
                    "type": "string",
                    "description": "Filter by head branch (user:branch or branch)",
                },
                "base": {
                    "type": "string",
                    "description": "Filter by base branch",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max PRs to return (default: 10)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_get_pr",
        "description": "Get detailed info about a pull request: title, body, diff stats, review status, and mergeability.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "number": {
                    "type": "integer",
                    "description": "Pull request number",
                },
            },
            "required": ["repo", "number"],
        },
    },
    {
        "name": "github_create_pr",
        "description": "Create a new pull request.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "title": {
                    "type": "string",
                    "description": "PR title",
                },
                "body": {
                    "type": "string",
                    "description": "PR description (markdown)",
                },
                "head": {
                    "type": "string",
                    "description": "Branch with your changes (e.g., 'feature-branch')",
                },
                "base": {
                    "type": "string",
                    "description": "Branch to merge into (e.g., 'main')",
                },
                "draft": {
                    "type": "boolean",
                    "description": "Create as draft PR (default: false)",
                },
            },
            "required": ["repo", "title", "head", "base"],
        },
    },
    {
        "name": "github_merge_pr",
        "description": "Merge a pull request.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "number": {
                    "type": "integer",
                    "description": "Pull request number",
                },
                "merge_method": {
                    "type": "string",
                    "enum": ["merge", "squash", "rebase"],
                    "description": "Merge method (default: merge)",
                },
            },
            "required": ["repo", "number"],
        },
    },
    {
        "name": "github_pr_files",
        "description": "List files changed in a pull request, with additions, deletions, and patch diff.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "number": {
                    "type": "integer",
                    "description": "Pull request number",
                },
            },
            "required": ["repo", "number"],
        },
    },
    # ── Workflows ──────────────────────────────────────────────
    {
        "name": "github_list_workflows",
        "description": "List recent GitHub Actions workflow runs for a repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max runs to return (default: 10)",
                },
            },
            "required": ["repo"],
        },
    },
    # ── Notifications ──────────────────────────────────────────
    {
        "name": "github_notifications",
        "description": "List your unread GitHub notifications.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max notifications to return (default: 20)",
                },
            },
        },
    },
    # ── Search ─────────────────────────────────────────────────
    {
        "name": "github_search",
        "description": "Search GitHub for repositories, issues/PRs, or code.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports GitHub search syntax)",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["repositories", "issues", "code"],
                    "description": "What to search for (default: issues)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (default: 10)",
                },
            },
            "required": ["query"],
        },
    },
]


# ─── Helpers ────────────────────────────────────────────────────

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


# ─── Repo Handlers ──────────────────────────────────────────────

def _list_repos(max_results: int = 10, visibility: str = "all", account_id=None) -> str:
    g = _get_github(account_id)
    repos = []
    kwargs = {"sort": "updated"}
    if visibility and visibility != "all":
        kwargs["visibility"] = visibility
    for repo in g.get_user().get_repos(**kwargs)[:max_results]:
        repos.append({
            "name": repo.full_name,
            "description": repo.description or "",
            "language": repo.language or "Unknown",
            "updated": repo.updated_at.isoformat() if repo.updated_at else "",
            "stars": repo.stargazers_count,
            "private": repo.private,
        })
    return json.dumps(repos, indent=2)


def _get_repo(repo: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    return json.dumps({
        "full_name": r.full_name,
        "description": r.description or "",
        "language": r.language or "Unknown",
        "default_branch": r.default_branch,
        "stars": r.stargazers_count,
        "forks": r.forks_count,
        "open_issues": r.open_issues_count,
        "watchers": r.watchers_count,
        "private": r.private,
        "topics": r.get_topics(),
        "created": r.created_at.isoformat() if r.created_at else "",
        "updated": r.updated_at.isoformat() if r.updated_at else "",
        "url": r.html_url,
    }, indent=2)


def _get_file(repo: str, path: str, ref: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    kwargs = {"path": path}
    if ref:
        kwargs["ref"] = ref
    contents = r.get_contents(**kwargs)
    if isinstance(contents, list):
        # It's a directory — list entries
        entries = [{"name": c.name, "type": c.type, "path": c.path} for c in contents]
        return json.dumps({"type": "directory", "entries": entries}, indent=2)
    # It's a file
    if contents.encoding == "base64" and contents.content:
        try:
            decoded = base64.b64decode(contents.content).decode("utf-8")
        except UnicodeDecodeError:
            decoded = f"[Binary file, {contents.size} bytes]"
    else:
        decoded = contents.content or ""
    # Truncate very large files
    if len(decoded) > 10000:
        decoded = decoded[:10000] + f"\n\n... [truncated, {contents.size} bytes total]"
    return json.dumps({
        "path": contents.path,
        "size": contents.size,
        "content": decoded,
        "sha": contents.sha,
    }, indent=2)


def _list_branches(repo: str, max_results: int = 20, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    branches = []
    for branch in r.get_branches()[:max_results]:
        branches.append({
            "name": branch.name,
            "protected": branch.protected,
            "sha": branch.commit.sha[:8],
        })
    return json.dumps(branches, indent=2)


def _list_releases(repo: str, max_results: int = 10, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    releases = []
    for release in r.get_releases()[:max_results]:
        releases.append({
            "tag": release.tag_name,
            "name": release.title or release.tag_name,
            "draft": release.draft,
            "prerelease": release.prerelease,
            "published": release.published_at.isoformat() if release.published_at else "",
            "author": release.author.login if release.author else "Unknown",
            "url": release.html_url,
        })
    return json.dumps(releases, indent=2)


# ─── Commit Handlers ────────────────────────────────────────────

def _get_commits(repo: str, max_results: int = 5, branch: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    kwargs = {}
    if branch:
        kwargs["sha"] = branch
    commits = []
    for commit in r.get_commits(**kwargs)[:max_results]:
        commits.append({
            "sha": commit.sha[:8],
            "message": commit.commit.message.split("\n")[0],
            "author": commit.commit.author.name if commit.commit.author else "Unknown",
            "date": commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else "",
            "files_changed": commit.stats.total if commit.stats else 0,
        })
    return json.dumps(commits, indent=2)


def _get_commit(repo: str, sha: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    commit = r.get_commit(sha)
    files = []
    for f in commit.files:
        files.append({
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "changes": f.changes,
            "patch": (f.patch or "")[:1000],
        })
    return json.dumps({
        "sha": commit.sha,
        "message": commit.commit.message,
        "author": commit.commit.author.name if commit.commit.author else "Unknown",
        "date": commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else "",
        "additions": commit.stats.additions if commit.stats else 0,
        "deletions": commit.stats.deletions if commit.stats else 0,
        "total_changes": commit.stats.total if commit.stats else 0,
        "files": files,
        "url": commit.html_url,
    }, indent=2)


# ─── Issue Handlers ──────────────────────────────────────────────

def _list_issues(repo: str, max_results: int = 10, state: str = "open", labels: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    kwargs = {"state": state}
    if labels:
        label_objs = []
        for name in labels.split(","):
            name = name.strip()
            if name:
                try:
                    label_objs.append(r.get_label(name))
                except Exception:
                    pass
        if label_objs:
            kwargs["labels"] = label_objs
    issues = []
    for item in r.get_issues(**kwargs)[:max_results]:
        # get_issues also returns PRs — filter them out
        if item.pull_request:
            continue
        issues.append({
            "number": item.number,
            "title": item.title,
            "state": item.state,
            "author": item.user.login if item.user else "Unknown",
            "labels": [l.name for l in item.labels],
            "body_preview": (item.body or "")[:200],
            "comments": item.comments,
            "created": item.created_at.isoformat() if item.created_at else "",
        })
    return json.dumps(issues, indent=2)


def _get_issue(repo: str, number: int, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    issue = r.get_issue(number)
    comments = []
    for c in issue.get_comments()[:20]:
        comments.append({
            "author": c.user.login if c.user else "Unknown",
            "body": (c.body or "")[:500],
            "created": c.created_at.isoformat() if c.created_at else "",
        })
    return json.dumps({
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "author": issue.user.login if issue.user else "Unknown",
        "body": (issue.body or "")[:2000],
        "labels": [l.name for l in issue.labels],
        "assignees": [a.login for a in issue.assignees],
        "comments": comments,
        "created": issue.created_at.isoformat() if issue.created_at else "",
        "updated": issue.updated_at.isoformat() if issue.updated_at else "",
        "url": issue.html_url,
    }, indent=2)


def _create_issue(repo: str, title: str, body: str = "", labels: str = None, assignees: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    kwargs = {"title": title, "body": body}
    if labels:
        kwargs["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
    if assignees:
        kwargs["assignees"] = [a.strip() for a in assignees.split(",") if a.strip()]
    issue = r.create_issue(**kwargs)
    return json.dumps({
        "number": issue.number,
        "title": issue.title,
        "url": issue.html_url,
        "message": f"Issue #{issue.number} created successfully.",
    }, indent=2)


def _comment_issue(repo: str, number: int, body: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    issue = r.get_issue(number)
    comment = issue.create_comment(body=body)
    return json.dumps({
        "id": comment.id,
        "url": comment.html_url,
        "message": f"Comment added to #{number}.",
    }, indent=2)


def _manage_labels(repo: str, number: int, add: str = None, remove: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    issue = r.get_issue(number)
    added = []
    removed = []
    if add:
        for name in add.split(","):
            name = name.strip()
            if name:
                issue.add_to_labels(name)
                added.append(name)
    if remove:
        for name in remove.split(","):
            name = name.strip()
            if name:
                try:
                    issue.remove_from_labels(name)
                    removed.append(name)
                except Exception:
                    pass
    current = [l.name for l in issue.get_labels()]
    return json.dumps({
        "added": added,
        "removed": removed,
        "current_labels": current,
        "message": f"Labels updated on #{number}.",
    }, indent=2)


# ─── PR Handlers ─────────────────────────────────────────────────

def _list_prs(repo: str, max_results: int = 10, state: str = "open", head: str = None, base: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    kwargs = {"state": state, "sort": "updated", "direction": "desc"}
    if head:
        kwargs["head"] = head
    if base:
        kwargs["base"] = base
    prs = []
    for pr in r.get_pulls(**kwargs)[:max_results]:
        prs.append({
            "number": pr.number,
            "title": pr.title,
            "state": pr.state,
            "author": pr.user.login if pr.user else "Unknown",
            "head": pr.head.ref,
            "base": pr.base.ref,
            "draft": pr.draft,
            "created": pr.created_at.isoformat() if pr.created_at else "",
            "updated": pr.updated_at.isoformat() if pr.updated_at else "",
        })
    return json.dumps(prs, indent=2)


def _get_pr(repo: str, number: int, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.get_pull(number)
    reviews = []
    for review in pr.get_reviews()[:10]:
        reviews.append({
            "user": review.user.login if review.user else "Unknown",
            "state": review.state,
        })
    return json.dumps({
        "number": pr.number,
        "title": pr.title,
        "state": pr.state,
        "author": pr.user.login if pr.user else "Unknown",
        "body": (pr.body or "")[:2000],
        "head": pr.head.ref,
        "base": pr.base.ref,
        "draft": pr.draft,
        "mergeable": pr.mergeable,
        "merged": pr.merged,
        "additions": pr.additions,
        "deletions": pr.deletions,
        "changed_files": pr.changed_files,
        "commits": pr.commits,
        "reviews": reviews,
        "labels": [l.name for l in pr.labels],
        "created": pr.created_at.isoformat() if pr.created_at else "",
        "updated": pr.updated_at.isoformat() if pr.updated_at else "",
        "url": pr.html_url,
    }, indent=2)


def _create_pr(repo: str, title: str, head: str, base: str, body: str = "", draft: bool = False, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.create_pull(title=title, body=body, head=head, base=base, draft=draft)
    return json.dumps({
        "number": pr.number,
        "title": pr.title,
        "url": pr.html_url,
        "message": f"PR #{pr.number} created successfully.",
    }, indent=2)


def _merge_pr(repo: str, number: int, merge_method: str = "merge", account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.get_pull(number)
    result = pr.merge(merge_method=merge_method)
    return json.dumps({
        "merged": result.merged,
        "sha": result.sha,
        "message": result.message,
    }, indent=2)


def _pr_files(repo: str, number: int, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.get_pull(number)
    files = []
    for f in pr.get_files():
        files.append({
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "changes": f.changes,
            "patch": (f.patch or "")[:1000],
        })
    return json.dumps(files, indent=2)


# ─── Workflow Handlers ───────────────────────────────────────────

def _list_workflows(repo: str, max_results: int = 10, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    runs = []
    for run in r.get_workflow_runs()[:max_results]:
        runs.append({
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "conclusion": run.conclusion,
            "branch": run.head_branch,
            "event": run.event,
            "created": run.created_at.isoformat() if run.created_at else "",
            "url": run.html_url,
        })
    return json.dumps(runs, indent=2)


# ─── Notification Handlers ───────────────────────────────────────

def _notifications(max_results: int = 20, account_id=None) -> str:
    g = _get_github(account_id)
    notifs = []
    for n in g.get_user().get_notifications()[:max_results]:
        notifs.append({
            "id": n.id,
            "reason": n.reason,
            "subject": n.subject.title,
            "type": n.subject.type,
            "repo": n.repository.full_name,
            "unread": n.unread,
            "updated": n.updated_at.isoformat() if n.updated_at else "",
            "url": n.subject.url or "",
        })
    return json.dumps(notifs, indent=2)


# ─── Search Handler ──────────────────────────────────────────────

def _search(query: str, search_type: str = "issues", max_results: int = 10, account_id=None) -> str:
    g = _get_github(account_id)
    results = []
    if search_type == "repositories":
        for repo in g.search_repositories(query)[:max_results]:
            results.append({
                "name": repo.full_name,
                "description": repo.description or "",
                "stars": repo.stargazers_count,
                "language": repo.language or "",
                "url": repo.html_url,
            })
    elif search_type == "code":
        for code in g.search_code(query)[:max_results]:
            results.append({
                "repo": code.repository.full_name,
                "path": code.path,
                "name": code.name,
                "url": code.html_url,
            })
    else:
        # Default: issues (also includes PRs in GitHub's search)
        for item in g.search_issues(query)[:max_results]:
            results.append({
                "number": item.number,
                "title": item.title,
                "state": item.state,
                "repo": item.repository.full_name,
                "is_pr": item.pull_request is not None,
                "author": item.user.login if item.user else "Unknown",
                "url": item.html_url,
            })
    return json.dumps(results, indent=2)


# ─── Main Handler ────────────────────────────────────────────────

def handle(tool_name: str, args: dict, account_id: str = None) -> str:
    try:
        # Repos
        if tool_name == "github_list_repos":
            return _list_repos(
                max_results=args.get("max_results", 10),
                visibility=args.get("visibility", "all"),
                account_id=account_id,
            )
        elif tool_name == "github_get_repo":
            return _get_repo(args["repo"], account_id=account_id)
        elif tool_name == "github_get_file":
            return _get_file(args["repo"], args["path"], ref=args.get("ref"), account_id=account_id)
        elif tool_name == "github_list_branches":
            return _list_branches(args["repo"], max_results=args.get("max_results", 20), account_id=account_id)
        elif tool_name == "github_list_releases":
            return _list_releases(args["repo"], max_results=args.get("max_results", 10), account_id=account_id)
        # Commits
        elif tool_name == "github_get_commit":
            return _get_commit(args["repo"], args["sha"], account_id=account_id)
        elif tool_name == "github_get_commits":
            return _get_commits(
                args["repo"],
                max_results=args.get("max_results", 5),
                branch=args.get("branch"),
                account_id=account_id,
            )
        # Issues
        elif tool_name == "github_list_issues":
            return _list_issues(
                args["repo"],
                max_results=args.get("max_results", 10),
                state=args.get("state", "open"),
                labels=args.get("labels"),
                account_id=account_id,
            )
        elif tool_name == "github_get_issue":
            return _get_issue(args["repo"], args["number"], account_id=account_id)
        elif tool_name == "github_create_issue":
            return _create_issue(
                args["repo"], args["title"],
                body=args.get("body", ""),
                labels=args.get("labels"),
                assignees=args.get("assignees"),
                account_id=account_id,
            )
        elif tool_name == "github_comment_issue":
            return _comment_issue(args["repo"], args["number"], args["body"], account_id=account_id)
        elif tool_name == "github_manage_labels":
            return _manage_labels(
                args["repo"], args["number"],
                add=args.get("add"),
                remove=args.get("remove"),
                account_id=account_id,
            )
        # PRs
        elif tool_name == "github_list_prs":
            return _list_prs(
                args["repo"],
                max_results=args.get("max_results", 10),
                state=args.get("state", "open"),
                head=args.get("head"),
                base=args.get("base"),
                account_id=account_id,
            )
        elif tool_name == "github_get_pr":
            return _get_pr(args["repo"], args["number"], account_id=account_id)
        elif tool_name == "github_create_pr":
            return _create_pr(
                args["repo"], args["title"],
                head=args["head"], base=args["base"],
                body=args.get("body", ""),
                draft=args.get("draft", False),
                account_id=account_id,
            )
        elif tool_name == "github_merge_pr":
            return _merge_pr(
                args["repo"], args["number"],
                merge_method=args.get("merge_method", "merge"),
                account_id=account_id,
            )
        elif tool_name == "github_pr_files":
            return _pr_files(args["repo"], args["number"], account_id=account_id)
        # Workflows
        elif tool_name == "github_list_workflows":
            return _list_workflows(args["repo"], max_results=args.get("max_results", 10), account_id=account_id)
        # Notifications
        elif tool_name == "github_notifications":
            return _notifications(max_results=args.get("max_results", 20), account_id=account_id)
        # Search
        elif tool_name == "github_search":
            return _search(
                args["query"],
                search_type=args.get("search_type", "issues"),
                max_results=args.get("max_results", 10),
                account_id=account_id,
            )
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"GitHub error: {e}"
