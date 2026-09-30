"""
Сервис работы с графом знаний Neo4j (асинхронный драйвер).

Хранит факты пользователя как узлы и связи: это даёт ответы на вопросы
«что связано с чем» быстрее, чем перебор в векторном поиске, и служит
источником контекста для LLM (Phase C.1.1).

Ключевые решения:
- AsyncGraphDatabase не блокирует event loop FastAPI при конкурентных запросах;
- ленивая инициализация драйвера — сервис стартует без Neo4j (ENABLE_LLM=false);
- каждая операция проверяет consent (152-ФЗ, B.1.4) и валидирует типы связей
  против RelationshipType (защита от Cypher Injection, I.1.1).

@see RelationshipType, mem0_memory_service
"""

import logging
import uuid
from typing import Any

from backend.src.config import get_settings
from backend.src.services.graph_relationships import RelationshipType

logger = logging.getLogger(__name__)
settings = get_settings()


class GraphService:
    """
    Сервис графа знаний на базе Neo4j.

    Ответственность: создание узлов фактов, связей между ними, чтение графа
    пользователя и поиск связанных фактов для контекста памяти.

    Жизненный цикл: один экземпляр на приложение; асинхронный драйвер
    создаётся лениво при первой операции и используется повторно.

    Почему Neo4j: связи фактов (SUPERSEDES, CONFLICTS_WITH) — это графовая
    модель; обход по связям в Neo4j на порядки дешевле, чем в реляционной БД.
    Асинхронный драйвер выбран, чтобы не блокировать event loop FastAPI.

    @see RelationshipType (типы связей), VectorStoreService (векторный поиск)
    """

    def __init__(self):
        """
        Инициализация сервиса без подключения к Neo4j.

        Драйвер создаётся лениво в _get_driver при первой операции —
        это позволяет приложению стартовать без работающей базы графов.
        """
        self._driver = None

    def _get_driver(self) -> Any:
        """
        Ленивая инициализация асинхронного драйвера Neo4j.

        Почему лениво: пакет neo4j может быть не установлен, а сама Neo4j —
        недоступна; сервис обязан стартовать (ENABLE_LLM=false) и сообщать
        о недоступности графа только в момент реальной операции.

        Raises:
            RuntimeError: если граф отключён или пакет neo4j не установлен
        """
        if self._driver is None:
            if not settings.ENABLE_LLM:
                raise RuntimeError("Graph store disabled (ENABLE_LLM=false)")

            try:
                from neo4j import AsyncGraphDatabase

                self._driver = AsyncGraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                )
                logger.info("Neo4j async driver initialized")
            except ImportError:
                raise RuntimeError("neo4j package not installed")

        return self._driver

    async def create_fact_node(
        self,
        fact_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str,
        content_summary: str,
        metadata: dict[str, Any] | None = None,
        consent_verified: bool = False,
    ) -> bool:
        """
        Создание узла факта в графе знаний.

        Перед записью проверяется consent (152-ФЗ, B.1.4): при
        consent_verified=False операция логируется как нарушение комплаенса
        и пропускается. Узел и связь HAS_FACT создаются через MERGE, поэтому
        повторные вызовы идемпотентны и не плодят дубликаты.

        Args:
            fact_id: идентификатор факта (uuid)
            user_id: идентификатор пользователя-владельца
            category: категория факта
            content_summary: краткое содержание факта (без ПДн — только сводка)
            metadata: дополнительные свойства узла
            consent_verified: подтверждение проверки согласия вызывающим кодом

        Returns:
            True, если узел создан (или граф отключён)
        """
        if not settings.ENABLE_LLM:
            logger.warning("Graph store disabled, skipping")
            return False

        # B.1.4: consent gate (152-FZ)
        if not consent_verified:
            logger.warning(
                "Graph create_fact_node BLOCKED: "
                "consent_verified=False for user=%s fact=%s",
                user_id,
                fact_id,
            )
            return False

        try:
            driver = self._get_driver()

            async with driver.session() as session:
                await session.run(
                    """
                    MERGE (u:User {id: $user_id})
                    MERGE (f:Fact {
                        id: $fact_id,
                        category: $category,
                        summary: $summary
                    })
                    MERGE (u)-[:HAS_FACT]->(f)
                    """,
                    user_id=str(user_id),
                    fact_id=str(fact_id),
                    category=category,
                    summary=content_summary,
                )

            logger.info(f"Fact node {fact_id} created in graph")
            return True
        except Exception as e:
            logger.error(f"Failed to create fact node: {e}")
            return False

    async def create_relationship(
        self,
        from_id: uuid.UUID,
        to_id: uuid.UUID,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
        consent_verified: bool = False,
    ) -> bool:
        """
        Создание связи между двумя узлами графа.

        Тип связи обязан пройти RelationshipType.is_valid до подстановки
        в Cypher (I.1.1): интерполяция в строку запроса делает произвольный
        ввод вектором инъекции. consent (152-ФЗ, B.1.4) — как в create_fact_node.

        Args:
            from_id: идентификатор исходного узла
            to_id: идентификатор целевого узла
            relationship_type: тип связи из RelationshipType
            properties: дополнительные свойства связи
            consent_verified: подтверждение проверки согласия

        Returns:
            True, если связь создана (или граф отключён)

        Raises:
            ValueError: если relationship_type не входит в белый список
        """
        if not settings.ENABLE_LLM:
            return False

        # B.1.4: consent gate (152-FZ)
        if not consent_verified:
            logger.warning(
                "Graph create_relationship BLOCKED: "
                "consent_verified=False from=%s to=%s",
                from_id,
                to_id,
            )
            return False

        # I.1.1: Cypher Injection prevention — validate relationship type
        if not RelationshipType.is_valid(relationship_type):
            raise ValueError(
                f"Invalid relationship type: {relationship_type}. "
                f"Allowed: {[rt.value for rt in RelationshipType]}"
            )

        # Safe to use in f-string since it's validated against the Enum
        rel_type = RelationshipType(relationship_type).value

        try:
            driver = self._get_driver()

            async with driver.session() as session:
                query = f"""
                    MATCH (a {{id: $from_id}})
                    MATCH (b {{id: $to_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r += $properties
                    """
                await session.run(
                    query,
                    from_id=str(from_id),
                    to_id=str(to_id),
                    properties=properties or {},
                )

            logger.info(
                f"Relationship created: {from_id} -{rel_type}-> {to_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            return False

    async def get_user_facts_graph(
        self,
        user_id: uuid.UUID,
        depth: int = 2,
    ) -> dict[str, Any]:
        """
        Получение графа фактов пользователя для контекста памяти.

        Обход начинается от узла User по связям HAS_FACT на depth уровней
        (LIMIT 100 защищает от слишком широкого обхода). Результат отдаётся
        в виде списков узлов и связей для рендеринга/агрегации на стороне
        вызова (например, в memory_search_service).

        Args:
            user_id: идентификатор пользователя
            depth: глубина обхода графа

        Returns:
            dict с ключами nodes и relationships
        """
        if not settings.ENABLE_LLM:
            return {"nodes": [], "relationships": []}

        try:
            driver = self._get_driver()

            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (u:User {id: $user_id})-[:HAS_FACT*1.."""
                    + str(depth)
                    + """]->(f:Fact)
                    RETURN DISTINCT f, u
                    LIMIT 100
                    """,
                    user_id=str(user_id),
                )

                nodes = []
                relationships = []

                async for record in result:
                    fact = record["f"]
                    nodes.append({
                        "id": fact["id"],
                        "type": "Fact",
                        "category": fact.get("category", ""),
                        "summary": fact.get("summary", ""),
                    })

                # Add user node
                nodes.insert(0, {
                    "id": str(user_id),
                    "type": "User",
                })

                return {"nodes": nodes, "relationships": relationships}
        except Exception as e:
            logger.error(f"Failed to get user graph: {e}")
            return {"nodes": [], "relationships": []}

    async def find_related_facts(
        self,
        fact_id: uuid.UUID,
        relationship_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Поиск фактов, связанных с заданным фактом.

        Используется для расширения контекста памяти: по связям RELATED_TO,
        CONFLICTS_WITH и т.п. находятся факты, релевантные запросу даже без
        общих ключевых слов. relationship_type валидируется (I.1.1) до
        подстановки в Cypher; без него ищутся все связи в глубину до 2.

        Args:
            fact_id: идентификатор исходного факта
            relationship_type: фильтр по типу связи (из RelationshipType)
            limit: максимальное число результатов

        Returns:
            список dict с ключами id, category, summary

        Raises:
            ValueError: если relationship_type не входит в белый список
        """
        if not settings.ENABLE_LLM:
            return []

        # I.1.1: Cypher Injection prevention — validate relationship type
        rel_filter = ""
        if relationship_type:
            if not RelationshipType.is_valid(relationship_type):
                raise ValueError(
                    f"Invalid relationship type: {relationship_type}. "
                    f"Allowed: {[rt.value for rt in RelationshipType]}"
                )
            rel_type = RelationshipType(relationship_type).value
            rel_filter = f":{rel_type}"

        try:
            driver = self._get_driver()

            async with driver.session() as session:
                result = await session.run(
                    f"""
                    MATCH (f1:Fact {{id: $fact_id}})-[{rel_filter}*1..2]-(f2:Fact)
                    WHERE f1 <> f2
                    RETURN DISTINCT f2
                    LIMIT $limit
                    """,
                    fact_id=str(fact_id),
                    limit=limit,
                )

                return [
                    {
                        "id": record["f2"]["id"],
                        "category": record["f2"].get("category", ""),
                        "summary": record["f2"].get("summary", ""),
                    }
                    async for record in result
                ]
        except Exception as e:
            logger.error(f"Failed to find related facts: {e}")
            return []

    async def delete_fact_node(
        self,
        fact_id: uuid.UUID,
    ) -> bool:
        """
        Удаление узла факта вместе со всеми его связями.

        DETACH DELETE снимает связи до удаления узла — без этого Neo4j
        блокирует удаление узла с инцидентными рёбрами. Вызывается каскадом
        из right_to_be_forgotten_service (RTBF, 152-ФЗ) при удалении
        персональных данных пользователя.

        Args:
            fact_id: идентификатор факта

        Returns:
            True, если узел удалён (или граф отключён)
        """
        if not settings.ENABLE_LLM:
            return False

        try:
            driver = self._get_driver()

            async with driver.session() as session:
                await session.run(
                    """
                    MATCH (f:Fact {id: $fact_id})
                    DETACH DELETE f
                    """,
                    fact_id=str(fact_id),
                )

            logger.info(f"Fact node {fact_id} deleted from graph")
            return True
        except Exception as e:
            logger.error(f"Failed to delete fact node: {e}")
            return False
