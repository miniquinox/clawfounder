# Firebase Connector

Connects ClawFounder to Google Firestore using your Google account.

## What It Does

- Read Firestore documents
- Write/update Firestore documents
- List documents in a collection

## Authentication

**No API keys or service accounts needed.** This connector uses your Google login.

From the ClawFounder dashboard, click "Login with Google" on the Firebase card.
This opens your browser — sign in with the Google account that has access to your
Firebase project, pick your project, and you're connected.

Under the hood, it uses the Firebase CLI's OAuth token to call the Firestore REST API.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `FIREBASE_PROJECT_ID` | Your Firebase project ID | Yes |

> `FIREBASE_REFRESH_TOKEN` is automatically saved by the dashboard after Google login.
> You don't need to set it manually.

## Setup

```bash
# Option 1: Use the dashboard (recommended)
cd dashboard && npm run dev
# Click "Login with Google" on the Firebase card

# Option 2: Manual CLI
npx firebase-tools login
# Then set FIREBASE_PROJECT_ID in your .env
```

## Available Tools

| Tool | Description |
|---|---|
| `firebase_get_document` | Read a Firestore document by path |
| `firebase_set_document` | Write or update a Firestore document |
| `firebase_list_collection` | List documents in a collection |

## Testing

```bash
python3 -m pytest connectors/firebase/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "List the documents in my users collection"
```
