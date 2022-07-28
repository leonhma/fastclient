from enum import Enum
from typing import Mapping

from urllib3.response import HTTPResponse


class Request:
    def __init__(
            self, method, url, fields: Mapping[str, str] = None, headers: Mapping[str, str] = None, id: int = None):
        self.method = method
        self.url = url
        self.fields = fields or {}
        self.headers = headers or {}

        self.id = id


class Response:
    """
    A wrapper for urllib3.response.HTTPResponse that doesn't include the `pool` and `connection` attributes.
    """

    def __init__(self, response: HTTPResponse, id: int):
        self.headers = response.headers
        self.status = response.status
        self.version = response.version
        self.reason = response.reason
        self.strict = response.strict
        self.decode_content = response.decode_content
        self.msg = response.msg
        self.retries = response.retries
        self.enforce_content_length = response.enforce_content_length

        self.id = id


class Error:
    def __init__(self, error: BaseException, id: int):
        self.error = error
        self.id = id


class RequestEvent(Enum):
    RESPONSE = 'response'
    ERROR = 'error'
