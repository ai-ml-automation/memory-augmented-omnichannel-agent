"""
Graph Relationships
Whitelist of allowed Neo4j relationship types (prevents Cypher Injection)
"""

from enum import Enum


class RelationshipType(str, Enum):
    """Allowed relationship types in the knowledge graph.

    Using an Enum prevents Cypher Injection by validating
    the relationship type before it is interpolated into queries.
    """

    HAS_FACT = "HAS_FACT"
    RELATED_TO = "RELATED_TO"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    SUPERSEDES = "SUPERSEDES"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid relationship type."""
        return value in cls._value2member_map_
