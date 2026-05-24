"""Ximilar Fashion Tagging API client."""

from __future__ import annotations

import logging
from typing import Any

from app.externals.http.base import BaseApiClient
from app.externals.http.exceptions import ApiClientAbortableException

log = logging.getLogger("app.ximilar")


class XimilarClient(BaseApiClient):
    BASE_URL = "https://api.ximilar.com/tagging/fashion/v2/"

    def __init__(self, api_token: str) -> None:
        super().__init__(keep_session=False)
        self._api_token = api_token.strip()

    @property
    def base_url(self) -> str:
        return self.BASE_URL

    @property
    def base_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self._api_token}",
        }

    def _records_body(self, image_url: str) -> dict[str, Any]:
        return {"records": [{"_url": image_url}]}

    async def detect_tags(self, image_url: str) -> dict[str, Any]:
        resp = await self.post("/detect_tags", json=self._records_body(image_url))
        return resp.parsed_response

    async def detect_tags_all(self, image_url: str) -> dict[str, Any]:
        """Tries detect_tags_all first; falls back to detect_tags on 403."""
        body = self._records_body(image_url)
        resp = await self.post("/detect_tags_all", json=body, raise_for_status=False)
        if resp.status < 400:
            return resp.parsed_response
        if resp.status == 403:
            log.warning("ximilar detect_tags_all → 403, fallback to detect_tags")
            return (await self.post("/detect_tags", json=body)).parsed_response
        raise ApiClientAbortableException(
            response=resp.raw_response,
            parsed_response=resp.parsed_response,
        )