"""
Custom exception types for forexfactory.
"""


class AutoFetchError(RuntimeError):
    """Raised when a CACHE-03 scope-miss auto-widen cannot obtain the requested data (D-06)."""
