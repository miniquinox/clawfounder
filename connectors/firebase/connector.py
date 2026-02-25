"""
Firebase connector — Read/write Firestore documents.

Authentication priority:
  1. FIREBASE_REFRESH_TOKEN env var (from dashboard login)
  2. Firebase CLI stored token (~/.config/configstore/firebase-tools.json)

Project detection priority:
  1. FIREBASE_PROJECT_ID env var
  2. .firebaserc in project root
  3. gcloud config project
"""

import os
import json

# Firebase CLI OAuth client credentials (public, embedded in firebase-tools source)
_FIREBASE_CLIENT_ID = "***REDACTED_CLIENT_ID***"
_FIREBASE_CLIENT_SECRET = "***REDACTED_CLIENT_SECRET***"

TOOLS = [
    {
        "name": "firebase_list_projects",
        "description": "List all Firebase projects the user has access to.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "firebase_list_collection",
        "description": "List documents in a Firestore collection. Can specify project_id and database.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection": {
                    "type": "string",
                    "description": "Collection path, e.g. 'users' or 'orders'",
                },
                "project_id": {
                    "type": "string",
                    "description": "Firebase project ID (optional — auto-detected if not provided)",
                },
                "database": {
                    "type": "string",
                    "description": "Firestore database ID (default: '(default)')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max documents to return (default: 20)",
                },
            },
            "required": ["collection"],
        },
    },
    {
        "name": "firebase_list_collections",
        "description": "List all top-level Firestore collections in a project. Can specify project_id and database.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Firebase project ID (optional — auto-detected if not provided)",
                },
                "database": {
                    "type": "string",
                    "description": "Firestore database ID (default: '(default)')",
                },
            },
        },
    },
    {
        "name": "firebase_get_document",
        "description": "Read a Firestore document by its path (e.g., 'users/user123'). Can specify project_id and database.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Document path, e.g. 'users/user123' or 'orders/abc123'",
                },
                "project_id": {
                    "type": "string",
                    "description": "Firebase project ID (optional — auto-detected if not provided)",
                },
                "database": {
                    "type": "string",
                    "description": "Firestore database ID (default: '(default)')",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "firebase_set_document",
        "description": "Write or update a Firestore document. Can specify project_id and database.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Document path, e.g. 'users/user123'",
                },
                "data": {
                    "type": "object",
                    "description": "The data to write (JSON object)",
                },
                "project_id": {
                    "type": "string",
                    "description": "Firebase project ID (optional — auto-detected if not provided)",
                },
                "database": {
                    "type": "string",
                    "description": "Firestore database ID (default: '(default)')",
                },
            },
            "required": ["path", "data"],
        },
    },
]


def _get_access_token():
    """Get a fresh access token using the Firebase CLI refresh token."""
    import requests

    refresh_token = os.environ.get("FIREBASE_REFRESH_TOKEN")

    if not refresh_token:
        # Try reading from Firebase CLI config directly
        config_path = os.path.join(
            os.path.expanduser("~"), ".config", "configstore", "firebase-tools.json"
        )
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    config = json.load(f)
                refresh_token = config.get("tokens", {}).get("refresh_token")
            except Exception:
                pass

    if not refresh_token:
        raise ValueError(
            "Not logged in. Use the dashboard to 'Login with Google' for Firebase, "
            "or run: npx firebase-tools login"
        )

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": _FIREBASE_CLIENT_ID,
            "client_secret": _FIREBASE_CLIENT_SECRET,
        },
    )

    if resp.status_code != 200:
        raise ValueError(f"Token refresh failed: {resp.text}")

    return resp.json()["access_token"]


def _get_project_id(override=None):
    """Get the Firebase project ID from override, env, .firebaserc, or gcloud."""
    # 1. Explicit override from tool args
    if override and override.strip():
        return override.strip()

    # 2. Environment variable
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "").strip()
    # Skip if it's a comment or empty
    if project_id and not project_id.startswith("#"):
        return project_id

    # 3. Try .firebaserc in project root
    for search_dir in [os.getcwd(), os.path.dirname(os.path.dirname(os.path.dirname(__file__)))]:
        rc_path = os.path.join(search_dir, ".firebaserc")
        if os.path.exists(rc_path):
            try:
                with open(rc_path) as f:
                    rc = json.load(f)
                pid = rc.get("projects", {}).get("default")
                if pid:
                    return pid
            except Exception:
                pass

    # 4. Try gcloud config
    import subprocess
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    raise ValueError("No Firebase project ID found. Set FIREBASE_PROJECT_ID in .env or pass project_id.")


def _firestore_url(project_id, database="(default)", path=""):
    base = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/{database}/documents"
    if path:
        return f"{base}/{path}"
    return base


def _parse_firestore_value(value):
    """Convert Firestore REST API value format to Python."""
    if "stringValue" in value:
        return value["stringValue"]
    elif "integerValue" in value:
        return int(value["integerValue"])
    elif "doubleValue" in value:
        return value["doubleValue"]
    elif "booleanValue" in value:
        return value["booleanValue"]
    elif "nullValue" in value:
        return None
    elif "mapValue" in value:
        fields = value["mapValue"].get("fields", {})
        return {k: _parse_firestore_value(v) for k, v in fields.items()}
    elif "arrayValue" in value:
        values = value["arrayValue"].get("values", [])
        return [_parse_firestore_value(v) for v in values]
    elif "timestampValue" in value:
        return value["timestampValue"]
    elif "referenceValue" in value:
        return value["referenceValue"]
    return str(value)


def _parse_document(doc):
    """Parse a Firestore REST document into a clean dict."""
    fields = doc.get("fields", {})
    parsed = {k: _parse_firestore_value(v) for k, v in fields.items()}
    name = doc.get("name", "")
    parsed["_id"] = name.split("/")[-1] if name else ""
    parsed["_path"] = "/".join(name.split("/documents/", 1)[1:]) if "/documents/" in name else ""
    return parsed


def _to_firestore_value(value):
    """Convert a Python value to Firestore REST API format."""
    if isinstance(value, str):
        return {"stringValue": value}
    elif isinstance(value, bool):
        return {"booleanValue": value}
    elif isinstance(value, int):
        return {"integerValue": str(value)}
    elif isinstance(value, float):
        return {"doubleValue": value}
    elif value is None:
        return {"nullValue": None}
    elif isinstance(value, list):
        return {"arrayValue": {"values": [_to_firestore_value(v) for v in value]}}
    elif isinstance(value, dict):
        return {"mapValue": {"fields": {k: _to_firestore_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


# ── Tool implementations ────────────────────────────────────────

def _list_projects() -> str:
    """List all Firebase projects via the Firebase Management API."""
    import requests
    try:
        token = _get_access_token()
        resp = requests.get(
            "https://firebase.googleapis.com/v1beta1/projects?pageSize=50",
            headers={"Authorization": f"Bearer {token}"},
        )

        if resp.status_code != 200:
            return f"Firebase API error ({resp.status_code}): {resp.text[:300]}"

        data = resp.json()
        projects = data.get("results", [])

        if not projects:
            return "No Firebase projects found."

        result = []
        for p in projects:
            pid = p.get("projectId", "unknown")
            name = p.get("displayName", pid)
            result.append(f"• {name} ({pid})")

        return f"Found {len(result)} Firebase project(s):\n" + "\n".join(result)
    except Exception as e:
        return f"Firebase error: {e}"


def _list_collections(project_id=None, database="(default)") -> str:
    """List top-level Firestore collections using listCollectionIds."""
    import requests
    try:
        token = _get_access_token()
        pid = _get_project_id(project_id)
        url = f"https://firestore.googleapis.com/v1/projects/{pid}/databases/{database}/documents:listCollectionIds"

        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={},
        )

        if resp.status_code != 200:
            error_text = resp.text[:200]
            if "Datastore Mode" in error_text:
                return f"Project '{pid}' database '{database}' uses Datastore mode (not Firestore native). Try a different database ID."
            return f"Firestore error ({resp.status_code}): {error_text}"

        data = resp.json()
        collection_ids = data.get("collectionIds", [])

        if not collection_ids:
            return f"No collections found in project '{pid}' database '{database}'."

        return f"Collections in {pid}/{database}:\n" + "\n".join(f"• {c}" for c in collection_ids)
    except Exception as e:
        return f"Firebase error: {e}"


def _get_document(path: str, project_id=None, database="(default)") -> str:
    import requests
    try:
        token = _get_access_token()
        pid = _get_project_id(project_id)
        url = _firestore_url(pid, database, path)

        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})

        if resp.status_code == 404:
            return f"Document not found: {path}"
        elif resp.status_code != 200:
            return f"Firestore error ({resp.status_code}): {resp.text[:200]}"

        doc = resp.json()
        return json.dumps(_parse_document(doc), indent=2)
    except Exception as e:
        return f"Firebase error: {e}"


def _set_document(path: str, data: dict, project_id=None, database="(default)") -> str:
    import requests
    try:
        token = _get_access_token()
        pid = _get_project_id(project_id)
        url = _firestore_url(pid, database, path)

        fields = {k: _to_firestore_value(v) for k, v in data.items()}
        body = {"fields": fields}

        resp = requests.patch(url, headers={"Authorization": f"Bearer {token}"}, json=body)

        if resp.status_code not in (200, 201):
            return f"Firestore error ({resp.status_code}): {resp.text[:200]}"

        return f"Document written: {path}"
    except Exception as e:
        return f"Firebase error: {e}"


def _list_collection(collection: str, project_id=None, database="(default)", limit: int = 20) -> str:
    import requests
    try:
        token = _get_access_token()
        pid = _get_project_id(project_id)
        url = _firestore_url(pid, database, collection)

        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"pageSize": limit},
        )

        if resp.status_code != 200:
            return f"Firestore error ({resp.status_code}): {resp.text[:200]}"

        data = resp.json()
        documents = data.get("documents", [])

        if not documents:
            return f"No documents found in '{collection}'."

        parsed = [_parse_document(doc) for doc in documents]
        return json.dumps(parsed, indent=2)
    except Exception as e:
        return f"Firebase error: {e}"


def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "firebase_list_projects":
            return _list_projects()
        elif tool_name == "firebase_list_collections":
            return _list_collections(
                project_id=args.get("project_id"),
                database=args.get("database", "(default)"),
            )
        elif tool_name == "firebase_get_document":
            return _get_document(
                args["path"],
                project_id=args.get("project_id"),
                database=args.get("database", "(default)"),
            )
        elif tool_name == "firebase_set_document":
            return _set_document(
                args["path"],
                args["data"],
                project_id=args.get("project_id"),
                database=args.get("database", "(default)"),
            )
        elif tool_name == "firebase_list_collection":
            return _list_collection(
                args["collection"],
                project_id=args.get("project_id"),
                database=args.get("database", "(default)"),
                limit=args.get("limit", 20),
            )
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Firebase error: {e}"
