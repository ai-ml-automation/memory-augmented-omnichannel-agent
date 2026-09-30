"""
Unit Tests for FactService
Проверяют CRUD фактов: шифрование значения (AES-256-GCM), проверку согласия
(consent), суперседию устаревших фактов, поиск по расшифрованным значениям
и статистику по типам.

Зачем эти тесты: факты — личные данные пользователя. Значение шифруется
в БД, поэтому тесты ловят утечки открытого текста, сохранение без согласия,
попадание устаревших фактов в активные выборки и сломанную расшифровку
при чтении (Phase B).
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Consent, User
from backend.src.services.fact_service import FactService, VALID_FACT_TYPES


async def _create_test_user(db: AsyncSession) -> User:
    """Helper: создать тестового пользователя без обращения к AuthService.

    Args:
        db: активная тестовая сессия, в которую сохраняется пользователь.

    Returns:
        User: созданный пользователь с фейковыми хэшами телефона и пароля
        (флашед, но не закоммиченный — транзакция откатится после теста).
    """
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
    """Helper: выдать активное согласие на обработку фактов.

    Args:
        db: активная тестовая сессия, в которую сохраняется согласие.
        user: пользователь, которому выдаётся согласие.

    Returns:
        Consent: согласие на канал "TG", выданное 01.01.2025.
    """
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
    """Ловит баг, если store_fact не сохраняет валидный факт целиком.

    После сохранения: id не пустой, value возвращается расшифрованным,
    тип/вес/канал сохранены, is_superseded=False, проставлены created_at
    и expires_at. Пропуск любого из этих полей сломает чтение факта.
    """
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
    """Ловит критический баг хранения открытого текста в БД.

    Читает value сырым SQL в обход identity map и проверяет, что в БД
    лежит НЕ исходный текст, а возвращаемый сервисом факт — расшифрован.
    Если сервис писал plaintext, утечка БД раскрыла бы личные данные.
    """
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
    """Ловит баг, если факт сохраняется без согласия пользователя.

    Без выданного consent store_fact обязан бросить PermissionError
    с "consent". Сохранение без согласия нарушает правила обработки
    персональных данных — это защитная проверка Phase B.
    """
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
    """Ловит баг, если принимается неизвестный тип факта.

    store_fact обязан бросить ValueError "Invalid fact type". Пропуск
    валидации засорит БД типами, которые не обработают ни выборки,
    ни статистика, ни рекомендации.
    """
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
    """Ловит баг, если хотя бы один валидный тип факта не сохраняется.

    Перебирает весь список VALID_FACT_TYPES и проверяет, что тип
    возвращённого факта совпадает с запрошенным. Пропуск типа здесь —
    признак рассинхронизации валидации и модели хранения.
    """
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
    """Ловит баг, если get_facts не возвращает все факты пользователя.

    Хранит 3 факта разных типов и каналов, затем проверяет, что чтение
    отдаёт все три значения расшифрованными. Пропущенный факт или
    зашифрованный текст в ответе — регрессия чтения.
    """
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
    """Ловит баг, если фильтр fact_type игнорируется при чтении.

    При 2 фактах "intent" и 1 "preference" запрос с fact_type="intent"
    обязан вернуть ровно 2 факта, все типа intent. Игнорирование фильтра
    вернёт лишние факты в карточку клиента.
    """
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
    """Ловит баг, если чтение одиночного факта не расшифровывает value.

    Сохраняет факт с кириллическим адресом и читает его по id: значение
    должно вернуться как plaintext. Сломанная расшифровка при чтении
    проявится именно здесь — в полном round-trip шифрования.
    """
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
    """Ловит баг, если get_fact для отсутствующего id бросает исключение.

    Для случайного uuid сервис обязан вернуть None — отсутствие факта
    это штатная ситуация, а не ошибка. Исключение здесь сломало бы
    обработку «факт не найден» на уровне API.
    """
    service = FactService(db_session)
    result = await service.get_fact(uuid.uuid4())
    assert result is None


# ------------------------------------------------------------------
# supersede / delete
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supersede_fact(db_session: AsyncSession):
    """Ловит баг, если суперседия не помечает факт устаревшим.

    После supersede_fact факт обязан получить is_superseded=True и вес 0.1.
    Устаревший факт не должен влиять на рекомендации с прежним весом —
    иначе клиенту будут предлагать отменённые предпочтения.
    """
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
    """Ловит баг, если hard-delete не удаляет факт из БД.

    После delete_fact чтение по id должно вернуть None. Это основа права
    на забвение (right to be forgotten): если запись переживёт удаление,
    удалить персональные данные пользователя станет невозможно.
    """
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
    """Ловит баг, если поиск по подстроке пропускает факты.

    Поиск идёт по расшифрованным значениям в памяти: запрос "laptop"
    обязан найти оба факта, содержащих это слово. Пропуск факта означает,
    что оператор не увидит релевантную информацию о клиенте.
    """
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
    """Ловит баг, если поиск фактов регистрозависим.

    Значение "LOVES COFFEE" должно находиться по запросу "coffee" —
    пользователь не помнит, в каком регистре сохранён факт. Регистроза-
    висимый поиск молча теряет результаты для операторов.
    """
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
    """Ловит баг, если статистика по типам фактов неверна.

    После сохранения 2 "intent" и 1 "preference" статистика обязана быть
    total=3, intent=2, preference=1, complaint=0. Сломанный счётчик
    исказит сводку по клиенту на дашборде оператора.
    """
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
    """Ловит баг, если устаревшие факты попадают в активные выборки.

    active_only=True обязан вернуть только 1 активный факт из двух,
    active_only=False — оба. Суперседия помечает, а не удаляет: история
    должна оставаться доступной, но не влиять на активные данные.
    """
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
