"""Source registry for dynamic source loading."""

from typing import Type

from .base import BaseSource

# Global registry for source classes
SOURCE_REGISTRY: dict[str, Type[BaseSource]] = {}


def register_source(name: str):
    """
    Decorator to register a source class in SOURCE_REGISTRY.

    Usage:
        @register_source("github_html")
        class GitHubHTMLSource(BaseSource):
            ...

    Args:
        name: Source identifier string
    """

    def decorator(cls: Type[BaseSource]) -> Type[BaseSource]:
        SOURCE_REGISTRY[name] = cls
        return cls

    return decorator


# Import all sources to trigger @register_source decorators
# This must be after SOURCE_REGISTRY and register_source are defined
from . import github_html  # noqa: E402
from . import github_trending_api  # noqa: E402
from . import hackernews  # noqa: E402
from . import juejin  # noqa: E402


__all__ = [
    "SOURCE_REGISTRY",
    "register_source",
    "github_html",
    "github_trending_api",
    "hackernews",
    "juejin",
]
