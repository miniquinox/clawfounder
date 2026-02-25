# Supabase Connector

Connects ClawFounder to [Supabase](https://supabase.com/) using the [supabase-py](https://github.com/supabase-community/supabase-py) client.

## What It Does

- Query tables
- Insert/update/delete rows
- Run raw SQL (read-only)

## Authentication

1. Go to your [Supabase project dashboard](https://app.supabase.com/)
2. Go to Settings → API
3. Copy the Project URL and the **service_role** key (not the anon key — service role bypasses RLS)

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `SUPABASE_URL` | Project URL (`https://xxx.supabase.co`) | Yes |
| `SUPABASE_SERVICE_KEY` | Service role key | Yes |

## Setup

```bash
cd connectors/supabase
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `supabase_query` | Query a table with optional filters |
| `supabase_insert` | Insert a row into a table |
| `supabase_sql` | Run a read-only SQL query |

## Testing

```bash
python3 -m pytest connectors/supabase/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "How many rows are in my users table?"
```
