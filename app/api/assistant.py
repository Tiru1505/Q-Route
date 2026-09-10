"""
The route assistant — two ways of answering, in order of trust.

`/ask` answers from the system's own state. `/chat` sends open-ended language
to a model. The first needs no API key and quotes only measured values; the
second needs one and is where free-form understanding lives.

`/ask` reaches for the model only when its own intents matched nothing, so a
question the backend can answer is never handed to something that would have to
recall the answer instead of reading it.
"""

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.models.assistant_models import (
    AssistantAskRequest,
    AssistantChatRequest,
    AssistantChatResponse,
)
from app.services.assistant_service import AssistantNotConfiguredError, AssistantService

router = APIRouter(prefix="/assistant", tags=["assistant"])
_service = AssistantService()
_logger = get_logger("api.assistant")


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Understand a natural-language navigation request",
)
async def chat(request: AssistantChatRequest) -> AssistantChatResponse:
    try:
        return await _service.chat(request)
    except AssistantNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"The AI provider could not complete the request: {exc}") from exc


@router.post(
    "/ask",
    summary="Ask the assistant a question about the current journey",
    description=(
        "Answers from the system's own state — the agent's decision, the "
        "forecaster's output, the active trip, the traffic layer, and what "
        "vision has counted.\n\n"
        "This needs no API key. Every figure it quotes was measured elsewhere "
        "in the backend rather than produced by a language model, and "
        "`source` says so: `measured` for an answer built from state, "
        "`llm` when a configured model handled a question the intents did not "
        "cover, `unmatched` when neither could.\n\n"
        "When the question falls outside what the system knows and no model is "
        "configured, it says what it can answer instead of guessing."
    ),
)
async def ask(request: AssistantAskRequest) -> dict:
    from app.core.config import get_settings
    from app.services import helper_service

    result = helper_service.answer(request.question, graph=request.graph)

    # A model, when there is one, handles only what the intents did not match —
    # never a question the system could answer itself, because a measured
    # figure must not be replaced by a recalled one.
    if result.get("source") == "unmatched" and get_settings().ai_api_key:
        try:
            chat_request = AssistantChatRequest(
                messages=[{"role": "user", "content": request.question}],
                context=request.context or {},
            )
            response = await _service.chat(chat_request)
            return {
                "text": response.message,
                "intent": None,
                "source": "llm",
                "actions": [a.model_dump() for a in (response.actions or [])],
            }
        except Exception as exc:
            _logger.warning("Assistant fallback failed: %s", exc)

    return result


@router.get(
    "/briefing",
    summary="What the assistant would say unprompted",
    description=(
        "The current prediction for the journey in progress, in one short "
        "message. The interface shows this when the assistant is opened, so "
        "the driver is told the forecast without having to think of the "
        "question."
    ),
)
def briefing(graph: str | None = Query(default=None)) -> dict:
    from app.services import helper_service

    return helper_service.answer("what is the forecast", graph=graph)
