import base64
import hashlib
import hmac
import json
import math
import time
from typing import Any
from uuid import uuid4


class InvalidCapability(ValueError):
    pass


def _normalize_json(value: Any) -> Any:
    """Normalize JSON numbers across model JSON and typed MCP boundaries.

    A model response decodes ``1500`` as an int, while a FastMCP ``float``
    parameter arrives at the executor as ``1500.0``. They are the same JSON
    number and must produce the same capability hash without weakening binding
    for genuinely different values.
    """
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Capability arguments must contain finite numbers")
        return int(value) if value.is_integer() else value
    if isinstance(value, dict):
        return {key: _normalize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _canonical_args(arguments: dict[str, Any]) -> str:
    return json.dumps(_normalize_json(arguments), sort_keys=True, separators=(",", ":"))


def arguments_hash(arguments: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_args(arguments).encode()).hexdigest()


def mint_capability(
    secret: str,
    *,
    tool: str,
    arguments: dict[str, Any],
    run_id: str,
    ttl_seconds: int = 30,
) -> str:
    payload = {
        "tool": tool,
        "argumentsHash": arguments_hash(arguments),
        "runId": run_id,
        "decision": "ALLOW",
        "exp": int(time.time()) + ttl_seconds,
        "jti": uuid4().hex,
    }
    encoded = base64.urlsafe_b64encode(_canonical_args(payload).encode()).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def verify_capability(
    secret: str, token: str, *, tool: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(
            supplied_signature + "=" * (-len(supplied_signature) % 4)
        )
        if not hmac.compare_digest(expected, supplied):
            raise InvalidCapability("Capability signature is invalid")
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw)
    except InvalidCapability:
        raise
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise InvalidCapability("Capability token is malformed") from error
    if payload.get("decision") != "ALLOW":
        raise InvalidCapability("Capability does not carry an ALLOW decision")
    if payload.get("tool") != tool:
        raise InvalidCapability("Capability is bound to another tool")
    if payload.get("argumentsHash") != arguments_hash(arguments):
        raise InvalidCapability("Capability arguments do not match")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise InvalidCapability("Capability has expired")
    if not payload.get("jti"):
        raise InvalidCapability("Capability has no unique identifier")
    return payload
