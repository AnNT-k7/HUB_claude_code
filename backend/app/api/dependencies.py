from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWTError, decode

from app.config import get_settings
from app.services.storage import ObjectStorage, create_object_storage


@dataclass(frozen=True)
class OfficerContext:
    officer_id: str
    roles: frozenset[str] = frozenset()


_bearer = HTTPBearer(auto_error=False)


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def get_current_officer(
    x_officer_id: Annotated[str | None, Header(alias="X-Officer-ID")] = None,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ] = None,
) -> OfficerContext:
    """Use explicit demo identity locally and verified OIDC/JWT claims elsewhere."""

    settings = get_settings()
    if settings.auth_mode == "jwt":
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A verified bearer token is required",
            )
        try:
            signing_key = _jwks_client(settings.jwt_jwks_url or "").get_signing_key_from_jwt(
                credentials.credentials
            )
            claims = decode(
                credentials.credentials,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
            )
        except PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token validation failed",
            ) from exc
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token has no subject",
            )
        raw_roles = claims.get("roles", [])
        roles = (
            {str(item) for item in raw_roles}
            if isinstance(raw_roles, list)
            else {str(raw_roles)}
        )
        scope = claims.get("scope")
        if isinstance(scope, str):
            roles.update(scope.split())
        return OfficerContext(subject, frozenset(roles))

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
    return OfficerContext(officer_id=officer_id, roles=frozenset({"demo"}))


CurrentOfficer = Annotated[OfficerContext, Depends(get_current_officer)]


def get_policy_admin(officer: CurrentOfficer) -> OfficerContext:
    settings = get_settings()
    allowed = (
        bool(officer.roles.intersection(settings.policy_admin_roles))
        if settings.auth_mode == "jwt"
        else officer.officer_id in settings.policy_admin_officer_ids
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Policy administrator permission is required",
        )
    return officer


PolicyAdmin = Annotated[OfficerContext, Depends(get_policy_admin)]


def require_case_access(created_by: str, officer: OfficerContext) -> None:
    settings = get_settings()
    if officer.officer_id == created_by:
        return
    if officer.roles.intersection(settings.case_admin_roles):
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Case not found",
    )


@lru_cache
def get_object_storage() -> ObjectStorage:
    return create_object_storage()


ObjectStorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
