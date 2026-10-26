# my-service: IANA service name to port resolver.
from __future__ import annotations

from .core import resolve, ServiceInfo

__all__ = ["resolve", "ServiceInfo"]
