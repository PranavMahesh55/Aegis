import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from datahub_actions.action.action import Action
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ForwardChangeConfig(BaseModel):
    endpoint: str = "http://aegis:8000/api/integrations/datahub/events"
    shared_secret: str = Field(min_length=12)
    timeout_seconds: float = 5.0


class ForwardAegisChangeAction(Action):
    """Forward relevant DataHub MCL/ECE events to Aegis with payload authentication."""

    RELEVANT_MARKERS = (
        "refund-policy",
        "refund-rag-index",
        "risk-features",
        "refund-resolution-agent",
        "account-risk-agent",
    )

    @classmethod
    def create(cls, config_dict: dict[str, Any], ctx: Any) -> "ForwardAegisChangeAction":
        return cls(ForwardChangeConfig.model_validate(config_dict or {}))

    def __init__(self, config: ForwardChangeConfig) -> None:
        self.config = config
        self.client = httpx.Client(timeout=config.timeout_seconds)

    def act(self, event: Any) -> None:
        payload = json.loads(event.as_json())
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if not any(marker in encoded.decode(errors="ignore") for marker in self.RELEVANT_MARKERS):
            return
        digest = hashlib.sha256(encoded).hexdigest()
        signature = hmac.new(
            self.config.shared_secret.encode(), encoded, hashlib.sha256
        ).hexdigest()
        response = self.client.post(
            self.config.endpoint,
            content=encoded,
            headers={
                "Content-Type": "application/json",
                "X-Aegis-Signature": f"sha256={signature}",
                "X-DataHub-Event-Id": digest,
            },
        )
        response.raise_for_status()
        logger.info("Forwarded DataHub change event %s to Aegis", digest)

    def close(self) -> None:
        self.client.close()
