# Firebase Connector

Connects ClawFounder to [Firebase](https://firebase.google.com/) using the [firebase-admin](https://firebase.google.com/docs/admin/setup) Python SDK.

## What It Does

- Read/write Firestore documents
- List collections
- Get project info

## Authentication

1. Go to [Firebase Console](https://console.firebase.google.com/) → your project
2. Go to Project Settings → Service accounts
3. Click "Generate new private key" to download a JSON file

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `FIREBASE_PROJECT_ID` | Your Firebase project ID | Yes |
| `FIREBASE_CREDENTIALS_FILE` | Path to service account JSON file | Yes |

## Setup

```bash
cd connectors/firebase
bash install.sh
```

## Available Tools

| Tool | Description |
|---|---|
| `firebase_get_document` | Read a Firestore document by path |
| `firebase_list_collection` | List documents in a Firestore collection |
| `firebase_set_document` | Write/update a Firestore document |

## Testing

```bash
python3 -m pytest connectors/firebase/test_connector.py -v
python3 -m agent.runner --provider gemini
# Ask: "Check my Firebase Firestore users collection"
```
