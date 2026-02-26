# GitHub Connector

Connects ClawFounder to GitHub using the [PyGithub](https://github.com/PyGithub/PyGithub) library.

## Authentication

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token (classic) with `repo` scope
3. Copy the token

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GITHUB_TOKEN` | Personal access token | Yes |

## Available Tools (20)

### Repos
| Tool | Description |
|---|---|
| `github_list_repos` | List your repos (filter by visibility) |
| `github_get_repo` | Get full details of a repo (topics, stats, default branch) |
| `github_get_file` | Read file content from a repo |
| `github_list_branches` | List branches in a repo |
| `github_list_releases` | List releases/tags for a repo |

### Commits
| Tool | Description |
|---|---|
| `github_get_commit` | Get full details of a single commit (files changed, patches, stats) |
| `github_get_commits` | Get recent commits (filter by branch) |

### Issues
| Tool | Description |
|---|---|
| `github_list_issues` | List issues (filter by state, labels) |
| `github_get_issue` | Get full issue details with comments |
| `github_create_issue` | Create an issue (with labels, assignees) |
| `github_comment_issue` | Comment on an issue or PR |
| `github_manage_labels` | Add/remove labels on an issue or PR |

### Pull Requests
| Tool | Description |
|---|---|
| `github_list_prs` | List PRs (filter by state, head, base) |
| `github_get_pr` | Get PR details (diff stats, reviews, mergeability) |
| `github_create_pr` | Create a PR (with draft option) |
| `github_merge_pr` | Merge a PR (merge/squash/rebase) |
| `github_pr_files` | List files changed in a PR with patches |

### Workflows
| Tool | Description |
|---|---|
| `github_list_workflows` | List recent GitHub Actions runs |

### Notifications
| Tool | Description |
|---|---|
| `github_notifications` | List unread GitHub notifications |

### Search
| Tool | Description |
|---|---|
| `github_search` | Search repos, issues/PRs, or code |

## Common Workflows

- **Review a PR**: `github_get_pr` → `github_pr_files` → `github_comment_issue`
- **Triage issues**: `github_list_issues` → `github_get_issue` → `github_manage_labels`
- **Inspect a commit**: `github_get_commits` to find it → `github_get_commit` for full diff and files changed
- **Check CI status**: `github_list_workflows` to see recent runs
- **Read source code**: `github_get_file` with repo and path
- **Find something**: `github_search` with type (repositories, issues, code)

## Setup

```bash
cd connectors/github
bash install.sh
```
