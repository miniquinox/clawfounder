# Connector Template

This is a **template** — copy this entire folder to start building your own connector.

```bash
cp -r connectors/_template connectors/your_service
```

## What This Connector Does

_Replace this with a description of your service._

## Authentication

_Explain what API keys, OAuth tokens, or credentials are needed._

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `YOUR_API_KEY` | _description_ | Yes |

## Setup

```bash
cd connectors/your_service
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `your_service_example_action` | _what it does_ |

## Testing

```bash
# Validate connector structure
python3 tests/validate_connector.py connectors/your_service

# Run unit tests
python3 -m pytest connectors/your_service/test_connector.py -v

# Test with the agent
python3 -m agent.runner --provider gemini
# Ask: "Your test question here"
```
