"""
Unit Tests for FactService
Tests fact CRUD with encryption and consent checks (Phase B).
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Consent, User
from backend.src.services.fact_service import FactService, VALID_FACT_TYPES


async def _create_test_user(db: AsyncSession) -> User:
    """Helper: create a test user."""
    user = User(
        id=uuid.uuid4(),
        phone_hash="test_hash",
        password_hash="test_pw_hash",
        is_active=True,
        tenant_id="default",
    )
    db.add(user)
    await db.flush()
    return user


async def _grant_consent(db: AsyncSession, user: User) -> Consent:
    """Helper: grant active consent for test user."""
    consent = Consent(
        id=uuid.uuid4(),
        user_id=user.id,
        granted_at=datetime(2025, 1, 1),
        channel="TG",
    )
    db.add(consent)
    await db.flush()
    return consent


# ------------------------------------------------------------------
# store_fact (with encryption + consent)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_store_fact_success(db_session: AsyncSession):
    """Test storing a valid fact (encrypted, consent verified)."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    fact = await service.store_fact(
        user_id=user.id,
        fact_type="preference",
        value="User prefers dark mode",
        channel="TG",
        weight=0.9,
    )

    assert fact is not None
    assert fact.id is not None
    assert fact.type == "preference"
    # Value is decrypted on return
    assert fact.value == "User prefers dark mode"
    assert fact.weight == 0.9
    assert fact.channel == "TG"
    assert fact.is_superseded is False
    assert fact.created_at is not None
    assert fact.expires_at is not None


@pytest.mark.asyncio
async def test_store_fact_value_encrypted_in_db(db_session: AsyncSession):
    """Test that value is actually encrypted in the database."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    plain = "My secret passport is 4515 123456"
    fact = await service.store_fact(
        user_id=user.id,
        fact_type="personal_info",
        value=plain,
        channel="TG",
    )

    # Read raw value from DB using raw SQL (bypass identity map)
    from sqlalchemy import text

    fact_id = str(fact.id)
    result = await db_session.execute(
        text("SELECT value FROM facts WHERE id = :fid"),
        {"fid": fact_id},
    )
    row = result.fetchone()
    raw_value = row[0] if row else None

    # Raw value in DB should NOT be plaintext
    assert raw_value != plain
    # But returned fact should be decrypted
    assert fact.value == plain


@pytest.mark.asyncio
async def test_store_fact_no_consent_raises(db_session: AsyncSession):
    """Test that store_fact without consent raises PermissionError."""
    user = await _create_test_user(db_session)
    # No consent granted
    service = FactService(db_session)

    with pytest.raises(PermissionError, match="consent"):
        await service.store_fact(
            user_id=user.id,
            fact_type="preference",
            value="Test",
            channel="TG",
        )


@pytest.mark.asyncio
async def test_store_fact_invalid_type_raises(db_session: AsyncSession):
    """Test that invalid fact type raises ValueError."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    with pytest.raises(ValueError, match="Invalid fact type"):
        await service.store_fact(
            user_id=user.id,
            fact_type="invalid_type",
            value="Some value",
            channel="TG",
        )


@pytest.mark.asyncio
async def test_store_fact_all_valid_types(db_session: AsyncSession):
    """Test that all valid fact types can be stored."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    for fact_type in VALID_FACT_TYPES:
        fact = await service.store_fact(
            user_id=user.id,
            fact_type=fact_type,
            value=f"Test {fact_type}",
            channel="TG",
        )
        assert fact.type == fact_type


# ------------------------------------------------------------------
# get_facts / get_fact (decryption)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_facts(db_session: AsyncSession):
    """Test retrieving facts for a user (decrypted)."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    await service.store_fact(user.id, "intent", "Buy laptop", "TG")
    await service.store_fact(user.id, "preference", "Likes dark mode", "VK")
    await service.store_fact(user.id, "complaint", "Slow delivery", "MAX")

    facts = await service.get_facts(user.id)

    assert len(facts) == 3
    # All values should be decrypted
    values = {f.value for f in facts}
    assert "Buy laptop" in values
    assert "Likes dark mode" in values
    assert "Slow delivery" in values


@pytest.mark.asyncio
async def test_get_facts_by_type(db_session: AsyncSession):
    """Test filtering facts by type."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    await service.store_fact(user.id, "intent", "Buy laptop", "TG")
    await service.store_fact(user.id, "intent", "Buy phone", "VK")
    await service.store_fact(user.id, "preference", "Dark mode", "TG")

    intents = await service.get_facts(user.id, fact_type="intent")

    assert len(intents) == 2
    assert all(f.type == "intent" for f in intents)


@pytest.mark.asyncio
async def test_get_fact_by_id(db_session: AsyncSession):
    """Test getting a single fact by ID (decrypted)."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    fact = await service.store_fact(
        user.id, "personal_info", "Address: ул. Пушкина д.10", "TG"
    )
    retrieved = await service.get_fact(fact.id)

    assert retrieved is not None
    assert retrieved.value == "Address: ул. Пушкина д.10"


@pytest.mark.asyncio
async def test_get_fact_nonexistent_returns_none(db_session: AsyncSession):
    """Test that get_fact returns None for non-existent ID."""
    service = FactService(db_session)
    result = await service.get_fact(uuid.uuid4())
    assert result is None


# ------------------------------------------------------------------
# supersede / delete
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supersede_fact(db_session: AsyncSession):
    """Test superseding a fact."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    fact = await service.store_fact(user.id, "preference", "Old preference", "TG")
    result = await service.supersede_fact(fact.id)

    assert result is True

    updated_fact = await service.get_fact(fact.id)
    assert updated_fact.is_superseded is True
    assert updated_fact.weight == 0.1


@pytest.mark.asyncio
async def test_delete_fact(db_session: AsyncSession):
    """Test hard-deleting a fact."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    fact = await service.store_fact(user.id, "intent", "Buy laptop", "TG")
    result = await service.delete_fact(fact.id)

    assert result is True

    deleted = await service.get_fact(fact.id)
    assert deleted is None


# ------------------------------------------------------------------
# search_facts (in-memory on decrypted values)
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_facts(db_session: AsyncSession):
    """Test searching facts by decrypted value text."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    await service.store_fact(user.id, "intent", "Buy laptop", "TG")
    await service.store_fact(user.id, "preference", "Likes dark mode", "VK")
    await service.store_fact(user.id, "complaint", "Laptop is slow", "MAX")

    results = await service.search_facts(user.id, "laptop")

    assert len(results) == 2
    # Both should have decrypted values containing "laptop"
    for fact in results:
        assert "laptop" in fact.value.lower()


@pytest.mark.asyncio
async def test_search_facts_case_insensitive(db_session: AsyncSession):
    """Test search is case-insensitive."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    await service.store_fact(user.id, "preference", "LOVES COFFEE", "TG")

    results = await service.search_facts(user.id, "coffee")
    assert len(results) == 1
    assert results[0].value == "LOVES COFFEE"


# ------------------------------------------------------------------
# stats
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_user_stats(db_session: AsyncSession):
    """Test user statistics."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    await service.store_fact(user.id, "intent", "Buy laptop", "TG")
    await service.store_fact(user.id, "intent", "Buy phone", "VK")
    await service.store_fact(user.id, "preference", "Dark mode", "TG")

    stats = await service.get_user_stats(user.id)

    assert stats["total"] == 3
    assert stats["intent"] == 2
    assert stats["preference"] == 1
    assert stats["complaint"] == 0


@pytest.mark.asyncio
async def test_get_facts_excludes_superseded(db_session: AsyncSession):
    """Test that get_facts excludes superseded facts by default."""
    user = await _create_test_user(db_session)
    await _grant_consent(db_session, user)
    service = FactService(db_session)

    fact1 = await service.store_fact(user.id, "intent", "Buy laptop", "TG")
    await service.store_fact(user.id, "preference", "Dark mode", "VK")

    await service.supersede_fact(fact1.id)

    active_facts = await service.get_facts(user.id, active_only=True)
    assert len(active_facts) == 1
    assert active_facts[0].type == "preference"

    all_facts = await service.get_facts(user.id, active_only=False)
    assert len(all_facts) == 2
