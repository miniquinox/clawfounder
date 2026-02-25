# GitHub Connector

Connects ClawFounder to GitHub using the [PyGithub](https://github.com/PyGithub/PyGithub) library.

## What It Does

- List your repositories
- Get recent commits
- List open issues and PRs
- Create issues

## Authentication

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token (classic) with `repo` scope
3. Copy the token

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GITHUB_TOKEN` | Personal access token | Yes |

## Setup

```bash
cd connectors/github
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `github_list_repos` | List your repositories |
| `github_get_commits` | Get recent commits for a repo |
| `github_list_issues` | List open issues for a repo |
| `github_create_issue` | Create a new issue |

## Testing

```bash
python3 -m pytest connectors/github/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "What was my last commit on clawfounder?"
```
