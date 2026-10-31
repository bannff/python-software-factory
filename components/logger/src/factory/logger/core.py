"""Legacy core module - delegates to runtime.

New code should use the runtime module directly.
"""

from factory.logger.runtime.runtime import LoggerRuntime

__all__ = ["LoggerRuntime"]
