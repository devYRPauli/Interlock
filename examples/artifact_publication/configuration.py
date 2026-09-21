"""Configuration for Interlock's artifact-publication gate."""

from pathlib import Path
from typing import Any, Union


def configuration(journal_dir: Union[str, Path]) -> dict[str, Any]:
    return {
        "journal_dir": str(journal_dir),
        "tools": {
            "publish_artifact": {
                "key": ["request_id"],
                "premises": {
                    "tool": "get_artifact",
                    "arguments": {"name": "name"},
                    "fields": ["version"],
                },
                "lookup": {
                    "tool": "find_publication",
                    "arguments": {"reference": "$effect_id"},
                    "found": "found",
                },
                "approval": {"tool": "get_approval", "arguments": {"approval_id": "approval_id"}},
                "idempotency_argument": "reference",
                # Prefer historical lookup during recovery. The provider also deduplicates in its transaction.
                "dedupes": False,
            }
        },
    }
