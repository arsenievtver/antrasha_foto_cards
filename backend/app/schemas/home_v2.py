from datetime import datetime

from pydantic import BaseModel


class HomeV2GenderCardsOut(BaseModel):
    image_url_male: str | None = None
    image_url_female: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminHomeV2SettingsOut(BaseModel):
    image_url_male: str | None = None
    image_url_female: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminHomeV2SettingsPatch(BaseModel):
    clear_image_male: bool = False
    clear_image_female: bool = False


class AdminHomeV2ImageUploadResponse(BaseModel):
    image_url_male: str | None = None
    image_url_female: str | None = None
    updated_at: datetime | None = None
