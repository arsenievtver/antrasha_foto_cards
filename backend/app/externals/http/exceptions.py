from aiohttp import ClientResponse


class ApiClientRetriableException(Exception):
    def __init__(
            self,
            response: ClientResponse,
            parsed_response: dict | list,
            *args,
            **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.response = response
        self.parsed_response = parsed_response


class ApiClientAbortableException(Exception):
    def __init__(
        self,
        response: ClientResponse,
        parsed_response: dict | list,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.response = response
        self.parsed_response = parsed_response


DEFAULT_EXTERNAL_ERROR_MESSAGE = "External service error"
DEFAULT_EXTERNAL_SERVICE_ERROR_CODE = "external_service_error"
DEFAULT_EXTERNAL_TERMINAL_ERROR_CODE = "external_terminal_error"
DEFAULT_EXTERNAL_TRANSIENT_ERROR_CODE = "external_transient_error"
DEFAULT_EXTERNAL_TIMEOUT_ERROR_CODE = "timeout_error"


class ExternalError(Exception):
    msg: str = DEFAULT_EXTERNAL_ERROR_MESSAGE
    code: str = DEFAULT_EXTERNAL_SERVICE_ERROR_CODE
    context: dict

    def __init__(
        self,
        msg: str | None = None,
        code: str | None = None,
        context: dict | None = None,
    ):
        self.msg = msg or self.msg
        self.code = code or self.code
        self.context = context or {}

    def __str__(self):
        msg = "%s: Code: %s | Context: %s" % (self.msg, self.code, self.context)
        return msg

    def __repr__(self):
        return self.__str__()


class ExternalTerminalError(ExternalError):
    code: str = DEFAULT_EXTERNAL_TERMINAL_ERROR_CODE


class ExternalTransientError(ExternalError):
    code: str = DEFAULT_EXTERNAL_TRANSIENT_ERROR_CODE


class ExternalTimeoutError(ExternalTransientError):
    code: str = DEFAULT_EXTERNAL_TIMEOUT_ERROR_CODE


class OrderDoesNotExist(Exception):
    pass


class ConfigNotFoundError(Exception):
    pass


class WebDavClientError(Exception):
    pass


class NoDataGotFromConsulHosts(Exception):
    pass
