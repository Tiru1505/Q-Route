"""Natural-language route assistant endpoint."""

from fastapi import APIRouter, HTTPException

from app.models.assistant_models import AssistantChatRequest, AssistantChatResponse
from app.services.assistant_service import AssistantNotConfiguredError, AssistantService

router = APIRouter(prefix="/assistant", tags=["assistant"])
_service = AssistantService()


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
