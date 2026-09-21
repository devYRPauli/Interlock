"""Small stdio MCP example; use through interlock.mcp_proxy (see README.md)."""

import argparse
import json
import sys
from typing import Any, Callable, Optional

from .models import PublicationRejected
from .storage import ArtifactStore


def schema(properties: dict[str, Any], required: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


TEXT = {"type": "string"}
PUBLISH = {
    "request_id": TEXT,
    "name": TEXT,
    "expected_version": {"type": "integer", "minimum": 0},
    "content": TEXT,
    "approval_id": TEXT,
    "reference": TEXT,
}
TOOLS = [
    {
        "name": "get_artifact",
        "description": "Read the current artifact and version; version 0 means absent.",
        "inputSchema": schema({"name": TEXT}),
    },
    {
        "name": "find_publication",
        "description": "Look up a historical operation, even after newer publications.",
        "inputSchema": schema({"reference": TEXT}),
    },
    {
        "name": "get_approval",
        "description": "Read an operator-issued grant. Agents cannot issue approvals.",
        "inputSchema": schema({"approval_id": TEXT}),
    },
    {
        "name": "publish_artifact",
        "description": "Publish approved text if the destination version still matches. "
        "The proxy supplies reference; reuse the exact request when recovering.",
        "inputSchema": schema(PUBLISH, [key for key in PUBLISH if key != "reference"]),
    },
]


def tool_functions(store: ArtifactStore) -> dict[str, Callable[..., dict[str, Any]]]:
    """Expose only publication/read operations; approvals stay with the operator."""
    return {
        "get_artifact": store.get_artifact,
        "find_publication": store.find_publication,
        "get_approval": store.get_approval,
        "publish_artifact": store.publish_artifact,
    }


def call_tool(store: ArtifactStore, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        result = tool_functions(store)[name](**arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(result)}],
            "structuredContent": result,
        }
    except PublicationRejected as error:
        # Only definite rejections are tool errors. A database/transport failure exits
        # the server: the proxy must leave a potentially committed send unresolved.
        return {"isError": True, "content": [{"type": "text", "text": str(error)}]}


def serve(store: ArtifactStore) -> None:
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        method, params = message.get("method"), message.get("params", {})
        reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
        if method == "initialize":
            reply["result"] = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "interlock-artifact-example", "version": "0.1.0"},
            }
        elif method == "ping":
            reply["result"] = {}
        elif method == "tools/list":
            reply["result"] = {"tools": TOOLS}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            if name not in tool_functions(store):
                reply["error"] = {"code": -32602, "message": "Unknown tool"}
            else:
                reply["result"] = call_tool(store, name, arguments)
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        print(json.dumps(reply), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Existing artifact SQLite database")
    args = parser.parse_args()
    serve(ArtifactStore(args.db))


if __name__ == "__main__":
    main()
