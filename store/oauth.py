"""Provider-neutral contracts for a future OAuth/social login integration."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OAuthIdentityData:
    subject: str
    email: str = ""
    profile: dict = field(default_factory=dict)


class BaseOAuthProvider(ABC):
    code = ""

    @abstractmethod
    def authorization_url(self, *, state, redirect_uri):
        raise NotImplementedError

    @abstractmethod
    def exchange_code(self, *, code, redirect_uri):
        """Return a verified OAuthIdentityData value."""
        raise NotImplementedError


_providers = {}


def register_oauth_provider(provider):
    _providers[provider.code] = provider


def get_oauth_provider(code):
    try:
        return _providers[code]
    except KeyError as error:
        raise ValueError(f"OAuth-провайдер не настроен: {code}") from error
