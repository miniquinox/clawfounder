# 🦀 ClawFounder

**Your AI agent that actually *does* things.**

Most AI tools wait for you to ask. ClawFounder doesn't. It connects to your Gmail, Telegram, GitHub, Supabase, Firebase — whatever you need — and works *for you* in the background.

Think of it like this: you install ClawFounder on your machine, plug in the connectors you care about, and it starts being useful. Check your emails every 2 hours and summarize them. Ping your team on Telegram every Thursday at 4pm for a standup. Pull your latest GitHub commits and build a changelog. Add data to a doc on the 1st of every month. Wake you up with a morning briefing.

It's an AI that lives on your computer and stays proactive.

> **This is an open source project.** We want the community to build connectors for everything. Slack, Discord, Notion, Jira, Stripe, Twilio, WhatsApp, Google Calendar, Spotify — you name it. If it has an API, it can be a connector.

---

## What's a Connector?

A connector is a small folder that teaches ClawFounder how to talk to a service. Each connector has:

| File | What it does |
|---|---|
| `instructions.md` | Explains the service, how auth works, what env vars you need |
| `connector.py` | The actual code — defines tools the AI can call |
| `requirements.txt` | Python dependencies |
| `install.sh` | One-liner setup script |
| `test_connector.py` | Tests to make sure it works |

That's it. Five files. Copy the template, fill them in, submit a PR.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/miniquinox/clawfounder.git
cd clawfounder

# 2. Create a virtual environment & install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Set up your keys
cp .env.example .env
# Edit .env with your API keys

# 4. Install a connector (e.g., Gmail)
cd connectors/gmail && bash install.sh && cd ../..

# 5. Talk to it
python -m agent.runner --provider gemini
# Try: "Do I have any unread emails?"
```

> **Note:** Always activate the venv first (`source venv/bin/activate`) before running commands.

Pick your LLM provider: `gemini`, `openai`, or `claude`.

---

## Project Structure

```
clawfounder/
├── README.md
├── CONTRIBUTING.md          ← How to add your own connector
├── requirements.txt
├── .env.example
│
├── agent/                   ← The brain
│   ├── runner.py            ← CLI entry point
│   ├── providers/           ← Gemini, OpenAI, Claude wrappers
│   ├── connector_loader.py  ← Auto-discovers your connectors
│   └── tool_router.py       ← Routes AI tool calls → connectors
│
├── connectors/              ← The muscles
│   ├── _template/           ← Copy this to start a new connector
│   ├── gmail/
│   ├── telegram/
│   ├── github/
│   ├── supabase/
│   ├── firebase/
│   └── yahoo_finance/
│
└── tests/                   ← Validation
    ├── validate_connector.py  ← Checks connector structure
    └── run_all.py             ← Runs everything
```

---

## Adding a Connector

**Short version:**

1. Copy `connectors/_template/` → `connectors/your_service/`
2. Fill in the 5 files
3. Run `python3 tests/validate_connector.py connectors/your_service`
4. Run `python3 -m agent.runner --provider gemini` and test it
5. Open a PR

**Long version:** See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## The Connector Contract

Every `connector.py` must export two things:

```python
# 1. A list of tools the AI can call
TOOLS = [
    {
        "name": "get_unread_emails",
        "description": "Fetches unread emails from Gmail",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max emails to return"
                }
            }
        }
    }
]

# 2. A handler that executes them
def handle(tool_name: str, args: dict) -> str:
    if tool_name == "get_unread_emails":
        return fetch_unread(args.get("max_results", 10))
```

The AI sees the tools, decides which to call, and ClawFounder routes it to your `handle()` function. That's the whole system.

---

## Testing Your Connector

We have a two-step validation:

### Step 1 — Structure Check
```bash
python3 tests/validate_connector.py connectors/your_service
```
This checks:
- ✅ All 5 required files exist
- ✅ `connector.py` exports `TOOLS` and `handle`
- ✅ Each tool has `name`, `description`, `parameters`
- ✅ `handle()` is callable

### Step 2 — Live Test
```bash
python3 -m agent.runner --provider gemini
```
Ask a question that triggers your connector. If it works, you're good.

### Step 3 — Unit Tests
```bash
python3 -m pytest connectors/your_service/test_connector.py -v
```
Your `test_connector.py` should test your connector independently.

### Run Everything
```bash
python3 tests/run_all.py
```
This validates every connector in the repo and runs all unit tests.

---

## The Vision

Right now, ClawFounder is a simple agent that connects to services and answers questions. But the plan is bigger:

- **Cron jobs** — Schedule any action. "Check my email every 2 hours and summarize." "Call my team every Thursday."
- **Proactive mode** — The agent checks in with *you*, not the other way around. Morning briefings, weekly reports, anomaly alerts.
- **Knowledge base** — The agent remembers past conversations and builds context over time.
- **Voice** — Integrate with Whisper for live voice calls. Imagine an AI project manager that calls your engineers, takes notes, and reports findings.
- **Multi-agent** — Chain connectors together. "When a new GitHub issue is created, check if it's a duplicate in the knowledge base, and if not, create a Jira ticket and notify the team on Slack."

We're building this in the open. Every connector the community adds makes ClawFounder more useful for everyone.

---

## Supported Providers

| Provider | Status | API Key Env Var |
|---|---|---|
| Google Gemini | ✅ Ready | `GEMINI_API_KEY` |
| OpenAI (GPT-4) | ✅ Ready | `OPENAI_API_KEY` |
| Anthropic Claude | ✅ Ready | `ANTHROPIC_API_KEY` |

---

## Included Connectors

| Connector | What it does |
|---|---|
| 📧 Gmail | Read, search, send emails |
| 💬 Telegram | Send/receive messages via bot |
| 🐙 GitHub | Repos, commits, issues, PRs |
| ⚡ Supabase | Query database, check logs |
| 🔥 Firebase | Firestore reads/writes, project info |
| 📈 Yahoo Finance | Stock quotes, market data |

---

## Contributing

We want your connectors! See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

Some ideas: Slack, Discord, Notion, Jira, Google Calendar, Spotify, Twilio, WhatsApp, Twitter/X, LinkedIn, Stripe, AWS, Vercel, Cloudflare, Reddit, HackerNews, Weather APIs, Home Assistant...

If it has an API, make it a connector. 🦀

---

## License

MIT — do whatever you want with it.
