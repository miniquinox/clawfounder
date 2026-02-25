"""
Firebase connector — Read/write Firestore documents via firebase-admin SDK.
"""

import os
import json

TOOLS = [
    {
        "name": "firebase_get_document",
        "description": "Read a Firestore document by its path (e.g., 'users/user123').",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Document path in 'collection/document' format",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "firebase_list_collection",
        "description": "List documents in a Firestore collection.",
        "parameters": {
            "type": "object",
            "properties": {
                "collection": {
                    "type": "string",
                    "description": "Collection name (e.g., 'users')",
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
        "name": "firebase_set_document",
        "description": "Write or update a Firestore document.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Document path in 'collection/document' format",
                },
                "data": {
                    "type": "string",
                    "description": "JSON string of the document data",
                },
                "merge": {
                    "type": "boolean",
                    "description": "If true, merge with existing data instead of overwriting (default: true)",
                },
            },
            "required": ["path", "data"],
        },
    },
]


_initialized = False


def _init_firebase():
    global _initialized
    if _initialized:
        return

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        raise ImportError("firebase-admin not installed. Run: bash connectors/firebase/install.sh")

    creds_file = os.environ.get("FIREBASE_CREDENTIALS_FILE")
    project_id = os.environ.get("FIREBASE_PROJECT_ID")

    if not creds_file:
        raise ValueError("FIREBASE_CREDENTIALS_FILE not set in .env")
    if not os.path.exists(creds_file):
        raise FileNotFoundError(f"Firebase credentials file not found: {creds_file}")

    cred = credentials.Certificate(creds_file)
    firebase_admin.initialize_app(cred, {"projectId": project_id})
    _initialized = True


def _get_document(path: str) -> str:
    _init_firebase()
    from firebase_admin import firestore
    db = firestore.client()
    doc = db.document(path).get()
    if doc.exists:
        return json.dumps(doc.to_dict(), indent=2, default=str)
    return f"Document not found: {path}"


def _list_collection(collection: str, limit: int = 20) -> str:
    _init_firebase()
    from firebase_admin import firestore
    db = firestore.client()
    docs = db.collection(collection).limit(limit).stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        data["_id"] = doc.id
        result.append(data)
    if not result:
        return f"No documents found in collection: {collection}"
    return json.dumps(result, indent=2, default=str)


def _set_document(path: str, data: str, merge: bool = True) -> str:
    _init_firebase()
    from firebase_admin import firestore
    db = firestore.client()
    doc_data = json.loads(data)
    db.document(path).set(doc_data, merge=merge)
    return f"Document written to: {path}"


def handle(tool_name: str, args: dict) -> str:
    try:
        if tool_name == "firebase_get_document":
            return _get_document(args["path"])
        elif tool_name == "firebase_list_collection":
            return _list_collection(args["collection"], args.get("limit", 20))
        elif tool_name == "firebase_set_document":
            return _set_document(args["path"], args["data"], args.get("merge", True))
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        return f"Firebase error: {e}"
