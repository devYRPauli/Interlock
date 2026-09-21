"""Publication input validation and canonical payload encoding."""

import json
from typing import TypedDict


class PublicationRejected(ValueError):
    """The provider definitely rejected a request without publishing it."""


class PublicationRequest(TypedDict):
    request_id: str
    name: str
    expected_version: int
    content: str
    approval_id: str


def request(
    request_id: str, name: str, expected_version: int, content: str, approval_id: str
) -> PublicationRequest:
    values: PublicationRequest = dict(
        request_id=request_id,
        name=name,
        expected_version=expected_version,
        content=content,
        approval_id=approval_id,
    )
    for field, value in (("request_id", request_id), ("name", name), ("approval_id", approval_id)):
        if not isinstance(value, str) or not value.strip():
            raise PublicationRejected(f"{field} must be a nonempty string")
    if type(expected_version) is not int or expected_version < 0:
        raise PublicationRejected(
            "expected_version must be a nonnegative integer; 0 creates an artifact"
        )
    if not isinstance(content, str):
        raise PublicationRejected("content must be text")
    return values


def encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
