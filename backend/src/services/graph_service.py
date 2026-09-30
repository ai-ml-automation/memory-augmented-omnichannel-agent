"""
Graph Service
Integration with Neo4j for knowledge graph operations (async driver)
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
    Knowledge graph service using Neo4j.

    Manages relationships between facts and entities.
    Uses AsyncGraphDatabase to avoid blocking the FastAPI event loop.
    """

    def __init__(self):
        self._driver = None

    def _get_driver(self) -> Any:
        """Lazy initialization of async Neo4j driver."""
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
        Create a fact node in the graph.

        152-FZ: consent_verified must be True; otherwise operation is
        logged as a compliance violation and skipped.

        Args:
            fact_id: Fact identifier
            user_id: User identifier
            category: Fact category
            content_summary: Short content summary
            metadata: Optional metadata
            consent_verified: Caller must confirm consent was checked

        Returns:
            True if created successfully
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
        Create relationship between two nodes.

        152-FZ: consent_verified must be True.

        Args:
            from_id: Source node ID
            to_id: Target node ID
            relationship_type: Relationship type (must be in RelationshipType enum)
            properties: Optional properties
            consent_verified: Caller must confirm consent was checked

        Returns:
            True if created

        Raises:
            ValueError: If relationship_type is not in the whitelist
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
        Get user's fact graph.

        Args:
            user_id: User identifier
            depth: Traversal depth

        Returns:
            Graph data with nodes and relationships
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
        Find facts related to a given fact.

        Args:
            fact_id: Fact identifier
            relationship_type: Optional relationship type filter (must be in RelationshipType enum)
            limit: Maximum results

        Returns:
            Related facts

        Raises:
            ValueError: If relationship_type is not in the whitelist
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
        Delete fact node and its relationships.

        Args:
            fact_id: Fact identifier

        Returns:
            True if deleted
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
