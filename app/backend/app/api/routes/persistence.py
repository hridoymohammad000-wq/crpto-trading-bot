from typing import cast

from fastapi import APIRouter, Request

from app.persistence import PersistenceDatabase

router = APIRouter()


@router.get("/system/persistence")
def get_persistence_status(request: Request) -> dict[str, object]:
    db = cast(PersistenceDatabase, request.app.state.persistence_database)
    status = db.health()
    status["restart_behavior"] = "manual_start_required"
    return status
