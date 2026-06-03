import uuid

from pydantic import BaseModel, Field


class TryOnExperimentStatusOut(BaseModel):
    enabled: bool
    message: str | None = None


class TryOnCatalogPhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    gender: str
    brand: str | None = None


class TryOnCatalogResponse(BaseModel):
    photos: list[TryOnCatalogPhotoOut]


class TryOnRunResponse(BaseModel):
    result_url: str
    photo_id: uuid.UUID
    elapsed_seconds: float = Field(description="Server-side Fashn round-trip time")
