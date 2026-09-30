"""
Белый список типов связей графа знаний Neo4j.

Почему whitelist, а не свободная строка: тип связи подставляется в Cypher-запрос
напрямую (см. GraphService), поэтому любое непроверенное значение открывает
вектор Cypher Injection. Ограничение набора допустимых типов гарантирует,
что в запрос попадает только значение из Enum, а не произвольный ввод.

Связанные компоненты: GraphService, RelationshipType.is_valid.
"""

from enum import Enum


class RelationshipType(str, Enum):
    """
    Допустимые типы связей в графе знаний.

    Наследование от str + Enum даёт два эффекта: значения остаются обычными
    строками (совместимы с API и хранением в Neo4j), а проверка принадлежности
    к Enum исключает произвольные типы из Cypher-запросов — это первая линия
    защиты от Cypher Injection до подстановки в запрос (I.1.1).

    Жизненный цикл: перечисление расширяется только вместе с бизнес-правилами
    графа; добавление типа требует явного решения, потому что меняет семантику
    существующих данных.

    @see GraphService.create_relationship
    """

    HAS_FACT = "HAS_FACT"
    RELATED_TO = "RELATED_TO"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    SUPERSEDES = "SUPERSEDES"

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Проверка, является ли строка допустимым типом связи.

        Используется перед подстановкой значения в Cypher-запрос: вызов
        RelationshipType(value) бросил бы ValueError, но проверка по словарю
        _value2member_map_ позволяет вернуть False без исключения там,
        где удобнее обработать ошибку на стороне вызова.

        Args:
            value: проверяемая строка типа связи

        Returns:
            True, если value входит в RelationshipType
        """
        return value in cls._value2member_map_
