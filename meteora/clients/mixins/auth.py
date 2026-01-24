"""Authentication mixins."""

import abc

from meteora import utils


class APIKeyMixin(abc.ABC):
    """API key mixin."""

    @utils.abstract_attribute
    def _api_key(self) -> str:
        # https://stackoverflow.com/questions/23831510/abstract-attribute-not-property
        pass


class APIKeyHeaderMixin(APIKeyMixin):
    """API key as request header mixin."""

    @property
    def request_headers(self) -> dict:
        """Request headers."""
        try:
            return self._request_headers
        except AttributeError:
            self._request_headers = {"X-API-KEY": self._api_key}
            return self._request_headers


class APIKeyParamMixin(APIKeyMixin):
    """API key as request parameter mixin."""

    @property
    @abc.abstractmethod
    def _api_key_param_name(self) -> str:
        pass

    @property
    def request_params(self) -> dict:
        """Request parameters."""
        try:
            return self._request_params
        except AttributeError:
            self._request_params = {self._api_key_param_name: self._api_key}
            return self._request_params
