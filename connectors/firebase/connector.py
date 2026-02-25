"""
Firebase connector — Read/write Firestore documents.

Authentication priority:
  1. FIREBASE_ACCESS_TOKEN env var (for testing / CI)
  2. gcloud auth print-access-token (if gcloud CLI is installed)
  3. Google Application Default Credentials (ADC)

Project detection priority:
  1. FIREBASE_PROJECT_ID env var
  2. .firebaserc in project root
  3. gcloud config project
"""

import os
import json


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
    """Get a Google access token. No hardcoded credentials."""
    import subprocess

    # 1. Explicit token from env (for CI/testing)
    token = os.environ.get("FIREBASE_ACCESS_TOKEN", "").strip()
    if token:
        return token

    # 2. gcloud CLI (most common for local dev)
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 3. Application Default Credentials via google-auth
    try:
        import google.auth
        import google.auth.transport.requests

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        if creds.token:
            return creds.token
    except Exception:
        pass

    raise ValueError(
        "No auth found. Options:\n"
        "  1. Install gcloud CLI and run: gcloud auth login\n"
        "  2. Set FIREBASE_ACCESS_TOKEN env var\n"
        "  3. Set up Application Default Credentials: gcloud auth application-default login"
    )


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


def _get_quota_project():
    """Get the gcloud quota project for API billing attribution."""
    import subprocess
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _auth_headers(project_id=None):
    """Build auth headers including quota project."""
    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    # Firebase Management API requires a quota project header with user credentials
    quota_project = project_id or _get_quota_project()
    if quota_project:
        headers["x-goog-user-project"] = quota_project
    return headers


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
        headers = _auth_headers()
        resp = requests.get(
            "https://firebase.googleapis.com/v1beta1/projects?pageSize=50",
            headers=headers,
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
        pid = _get_project_id(project_id)
        url = f"https://firestore.googleapis.com/v1/projects/{pid}/databases/{database}/documents:listCollectionIds"
        headers = _auth_headers(pid)
        headers["Content-Type"] = "application/json"

        resp = requests.post(url, headers=headers, json={})

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
        pid = _get_project_id(project_id)
        url = _firestore_url(pid, database, path)

        resp = requests.get(url, headers=_auth_headers(pid))

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
        pid = _get_project_id(project_id)
        url = _firestore_url(pid, database, path)

        fields = {k: _to_firestore_value(v) for k, v in data.items()}
        body = {"fields": fields}

        resp = requests.patch(url, headers=_auth_headers(pid), json=body)

        if resp.status_code not in (200, 201):
            return f"Firestore error ({resp.status_code}): {resp.text[:200]}"

        return f"Document written: {path}"
    except Exception as e:
        return f"Firebase error: {e}"


def _list_collection(collection: str, project_id=None, database="(default)", limit: int = 20) -> str:
    import requests
    try:
        pid = _get_project_id(project_id)
        url = _firestore_url(pid, database, collection)

        resp = requests.get(
            url,
            headers=_auth_headers(pid),
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
