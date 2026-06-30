from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user_dep
from app.analytics.logging.logger import end_session, log_reaction, log_final_reaction

router = APIRouter(prefix="/analytics", tags=["analytics"])


class SessionEndRequest(BaseModel):
    session_id: str = Field(min_length=1)


class ReactionRequest(BaseModel):
    session_id: str = Field(min_length=1)
    reaction: bool


class FinalReactionRequest(BaseModel):
    session_id: str = Field(min_length=1)
    final_reaction: bool


@router.post("/session_end")
def session_end(req: SessionEndRequest, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user_dep)):
    """Notify backend that a web session ended — forwards to Kafka logger."""
    end_session(req.session_id, background_tasks)
    return {"success": True}


@router.post("/reaction")
def reaction(req: ReactionRequest, current_user: dict = Depends(get_current_user_dep)):
    """Log a like/dislike reaction on a single bot message."""
    log_reaction(reaction=req.reaction, session_id=req.session_id)
    return {"success": True}


@router.post("/final_reaction")
def final_reaction(req: FinalReactionRequest, current_user: dict = Depends(get_current_user_dep)):
    """Log the overall session satisfaction (like/dislike) at end of session."""
    log_final_reaction(final_reaction=req.final_reaction, session_id=req.session_id)
    return {"success": True}
