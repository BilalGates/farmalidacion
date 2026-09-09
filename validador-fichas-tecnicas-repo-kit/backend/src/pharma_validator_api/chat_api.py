from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from pharma_validator_api.contextual_chat import ContextualChatError, answer_from_document
from pharma_validator_api.errors import ApplicationError
from pharma_validator_api.records import SessionDependency

router = APIRouter(prefix="/records", tags=["consulta documental"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)


@router.post("/{record_id}/chat")
def chat(record_id: str, payload: ChatRequest, session: SessionDependency) -> dict[str, object]:
    try:
        result = answer_from_document(session, record_id=record_id, question=payload.question)
    except ContextualChatError as error:
        raise ApplicationError(str(error), status_code=400) from error
    return {
        "status": result.status,
        "message": result.message,
        "citations": [
            {
                "document_version_id": item.document_version_id,
                "section": item.section,
                "literal_text": item.literal_text,
            }
            for item in result.citations
        ],
    }
