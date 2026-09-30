"""
Right to be Forgotten Service
152-FZ compliance: cascade deletion of all user data

B.3.1: Deletes user data from all stores:
- PostgreSQL (facts, consents, sessions, channel_bindings, user)
- Qdrant (vector index)
- Neo4j (knowledge graph)
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.models import Fact, User

logger = logging.getLogger(__name__)


class RightToBeForgottenService:
    """
    Service for Right to be Forgotten (152-FZ).

    Cascade-deletes all user data from PostgreSQL, Qdrant, and Neo4j.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_user_data(
        self,
        user_id: uuid.UUID,
        source: str = "OPERATOR",
    ) -> dict[str, int | str]:
        """
        Delete all user data across all stores.

        This is the main entry point for Right to be Forgotten.
        Called when consent is revoked or user requests deletion.

        Args:
            user_id: User identifier
            source: Audit source (OPERATOR, AI, USER_REQUEST)

        Returns:
            Summary dict with deletion counts per store
        """
        summary: dict[str, int | str] = {
            "user_id": str(user_id),
            "postgres_facts_deleted": 0,
            "qdrant_facts_deleted": 0,
            "neo4j_facts_deleted": 0,
            "user_deleted": False,
        }

        # Step 1: Get all user facts
        result = await self.db.execute(
            select(Fact).where(Fact.user_id == user_id)
        )
        facts = list(result.scalars().all())
        fact_ids = [f.id for f in facts]

        logger.info(
            "RightToBeForgotten: deleting %d facts for user=%s",
            len(facts),
            user_id,
        )

        # Step 2: Delete from Qdrant (vector store)
        qdrant_deleted = await self._delete_from_qdrant(fact_ids)
        summary["qdrant_facts_deleted"] = qdrant_deleted

        # Step 3: Delete from Neo4j (knowledge graph)
        neo4j_deleted = await self._delete_from_neo4j(fact_ids, user_id)
        summary["neo4j_facts_deleted"] = neo4j_deleted

        # Step 4: Delete facts from PostgreSQL
        for fact in facts:
            await self.db.delete(fact)
        await self.db.flush()
        summary["postgres_facts_deleted"] = len(facts)

        # Step 5: Delete user record (cascade deletes consents,
        # sessions, channel_bindings, audit_logs)
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            await self.db.delete(user)
            await self.db.flush()
            summary["user_deleted"] = True
            logger.info("User %s deleted from PostgreSQL", user_id)

        logger.info(
            "RightToBeForgotten complete: user=%s summary=%s",
            user_id,
            summary,
        )

        return summary

    async def _delete_from_qdrant(self, fact_ids: list[uuid.UUID]) -> int:
        """
        Delete facts from Qdrant vector store.

        Returns:
            Number of facts deleted
        """
        if not fact_ids:
            return 0

        try:
            from backend.src.config import get_settings
            settings = get_settings()

            if not settings.ENABLE_MEMORY:
                logger.info("Qdrant disabled, skipping vector deletion")
                return 0

            from qdrant_client import QdrantClient

            client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )

            client.delete(
                collection_name="facts",
                points_selector=[str(fid) for fid in fact_ids],
            )

            logger.info(
                "Deleted %d facts from Qdrant",
                len(fact_ids),
            )
            return len(fact_ids)
        except ImportError:
            logger.warning("qdrant-client not installed, skipping")
            return 0
        except Exception as e:
            logger.error("Failed to delete from Qdrant: %s", e)
            return 0

    async def _delete_from_neo4j(
        self,
        fact_ids: list[uuid.UUID],
        user_id: uuid.UUID,
    ) -> int:
        """
        Delete facts and user node from Neo4j.

        Returns:
            Number of fact nodes deleted
        """
        if not fact_ids:
            return 0

        try:
            from backend.src.config import get_settings
            settings = get_settings()

            if not settings.ENABLE_MEMORY:
                logger.info("Neo4j disabled, skipping graph deletion")
                return 0

            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )

            with driver.session() as session:
                # Delete all fact nodes belonging to user
                session.run(
                    """
                    MATCH (u:User {id: $user_id})-[:HAS_FACT]->(f:Fact)
                    DETACH DELETE f
                    """,
                    user_id=str(user_id),
                )

                # Delete user node
                session.run(
                    """
                    MATCH (u:User {id: $user_id})
                    DETACH DELETE u
                    """,
                    user_id=str(user_id),
                )

            driver.close()

            logger.info(
                "Deleted user %s and %d fact nodes from Neo4j",
                user_id,
                len(fact_ids),
            )
            return len(fact_ids)
        except ImportError:
            logger.warning("neo4j not installed, skipping")
            return 0
        except Exception as e:
            logger.error("Failed to delete from Neo4j: %s", e)
            return 0
