"""
Consents Router
Endpoints for consent management (152-FZ)

B.3.2: Added data deletion endpoint (Right to be Forgotten)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.schemas import ConsentGrant, ConsentResponse, UserResponse
from backend.src.services.auth_service import AuthService
from backend.src.services.consent_service import ConsentService
from backend.src.services.right_to_be_forgotten_service import (
    RightToBeForgottenService,
)

router = APIRouter(prefix="/consents", tags=["consents"])


async def get_current_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Dependency to get current user from cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(token)
        return UserResponse(
            id=user.id,
            phone_hash=user.phone_hash,
            created_at=user.created_at,
            is_active=user.is_active,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


class DataDeletionResponse(BaseModel):
    """Response for data deletion request."""
    status: str
    postgres_facts_deleted: int
    qdrant_facts_deleted: int
    neo4j_facts_deleted: int
    user_deleted: bool


@router.post("/grant", response_model=ConsentResponse, status_code=201)
async def grant_consent(
    consent_data: ConsentGrant,
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    """
    Grant consent for data processing.

    Requires authentication.

    Args:
        consent_data: Consent data (channel, ip_address)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Consent status after grant
    """
    service = ConsentService(db)
    try:
        await service.grant_consent(
            user_id=current_user.id,
            channel=consent_data.channel,
            ip_address=consent_data.ip_address,
        )
        status = await service.get_consent_status(current_user.id)
        return ConsentResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/revoke", response_model=ConsentResponse)
async def revoke_consent(
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    """
    Revoke user consent and trigger Right to be Forgotten.

    B.3.2: Revoking consent now cascade-deletes all user data
    from PostgreSQL, Qdrant, and Neo4j.

    Requires authentication.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Consent status after revoke
    """
    service = ConsentService(db)
    try:
        await service.revoke_consent(
            user_id=current_user.id,
            source="USER_REQUEST",
        )
        status = await service.get_consent_status(current_user.id)
        return ConsentResponse(**status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status", response_model=ConsentResponse)
async def get_consent_status(
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> ConsentResponse:
    """
    Get current consent status.

    Requires authentication.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Current consent status
    """
    service = ConsentService(db)
    status = await service.get_consent_status(current_user.id)
    return ConsentResponse(**status)


@router.post(
    "/data-deletion",
    response_model=DataDeletionResponse,
)
async def request_data_deletion(
    current_user: UserResponse = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db),
) -> DataDeletionResponse:
    """
    Request Right to be Forgotten (152-FZ).

    B.3.2: Dedicated endpoint for user-initiated data deletion.
    Deletes all user data from PostgreSQL, Qdrant, and Neo4j.

    This is the explicit "right to erasure" endpoint.
    Consent revocation (/consents/revoke) also triggers this
    automatically.

    Requires authentication.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Deletion summary with counts per store
    """
    rtbf = RightToBeForgottenService(db)
    try:
        summary = await rtbf.delete_user_data(
            user_id=current_user.id,
            source="USER_REQUEST",
        )
        return DataDeletionResponse(
            status="deleted",
            postgres_facts_deleted=summary["postgres_facts_deleted"],
            qdrant_facts_deleted=summary["qdrant_facts_deleted"],
            neo4j_facts_deleted=summary["neo4j_facts_deleted"],
            user_deleted=summary["user_deleted"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data deletion failed: {e}",
        )
