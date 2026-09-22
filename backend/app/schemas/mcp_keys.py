import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.mcp_api_key import McpApiKey
from app.services.mcp_keys import SCOPE_READ, SCOPES, mask_key


class McpKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    masked_key: str
    key: str | None
    scope: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None


class McpKeyCreated(McpKeyRead):
    key: str


class McpKeyCreateInput(BaseModel):
    name: str = Field(default="MCP клиент", max_length=100)
    scope: str = Field(default=SCOPE_READ, description="'read' или 'write'")

    @field_validator("scope")
    @classmethod
    def scope_is_known(cls, value: str) -> str:
        if value not in SCOPES:
            raise ValueError(f"Допустимые значения scope: {', '.join(SCOPES)}")
        return value

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Укажите название ключа")
        return cleaned


def serialize_key(key: McpApiKey) -> McpKeyRead:
    return McpKeyRead(
        id=key.id,
        name=key.name,
        masked_key=mask_key(key),
        key=key.key_plain,
        scope=key.scope,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
    )


def serialize_created_key(key: McpApiKey, plaintext: str) -> McpKeyCreated:
    data = serialize_key(key).model_dump()
    data["key"] = plaintext
    return McpKeyCreated.model_validate(data)
