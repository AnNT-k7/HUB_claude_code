from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings
from app.services.storage import ObjectStorage, create_object_storage


@dataclass(frozen=True)
class OfficerContext:
    officer_id: str


def get_current_officer(
    x_officer_id: Annotated[str | None, Header(alias="X-Officer-ID")] = None,
) -> OfficerContext:
    """Development identity boundary; replace with bank SSO in production."""

    settings = get_settings()
    officer_id = (x_officer_id or "").strip()
    if not officer_id and settings.environment == "development":
        officer_id = settings.demo_officer_id
    if not officer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Officer identity is required",
        )
    if len(officer_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Officer identity is invalid",
        )
    return OfficerContext(officer_id=officer_id)


CurrentOfficer = Annotated[OfficerContext, Depends(get_current_officer)]


def get_policy_admin(officer: CurrentOfficer) -> OfficerContext:
    if officer.officer_id not in get_settings().policy_admin_officer_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Policy administrator permission is required",
        )
    return officer


PolicyAdmin = Annotated[OfficerContext, Depends(get_policy_admin)]


@lru_cache
def get_object_storage() -> ObjectStorage:
    return create_object_storage()


ObjectStorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
