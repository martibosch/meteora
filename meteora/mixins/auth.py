"""Authentication mixins."""

from abc import ABC, abstractmethod

from better_abc import abstract_attribute


class APIKeyMixin(ABC):
    """API key mixin."""

    @abstract_attribute
    def _api_key(self):
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
    @abstractmethod
    def _api_key_param_name(self):
        pass

    @property
    def request_params(self):
        """Request parameters."""
        try:
            return self._request_params
        except AttributeError:
            self._request_params = {self._api_key_param_name: self._api_key}
            return self._request_params
