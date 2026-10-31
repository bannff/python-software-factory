"""Native agentic-generation stages for the dataset brick.

Ported from bannff/Agentic-Datasets@26cb683 (the v2 stage callables). Each
stage is a pure generator over ``ConversationRecord`` values; LLM access is
injected through the ``CompletionPort`` protocol (``runtime/ports.py``).
"""

from .agentinstruct import agentinstruct
from .apigenmt import apigenmt
from .reviewinstruct import reviewinstruct
from .s2m import s2m

__all__ = ["agentinstruct", "apigenmt", "reviewinstruct", "s2m"]
