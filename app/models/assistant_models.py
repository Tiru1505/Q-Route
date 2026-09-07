"""Models for the natural-language navigation assistant."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=12000)


class AssistantContext(BaseModel):
    start: dict[str, Any] | None = None
    destination: dict[str, Any] | None = None
    current_route: dict[str, Any] | None = None
    routes: list[dict[str, Any]] = Field(default_factory=list)
    selected_route: dict[str, Any] | None = None
    traffic: dict[str, Any] | None = None


class AssistantChatRequest(BaseModel):
    messages: list[AssistantMessage] = Field(..., min_length=1, max_length=40)
    context: AssistantContext = Field(default_factory=AssistantContext)


class AssistantAction(BaseModel):
    type: Literal["set_start", "set_destination", "route_result", "alternatives", "reroute"]
    payload: dict[str, Any]


class AssistantChatResponse(BaseModel):
    message: str
    actions: list[AssistantAction] = Field(default_factory=list)
    provider: str
    model: str
