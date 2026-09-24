class BybitError(Exception):
    """Base exception for Bybit Demo client failures."""


class BybitAuthenticationError(BybitError):
    """Raised when a private request cannot be authenticated."""


class BybitAPIError(BybitError):
    """Raised when Bybit returns an invalid or unsuccessful response."""


class BybitConnectionError(BybitError):
    """Raised when the Bybit Demo API cannot be reached."""
