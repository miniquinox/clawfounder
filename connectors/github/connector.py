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
    """Return True if any GitHub token is available (base or account-specific)."""
    if os.environ.get("GITHUB_TOKEN"):
        return True
    # Check account-specific tokens from the registry
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"
    if accounts_file.exists():
        try:
            registry = json.loads(accounts_file.read_text())
            for acct in registry.get("accounts", {}).get("github", []):
                env_key = acct.get("env_key", "")
                if env_key and os.environ.get(env_key):
                    return True
        except Exception:
            pass
    return False


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
    # ── Write Operations (files + repos) ──────────────────────
    {
        "name": "github_create_or_update_file",
        "description": "Create or update a single file in a GitHub repository. If the file exists, you must provide its current SHA (or set auto_sha=true to fetch it automatically). The content should be the raw text — it will be base64-encoded automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "path": {
                    "type": "string",
                    "description": "File path within the repo (e.g., 'docs/README.md')",
                },
                "content": {
                    "type": "string",
                    "description": "The full file content (raw text)",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to commit to (default: repo default branch)",
                },
                "sha": {
                    "type": "string",
                    "description": "Current blob SHA of the file (required for updates, omit for new files). Set to 'auto' to fetch automatically.",
                },
            },
            "required": ["repo", "path", "content", "message"],
        },
    },
    {
        "name": "github_delete_file",
        "description": "Delete a file from a GitHub repository. Requires the file's current SHA (set to 'auto' to fetch it automatically).",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "path": {
                    "type": "string",
                    "description": "File path to delete",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message for the deletion",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch to commit to (default: repo default branch)",
                },
                "sha": {
                    "type": "string",
                    "description": "Current blob SHA of the file. Set to 'auto' to fetch automatically.",
                },
            },
            "required": ["repo", "path", "message"],
        },
    },
    {
        "name": "github_create_branch",
        "description": "Create a new branch in a GitHub repository from an existing branch, tag, or commit.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "branch": {
                    "type": "string",
                    "description": "Name for the new branch",
                },
                "source_branch": {
                    "type": "string",
                    "description": "Source branch to create from (default: repo default branch)",
                },
            },
            "required": ["repo", "branch"],
        },
    },
    {
        "name": "github_delete_branch",
        "description": "Delete a branch from a GitHub repository. Cannot delete the default branch.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name to delete",
                },
            },
            "required": ["repo", "branch"],
        },
    },
    {
        "name": "github_create_repo",
        "description": "Create a new GitHub repository for the authenticated user.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Repository name",
                },
                "description": {
                    "type": "string",
                    "description": "Repository description",
                },
                "private": {
                    "type": "boolean",
                    "description": "Whether the repo is private (default: false)",
                },
                "auto_init": {
                    "type": "boolean",
                    "description": "Initialize with a README (default: true)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "github_fork_repo",
        "description": "Fork a repository to the authenticated user's account.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository to fork in 'owner/repo' format",
                },
            },
            "required": ["repo"],
        },
    },
    # ── Issue/PR Mutations ────────────────────────────────────
    {
        "name": "github_update_issue",
        "description": "Update a GitHub issue — edit title, body, state (open/closed), labels, or assignees. Note: setting labels replaces all existing labels.",
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
                "title": {
                    "type": "string",
                    "description": "New title",
                },
                "body": {
                    "type": "string",
                    "description": "New body (markdown)",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed"],
                    "description": "Set issue state",
                },
                "labels": {
                    "type": "string",
                    "description": "Comma-separated labels (replaces all existing labels)",
                },
                "assignees": {
                    "type": "string",
                    "description": "Comma-separated GitHub usernames to assign",
                },
            },
            "required": ["repo", "number"],
        },
    },
    {
        "name": "github_update_pr",
        "description": "Update a pull request — edit title, body, state (open/closed), or base branch.",
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
                "title": {
                    "type": "string",
                    "description": "New title",
                },
                "body": {
                    "type": "string",
                    "description": "New body (markdown)",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed"],
                    "description": "Set PR state",
                },
                "base": {
                    "type": "string",
                    "description": "Change base branch",
                },
            },
            "required": ["repo", "number"],
        },
    },
    {
        "name": "github_create_review",
        "description": "Submit a review on a pull request. Events: APPROVE, REQUEST_CHANGES, or COMMENT.",
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
                "event": {
                    "type": "string",
                    "enum": ["APPROVE", "REQUEST_CHANGES", "COMMENT"],
                    "description": "Review action",
                },
                "body": {
                    "type": "string",
                    "description": "Review comment body (required for REQUEST_CHANGES and COMMENT)",
                },
            },
            "required": ["repo", "number", "event"],
        },
    },
    {
        "name": "github_request_reviewers",
        "description": "Request reviews on a pull request from specific users or teams.",
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
                "reviewers": {
                    "type": "string",
                    "description": "Comma-separated GitHub usernames to request review from",
                },
                "team_reviewers": {
                    "type": "string",
                    "description": "Comma-separated team slugs to request review from",
                },
            },
            "required": ["repo", "number"],
        },
    },
    # ── Diff & Comparison ─────────────────────────────────────
    {
        "name": "github_compare",
        "description": "Compare two branches, tags, or commits. Shows ahead/behind counts and files changed.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "base": {
                    "type": "string",
                    "description": "Base branch, tag, or commit SHA",
                },
                "head": {
                    "type": "string",
                    "description": "Head branch, tag, or commit SHA",
                },
            },
            "required": ["repo", "base", "head"],
        },
    },
    # ── Workflows & CI ────────────────────────────────────────
    {
        "name": "github_trigger_workflow",
        "description": "Trigger a GitHub Actions workflow dispatch event. The workflow must have a workflow_dispatch trigger.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "workflow_id": {
                    "type": "string",
                    "description": "Workflow file name (e.g., 'ci.yml') or numeric ID",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch or tag to run the workflow on (default: repo default branch)",
                },
                "inputs": {
                    "type": "string",
                    "description": "JSON string of workflow input key-value pairs",
                },
            },
            "required": ["repo", "workflow_id"],
        },
    },
    {
        "name": "github_list_workflow_definitions",
        "description": "List workflow definition files (e.g., ci.yml, deploy.yml) in a repository, not runs.",
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
    # ── User & Meta ───────────────────────────────────────────
    {
        "name": "github_get_me",
        "description": "Get the authenticated GitHub user's profile information.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "github_get_repo_tree",
        "description": "Get the full file/directory tree of a repository at a given branch or SHA. Useful for understanding repo structure.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch, tag, or commit SHA (default: repo default branch)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Recursively list all files (default: true)",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "github_list_tags",
        "description": "List git tags for a repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max tags to return (default: 20)",
                },
            },
            "required": ["repo"],
        },
    },
    # ── Gists ─────────────────────────────────────────────────
    {
        "name": "github_list_gists",
        "description": "List the authenticated user's gists.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max gists to return (default: 10)",
                },
            },
        },
    },
    {
        "name": "github_create_gist",
        "description": "Create a new GitHub gist with one or more files.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Gist description",
                },
                "files": {
                    "type": "string",
                    "description": "JSON object mapping filenames to content, e.g. '{\"hello.py\": \"print(1)\", \"notes.txt\": \"some text\"}'",
                },
                "public": {
                    "type": "boolean",
                    "description": "Whether the gist is public (default: false)",
                },
            },
            "required": ["files"],
        },
    },
    # ── Releases & Stars ──────────────────────────────────────
    {
        "name": "github_create_release",
        "description": "Create a new release on a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "tag": {
                    "type": "string",
                    "description": "Tag name for the release (e.g., 'v1.0.0')",
                },
                "name": {
                    "type": "string",
                    "description": "Release title",
                },
                "body": {
                    "type": "string",
                    "description": "Release notes (markdown)",
                },
                "draft": {
                    "type": "boolean",
                    "description": "Create as draft release (default: false)",
                },
                "prerelease": {
                    "type": "boolean",
                    "description": "Mark as prerelease (default: false)",
                },
            },
            "required": ["repo", "tag"],
        },
    },
    {
        "name": "github_star_repo",
        "description": "Star or unstar a GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "unstar": {
                    "type": "boolean",
                    "description": "Set to true to unstar instead of star (default: false)",
                },
            },
            "required": ["repo"],
        },
    },
]


# ─── Helpers ────────────────────────────────────────────────────

def _resolve_env_key(account_id=None):
    """Resolve the env var name for the given account.

    Priority when no account_id is given:
    1. Registered account keys from accounts.json (smart multi-account)
    2. Base GITHUB_TOKEN (legacy / no accounts registered)
    """
    accounts_file = Path.home() / ".clawfounder" / "accounts.json"

    if account_id is None or account_id == "default":
        # Prefer registered account keys — they are the source of truth
        if accounts_file.exists():
            try:
                registry = json.loads(accounts_file.read_text())
                for acct in registry.get("accounts", {}).get("github", []):
                    env_key = acct.get("env_key", "")
                    if env_key and os.environ.get(env_key):
                        return env_key
            except Exception:
                pass
        # Fall back to base key (no accounts registered yet)
        return "GITHUB_TOKEN"

    # Specific account requested — look up its key
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
    kwargs = {"sort": "updated", "affiliation": "owner,collaborator,organization_member"}
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


# ─── File & Repo Write Handlers ──────────────────────────────────

def _create_or_update_file(repo: str, path: str, content: str, message: str,
                           branch: str = None, sha: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    kwargs = {"path": path, "message": message, "content": content}
    if branch:
        kwargs["branch"] = branch

    # Auto-fetch SHA if requested or if file exists
    if sha == "auto" or sha is None:
        try:
            fc_kwargs = {"path": path}
            if branch:
                fc_kwargs["ref"] = branch
            existing = r.get_contents(**fc_kwargs)
            if not isinstance(existing, list):
                kwargs["sha"] = existing.sha
        except Exception:
            # File doesn't exist — that's fine for create
            if sha == "auto":
                pass
    elif sha:
        kwargs["sha"] = sha

    is_update = "sha" in kwargs
    result = r.update_file(**kwargs) if is_update else r.create_file(**kwargs)
    commit = result["commit"]
    return json.dumps({
        "action": "updated" if is_update else "created",
        "path": path,
        "sha": result["content"].sha if result.get("content") else "",
        "commit_sha": commit.sha,
        "commit_url": commit.html_url,
        "message": f"File '{path}' {'updated' if is_update else 'created'} successfully.",
    }, indent=2)


def _delete_file(repo: str, path: str, message: str, branch: str = None,
                 sha: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)

    # Auto-fetch SHA
    if not sha or sha == "auto":
        fc_kwargs = {"path": path}
        if branch:
            fc_kwargs["ref"] = branch
        existing = r.get_contents(**fc_kwargs)
        sha = existing.sha

    kwargs = {"path": path, "message": message, "sha": sha}
    if branch:
        kwargs["branch"] = branch
    result = r.delete_file(**kwargs)
    commit = result["commit"]
    return json.dumps({
        "path": path,
        "commit_sha": commit.sha,
        "commit_url": commit.html_url,
        "message": f"File '{path}' deleted successfully.",
    }, indent=2)


def _create_branch(repo: str, branch: str, source_branch: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    source = source_branch or r.default_branch
    # Get the SHA of the source branch tip
    source_ref = r.get_branch(source)
    sha = source_ref.commit.sha
    # create_git_ref needs "refs/heads/X" format
    ref = r.create_git_ref(ref=f"refs/heads/{branch}", sha=sha)
    return json.dumps({
        "branch": branch,
        "source": source,
        "sha": sha[:8],
        "ref": ref.ref,
        "message": f"Branch '{branch}' created from '{source}'.",
    }, indent=2)


def _delete_branch(repo: str, branch: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    # get_git_ref needs "heads/X" format (no "refs/" prefix)
    ref = r.get_git_ref(f"heads/{branch}")
    ref.delete()
    return json.dumps({
        "branch": branch,
        "message": f"Branch '{branch}' deleted successfully.",
    }, indent=2)


def _create_repo(name: str, description: str = "", private: bool = False,
                 auto_init: bool = True, account_id=None) -> str:
    g = _get_github(account_id)
    user = g.get_user()
    repo = user.create_repo(
        name=name,
        description=description,
        private=private,
        auto_init=auto_init,
    )
    return json.dumps({
        "full_name": repo.full_name,
        "private": repo.private,
        "url": repo.html_url,
        "clone_url": repo.clone_url,
        "message": f"Repository '{repo.full_name}' created successfully.",
    }, indent=2)


def _fork_repo(repo: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    fork = r.create_fork()
    return json.dumps({
        "full_name": fork.full_name,
        "parent": repo,
        "url": fork.html_url,
        "clone_url": fork.clone_url,
        "message": f"Forked '{repo}' to '{fork.full_name}'.",
    }, indent=2)


# ─── Issue/PR Mutation Handlers ──────────────────────────────────

def _update_issue(repo: str, number: int, title: str = None, body: str = None,
                  state: str = None, labels: str = None, assignees: str = None,
                  account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    issue = r.get_issue(number)
    kwargs = {}
    if title is not None:
        kwargs["title"] = title
    if body is not None:
        kwargs["body"] = body
    if state is not None:
        kwargs["state"] = state
    if labels is not None:
        kwargs["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
    if assignees is not None:
        kwargs["assignees"] = [a.strip() for a in assignees.split(",") if a.strip()]
    issue.edit(**kwargs)
    return json.dumps({
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "labels": [l.name for l in issue.labels],
        "assignees": [a.login for a in issue.assignees],
        "url": issue.html_url,
        "message": f"Issue #{number} updated.",
    }, indent=2)


def _update_pr(repo: str, number: int, title: str = None, body: str = None,
               state: str = None, base: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.get_pull(number)
    kwargs = {}
    if title is not None:
        kwargs["title"] = title
    if body is not None:
        kwargs["body"] = body
    if state is not None:
        kwargs["state"] = state
    if base is not None:
        kwargs["base"] = base
    pr.edit(**kwargs)
    return json.dumps({
        "number": pr.number,
        "title": pr.title,
        "state": pr.state,
        "base": pr.base.ref,
        "url": pr.html_url,
        "message": f"PR #{number} updated.",
    }, indent=2)


def _create_review(repo: str, number: int, event: str, body: str = "", account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.get_pull(number)
    review = pr.create_review(body=body, event=event)
    return json.dumps({
        "id": review.id,
        "state": review.state,
        "user": review.user.login if review.user else "Unknown",
        "url": review.html_url,
        "message": f"Review ({event}) submitted on PR #{number}.",
    }, indent=2)


def _request_reviewers(repo: str, number: int, reviewers: str = None,
                       team_reviewers: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    pr = r.get_pull(number)
    kwargs = {}
    if reviewers:
        kwargs["reviewers"] = [r.strip() for r in reviewers.split(",") if r.strip()]
    if team_reviewers:
        kwargs["team_reviewers"] = [t.strip() for t in team_reviewers.split(",") if t.strip()]
    pr.create_review_request(**kwargs)
    return json.dumps({
        "number": number,
        "requested_reviewers": kwargs.get("reviewers", []),
        "requested_teams": kwargs.get("team_reviewers", []),
        "message": f"Review requested on PR #{number}.",
    }, indent=2)


# ─── Diff & Comparison Handler ───────────────────────────────────

def _compare(repo: str, base: str, head: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    comparison = r.compare(base, head)
    files = []
    for f in comparison.files[:50]:
        files.append({
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "changes": f.changes,
        })
    return json.dumps({
        "base": base,
        "head": head,
        "status": comparison.status,
        "ahead_by": comparison.ahead_by,
        "behind_by": comparison.behind_by,
        "total_commits": comparison.total_commits,
        "files_changed": len(comparison.files),
        "files": files,
        "url": comparison.html_url,
    }, indent=2)


# ─── Workflow Handlers (new) ─────────────────────────────────────

def _trigger_workflow(repo: str, workflow_id: str, ref: str = None,
                      inputs: str = None, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    ref = ref or r.default_branch

    # workflow_id can be filename or numeric ID
    try:
        wf_id = int(workflow_id)
    except ValueError:
        wf_id = workflow_id

    workflow = r.get_workflow(wf_id)
    input_dict = json.loads(inputs) if inputs else {}
    success = workflow.create_dispatch(ref=ref, inputs=input_dict)
    return json.dumps({
        "triggered": success,
        "workflow": workflow.name,
        "ref": ref,
        "inputs": input_dict,
        "message": f"Workflow '{workflow.name}' dispatched on '{ref}'." if success else "Failed to trigger workflow.",
    }, indent=2)


def _list_workflow_definitions(repo: str, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    workflows = []
    for wf in r.get_workflows():
        workflows.append({
            "id": wf.id,
            "name": wf.name,
            "path": wf.path,
            "state": wf.state,
        })
    return json.dumps(workflows, indent=2)


# ─── User & Meta Handlers ───────────────────────────────────────

def _get_me(account_id=None) -> str:
    g = _get_github(account_id)
    user = g.get_user()
    return json.dumps({
        "login": user.login,
        "name": user.name or "",
        "email": user.email or "",
        "bio": user.bio or "",
        "public_repos": user.public_repos,
        "private_repos": user.owned_private_repos or 0,
        "followers": user.followers,
        "following": user.following,
        "created": user.created_at.isoformat() if user.created_at else "",
        "url": user.html_url,
    }, indent=2)


def _get_repo_tree(repo: str, ref: str = None, recursive: bool = True, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    sha = ref or r.default_branch
    tree = r.get_git_tree(sha=sha, recursive=recursive)
    entries = []
    for item in tree.tree:
        entries.append({
            "path": item.path,
            "type": item.type,  # "blob" or "tree"
            "size": item.size if item.type == "blob" else None,
        })
    return json.dumps({
        "sha": tree.sha,
        "total_entries": len(entries),
        "truncated": tree.raw_data.get("truncated", False),
        "tree": entries,
    }, indent=2)


def _list_tags(repo: str, max_results: int = 20, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    tags = []
    for tag in r.get_tags()[:max_results]:
        tags.append({
            "name": tag.name,
            "sha": tag.commit.sha[:8],
        })
    return json.dumps(tags, indent=2)


# ─── Gist Handlers ──────────────────────────────────────────────

def _list_gists(max_results: int = 10, account_id=None) -> str:
    g = _get_github(account_id)
    gists = []
    for gist in g.get_user().get_gists()[:max_results]:
        gists.append({
            "id": gist.id,
            "description": gist.description or "",
            "public": gist.public,
            "files": list(gist.files.keys()),
            "created": gist.created_at.isoformat() if gist.created_at else "",
            "updated": gist.updated_at.isoformat() if gist.updated_at else "",
            "url": gist.html_url,
        })
    return json.dumps(gists, indent=2)


def _create_gist(files: str, description: str = "", public: bool = False, account_id=None) -> str:
    from github import InputFileContent
    g = _get_github(account_id)
    file_dict = json.loads(files)
    gist_files = {name: InputFileContent(content) for name, content in file_dict.items()}
    gist = g.get_user().create_gist(
        public=public,
        files=gist_files,
        description=description,
    )
    return json.dumps({
        "id": gist.id,
        "url": gist.html_url,
        "files": list(gist.files.keys()),
        "message": "Gist created successfully.",
    }, indent=2)


# ─── Release & Star Handlers ────────────────────────────────────

def _create_release(repo: str, tag: str, name: str = None, body: str = "",
                    draft: bool = False, prerelease: bool = False, account_id=None) -> str:
    g = _get_github(account_id)
    r = g.get_repo(repo)
    release = r.create_git_release(
        tag=tag,
        name=name or tag,
        message=body,
        draft=draft,
        prerelease=prerelease,
    )
    return json.dumps({
        "id": release.id,
        "tag": release.tag_name,
        "name": release.title,
        "draft": release.draft,
        "prerelease": release.prerelease,
        "url": release.html_url,
        "message": f"Release '{release.title}' created.",
    }, indent=2)


def _star_repo(repo: str, unstar: bool = False, account_id=None) -> str:
    g = _get_github(account_id)
    user = g.get_user()
    r = g.get_repo(repo)
    if unstar:
        user.remove_from_starred(r)
        action = "unstarred"
    else:
        user.add_to_starred(r)
        action = "starred"
    return json.dumps({
        "repo": repo,
        "action": action,
        "message": f"Repository '{repo}' {action}.",
    }, indent=2)


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
        # File & Repo Write Operations
        elif tool_name == "github_create_or_update_file":
            return _create_or_update_file(
                args["repo"], args["path"], args["content"], args["message"],
                branch=args.get("branch"),
                sha=args.get("sha"),
                account_id=account_id,
            )
        elif tool_name == "github_delete_file":
            return _delete_file(
                args["repo"], args["path"], args["message"],
                branch=args.get("branch"),
                sha=args.get("sha"),
                account_id=account_id,
            )
        elif tool_name == "github_create_branch":
            return _create_branch(
                args["repo"], args["branch"],
                source_branch=args.get("source_branch"),
                account_id=account_id,
            )
        elif tool_name == "github_delete_branch":
            return _delete_branch(args["repo"], args["branch"], account_id=account_id)
        elif tool_name == "github_create_repo":
            return _create_repo(
                args["name"],
                description=args.get("description", ""),
                private=args.get("private", False),
                auto_init=args.get("auto_init", True),
                account_id=account_id,
            )
        elif tool_name == "github_fork_repo":
            return _fork_repo(args["repo"], account_id=account_id)
        # Issue/PR Mutations
        elif tool_name == "github_update_issue":
            return _update_issue(
                args["repo"], args["number"],
                title=args.get("title"),
                body=args.get("body"),
                state=args.get("state"),
                labels=args.get("labels"),
                assignees=args.get("assignees"),
                account_id=account_id,
            )
        elif tool_name == "github_update_pr":
            return _update_pr(
                args["repo"], args["number"],
                title=args.get("title"),
                body=args.get("body"),
                state=args.get("state"),
                base=args.get("base"),
                account_id=account_id,
            )
        elif tool_name == "github_create_review":
            return _create_review(
                args["repo"], args["number"], args["event"],
                body=args.get("body", ""),
                account_id=account_id,
            )
        elif tool_name == "github_request_reviewers":
            return _request_reviewers(
                args["repo"], args["number"],
                reviewers=args.get("reviewers"),
                team_reviewers=args.get("team_reviewers"),
                account_id=account_id,
            )
        # Diff & Comparison
        elif tool_name == "github_compare":
            return _compare(args["repo"], args["base"], args["head"], account_id=account_id)
        # Workflows & CI
        elif tool_name == "github_trigger_workflow":
            return _trigger_workflow(
                args["repo"], args["workflow_id"],
                ref=args.get("ref"),
                inputs=args.get("inputs"),
                account_id=account_id,
            )
        elif tool_name == "github_list_workflow_definitions":
            return _list_workflow_definitions(args["repo"], account_id=account_id)
        # User & Meta
        elif tool_name == "github_get_me":
            return _get_me(account_id=account_id)
        elif tool_name == "github_get_repo_tree":
            return _get_repo_tree(
                args["repo"],
                ref=args.get("ref"),
                recursive=args.get("recursive", True),
                account_id=account_id,
            )
        elif tool_name == "github_list_tags":
            return _list_tags(args["repo"], max_results=args.get("max_results", 20), account_id=account_id)
        # Gists
        elif tool_name == "github_list_gists":
            return _list_gists(max_results=args.get("max_results", 10), account_id=account_id)
        elif tool_name == "github_create_gist":
            return _create_gist(
                args["files"],
                description=args.get("description", ""),
                public=args.get("public", False),
                account_id=account_id,
            )
        # Releases & Stars
        elif tool_name == "github_create_release":
            return _create_release(
                args["repo"], args["tag"],
                name=args.get("name"),
                body=args.get("body", ""),
                draft=args.get("draft", False),
                prerelease=args.get("prerelease", False),
                account_id=account_id,
            )
        elif tool_name == "github_star_repo":
            return _star_repo(args["repo"], unstar=args.get("unstar", False), account_id=account_id)
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"GitHub error: {e}"
