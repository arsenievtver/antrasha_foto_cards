import asyncio
import dataclasses
import logging
from datetime import timedelta
from typing import Any, Mapping, Tuple
from urllib.parse import urljoin
from failsafe import Delay, Failsafe, FailsafeError, RetryPolicy

import ujson
from aiohttp import (
    ClientConnectionError,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
)
from app.externals.http.exceptions import (
    ApiClientAbortableException,
    ApiClientRetriableException,
)

DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
FAILSAFE_ALLOWED_RETRIES = 3
FAILSAFE_BACKOFF_SECONDS = 0.5



@dataclasses.dataclass
class BaseApiClientResponse:
    raw_response: ClientResponse
    status: int
    headers: Mapping
    parsed_response: dict | list | Any = None


class BaseApiClient:
    _session = None
    request_timeout_seconds: int = DEFAULT_REQUEST_TIMEOUT_SECONDS
    allowed_retries: int = FAILSAFE_ALLOWED_RETRIES
    backoff_seconds: float = FAILSAFE_BACKOFF_SECONDS
    abortable_exceptions: list[Exception] = [ApiClientAbortableException]
    retriable_exceptions: list[Exception] = [
        ApiClientRetriableException,
        ClientConnectionError,
        asyncio.exceptions.TimeoutError,
        asyncio.TimeoutError,
        TimeoutError,
    ]

    def __init__(self, keep_session: bool = False):
        self.logger = logging.getLogger('control')
        self.failsafe = self._init_failsafe()
        self.keep_session = keep_session

    @property
    def base_url(self) -> str:
        raise NotImplementedError('`base_url` must be defined')

    @property
    def base_headers(self) -> dict:
        return {}

    def _init_failsafe(self) -> Failsafe:
        retry_policy = RetryPolicy(
            allowed_retries=self.allowed_retries,
            backoff=Delay(timedelta(seconds=self.backoff_seconds)),
            abortable_exceptions=self.abortable_exceptions,
            retriable_exceptions=self.retriable_exceptions,
        )
        return Failsafe(retry_policy=retry_policy)

    @property
    def session(self) -> ClientSession:
        if self._session is None or self._session.closed:

            self._session = ClientSession(
                headers=self.base_headers,
                json_serialize=ujson.dumps,
                timeout=ClientTimeout(total=self.request_timeout_seconds),
            )

        return self._session

    @staticmethod
    async def _parse(response: ClientResponse) -> dict | list:
        try:
            json_response = await response.json(loads=ujson.loads)
        except (ContentTypeError, ujson.JSONDecodeError):
            json_response = None
        return json_response

    async def handle_errors(
        self, response: ClientResponse, parsed_response: dict | list
    ) -> None:
        if response.status >= 500:
            raise ApiClientRetriableException(
                response=response, parsed_response=parsed_response
            )
        elif response.status >= 400:
            raise ApiClientAbortableException(
                response=response, parsed_response=parsed_response
            )

    async def _make_request(
        self, method: str, url: str, **kwargs
    ) -> Tuple[ClientResponse, dict | list]:
        payload_ctx = {'payload': kwargs.get('json') or kwargs.get('data')}
        async with self.session.request(
            method,
            url,
            raise_for_status=False,
            trace_request_ctx=payload_ctx,
            **kwargs
        ) as response:
            parsed_response = await self._parse(response)
            await self.handle_errors(response, parsed_response)
        if not self.keep_session:
            await self.close()
        return response, parsed_response

    async def close(self) -> None:
        if self.session is None:
            return None
        await self.session.close()

    async def request(
        self, method: str, endpoint: str, **params
    ) -> BaseApiClientResponse:
        raise_for_status = params.pop('raise_for_status', True)
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        orig_error, response, parsed_response = None, None, None
        try:
            response, parsed_response = await self.failsafe.run(
                lambda: self._make_request(method, url, **params)
            )
        except FailsafeError as e:
            orig_error = e.__cause__ or e
            if isinstance(orig_error, ApiClientRetriableException):
                response = orig_error.response
                parsed_response = orig_error.parsed_response
            else:
                raise orig_error
        except ApiClientAbortableException as e:
            orig_error = e
            response = e.response
            parsed_response = e.parsed_response
        finally:
            if orig_error is not None:
                if raise_for_status:
                    raise orig_error
            return BaseApiClientResponse(
                raw_response=response,
                status=response.status,
                headers=response.headers,
                parsed_response=parsed_response,
            )

    async def get(self, endpoint: str, **kwargs) -> BaseApiClientResponse:
        return await self.request('get', endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> BaseApiClientResponse:
        return await self.request('post', endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> BaseApiClientResponse:
        return await self.request('put', endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> BaseApiClientResponse:
        return await self.request('patch', endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> BaseApiClientResponse:
        return await self.request('delete', endpoint, **kwargs)
