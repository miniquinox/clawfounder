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

## Available Tools (40)

### Repos
| Tool | Description |
|---|---|
| `github_list_repos` | List your repos (filter by visibility) |
| `github_get_repo` | Get full details of a repo (topics, stats, default branch) |
| `github_get_file` | Read file content from a repo |
| `github_list_branches` | List branches in a repo |
| `github_list_releases` | List releases for a repo |
| `github_create_repo` | Create a new repository |
| `github_fork_repo` | Fork a repository to your account |

### File Operations
| Tool | Description |
|---|---|
| `github_create_or_update_file` | Create or update a file in a repo (auto-fetches SHA for updates) |
| `github_delete_file` | Delete a file from a repo |

### Branches & Tags
| Tool | Description |
|---|---|
| `github_create_branch` | Create a new branch from an existing branch |
| `github_delete_branch` | Delete a branch |
| `github_list_tags` | List git tags for a repo |

### Commits
| Tool | Description |
|---|---|
| `github_get_commit` | Get full details of a single commit (files changed, patches, stats) |
| `github_get_commits` | Get recent commits (filter by branch) |

### Diff & Comparison
| Tool | Description |
|---|---|
| `github_compare` | Compare two branches/tags/commits — ahead/behind, files changed |

### Issues
| Tool | Description |
|---|---|
| `github_list_issues` | List issues (filter by state, labels) |
| `github_get_issue` | Get full issue details with comments |
| `github_create_issue` | Create an issue (with labels, assignees) |
| `github_update_issue` | Edit issue title, body, state, labels, assignees |
| `github_comment_issue` | Comment on an issue or PR |
| `github_manage_labels` | Add/remove labels on an issue or PR |

### Pull Requests
| Tool | Description |
|---|---|
| `github_list_prs` | List PRs (filter by state, head, base) |
| `github_get_pr` | Get PR details (diff stats, reviews, mergeability) |
| `github_create_pr` | Create a PR (with draft option) |
| `github_update_pr` | Edit PR title, body, state, base branch |
| `github_merge_pr` | Merge a PR (merge/squash/rebase) |
| `github_pr_files` | List files changed in a PR with patches |
| `github_create_review` | Submit a PR review (APPROVE, REQUEST_CHANGES, COMMENT) |
| `github_request_reviewers` | Request review from users or teams |

### Workflows & CI
| Tool | Description |
|---|---|
| `github_list_workflows` | List recent GitHub Actions runs |
| `github_list_workflow_definitions` | List workflow files (ci.yml, deploy.yml, etc.) |
| `github_trigger_workflow` | Trigger a workflow dispatch event |

### User & Meta
| Tool | Description |
|---|---|
| `github_get_me` | Get authenticated user profile |
| `github_get_repo_tree` | Get full file/directory tree of a repo |

### Notifications
| Tool | Description |
|---|---|
| `github_notifications` | List unread GitHub notifications |

### Search
| Tool | Description |
|---|---|
| `github_search` | Search repos, issues/PRs, or code |

### Gists
| Tool | Description |
|---|---|
| `github_list_gists` | List your gists |
| `github_create_gist` | Create a gist with one or more files |

### Releases & Stars
| Tool | Description |
|---|---|
| `github_create_release` | Create a release on a repo |
| `github_star_repo` | Star or unstar a repo |

## Common Workflows

- **Review a PR**: `github_get_pr` → `github_pr_files` → `github_create_review`
- **Triage issues**: `github_list_issues` → `github_get_issue` → `github_update_issue` / `github_manage_labels`
- **Inspect a commit**: `github_get_commits` to find it → `github_get_commit` for full diff
- **Compare branches**: `github_compare` to see ahead/behind and files changed
- **Check CI status**: `github_list_workflows` for recent runs, `github_list_workflow_definitions` to see what workflows exist
- **Trigger a deploy**: `github_trigger_workflow` with workflow file and branch
- **Read source code**: `github_get_file` with repo and path, or `github_get_repo_tree` for full structure
- **Create a branch and edit**: `github_create_branch` → `github_create_or_update_file` → `github_create_pr`
- **Find something**: `github_search` with type (repositories, issues, code)
- **Share code**: `github_create_gist` with one or more files
- **Release**: `github_create_release` with tag, name, and release notes
- **Who am I?**: `github_get_me` for authenticated user profile

## Setup

```bash
cd connectors/github
bash install.sh
```
