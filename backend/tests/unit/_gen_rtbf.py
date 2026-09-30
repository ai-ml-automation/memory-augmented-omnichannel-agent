"""
Служебный генератор данных для RTBF-тестов.

Почему отдельный файл: сценарии «право на забвение» требуют больших наборов
фактов/аудита с предсказуемыми id — генератор подготавливает их вне тестовых
функций, чтобы тесты оставались читаемыми и не дублировали данные.
"""
import pathlib
target = pathlib.Path(r'D:\__tasks3\memory-augmented-omnichannel-agent-local\backend\tests\unit\test_right_to_be_forgotten.py')
L = []
