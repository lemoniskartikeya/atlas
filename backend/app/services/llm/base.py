"""The provider interface the coach talks to."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol


class LLMError(RuntimeError):
    """A provider call failed in a way worth showing the user.

    Carries a message already written for a person — "that key was rejected",
    not a raw 401 body. The coach falls back to its offline answer either way;
    this is what the Settings page shows when they press "Test".
    """


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ProviderInfo:
    """Everything the UI needs to offer a provider without hardcoding it."""

    id: str
    label: str
    default_model: str
    #: Where the user goes to get a key. Atlas cannot obtain one for them.
    key_url: Optional[str]
    #: Honest one-liner about cost, shown next to the choice.
    cost_note: str
    #: True when no key is needed (a model running on this machine).
    local: bool = False
    #: Models worth offering in a dropdown. Free-form entry is still allowed.
    suggested_models: list[str] = field(default_factory=list)


class Provider(Protocol):
    info: ProviderInfo

    def complete(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        model: str,
        api_key: Optional[str],
        max_tokens: int,
        timeout: float,
    ) -> str:
        """Return the assistant's reply text, or raise LLMError."""
        ...


def normalise(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Drop empties and guarantee the turn order every provider expects.

    Chat APIs are near-universally strict about starting on a user turn and
    alternating from there; the coach's history can violate both after a
    failed request or a UI retry.
    """
    cleaned = [
        ChatMessage(role=m.role, content=m.content.strip())
        for m in messages
        if m.role in ("user", "assistant") and m.content.strip()
    ]

    collapsed: list[ChatMessage] = []
    for msg in cleaned:
        if collapsed and collapsed[-1].role == msg.role:
            collapsed[-1] = ChatMessage(
                role=msg.role, content=f"{collapsed[-1].content}\n\n{msg.content}"
            )
        else:
            collapsed.append(msg)

    while collapsed and collapsed[0].role != "user":
        collapsed.pop(0)

    if not collapsed:
        collapsed = [
            ChatMessage(
                role="user",
                content="Give me a short read on how I'm doing and what to focus on.",
            )
        ]
    return collapsed
