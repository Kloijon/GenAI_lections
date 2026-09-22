import time
import tempfile
from pathlib import Path
from threading import Thread

import pytest

from llm_agent.core_v2 import LLMAgent
from llm_agent.tool_directorywatcher import DirectoryWatcherTool

# =====================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================

MODEL_NAME = "qwen2.5:0.5b"


def _collect_report(path: str, duration: int) -> str:
    """Запускает DirectoryWatcherTool напрямую и возвращает отчёт."""
    tool = DirectoryWatcherTool()
    return tool.use(path=path, duration=duration, details=False)


def _ask_llm(agent: LLMAgent, prompt: str, max_retries: int = 3) -> str:
    """Спрашивает LLM с retry на случай пустого content."""
    for attempt in range(max_retries):
        payload = {
            "model": agent.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "temperature": 0.0,
            "max_tokens": 16,
        }
        response_data = agent._make_api_request(payload)
        message = response_data["choices"][0]["message"]
        content = (message.get("content") or "").strip()
        if content:
            return content
        print(f"[warn] Пустой ответ, повтор {attempt + 1}/{max_retries}")
    return ""


def _is_yes(response: str) -> bool:
    """Проверяет, что LLM ответила строго ДА (без 'уДАлось' и подобного)."""
    normalized = response.strip().upper().replace("Ё", "Е")
    return normalized == "ДА" or normalized.startswith("ДА ") or normalized.startswith("ДА,")


def _is_no(response: str) -> bool:
    """Проверяет, что LLM ответила строго НЕТ."""
    normalized = response.strip().upper().replace("Ё", "Е")
    return normalized == "НЕТ" or normalized.startswith("НЕТ ") or normalized.startswith("НЕТ,")


# =====================================================================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ (Запускают реальную Ollama)
# =====================================================================
# Маркируем как 'integration', чтобы их можно было отключать при быстрой проверке

@pytest.mark.integration
def test_directory_watcher_file_creation_llm():
    """LLM проверяет, что отчёт корректно описывает создание файла."""
    with tempfile.TemporaryDirectory() as tmp:
        results = {}

        def worker():
            results["report"] = _collect_report(tmp, 2)

        thread = Thread(target=worker)
        thread.start()
        time.sleep(0.5)

        (Path(tmp) / "hello.txt").write_text("data")
        thread.join(timeout=5)

        report = results["report"]

        agent = LLMAgent(local=True, ollama_model=MODEL_NAME)
        query = (
            "Ниже отчёт инструмента отслеживания файловой системы. "
            'В процессе работы был создан файл "hello.txt".\n\n'
            f"Отчёт:\n{report}\n\n"
            "Вопрос: содержит ли отчёт признак того, что файл hello.txt был создан? "
            "Ответь строго одним словом на русском: ДА или НЕТ."
        )

        response = _ask_llm(agent, query)
        assert _is_yes(response), f"Ожидали ДА, получили: {response!r}"


@pytest.mark.integration
def test_directory_watcher_modification_llm():
    """LLM проверяет, что отчёт корректно описывает изменение файла."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "doc.txt"
        target.write_text("initial")

        results = {}

        def worker():
            results["report"] = _collect_report(tmp, 2)

        thread = Thread(target=worker)
        thread.start()
        time.sleep(0.5)

        target.write_text("changed content")
        thread.join(timeout=5)

        report = results["report"]

        agent = LLMAgent(local=True, ollama_model=MODEL_NAME)
        query = (
            "Ниже отчёт инструмента отслеживания файловой системы. "
            'Файл "doc.txt" был изменён.\n\n'
            f"Отчёт:\n{report}\n\n"
            "Вопрос: зафиксировано ли в отчёте событие изменения? "
            "Ответь строго одним словом на русском: ДА или НЕТ."
        )

        response = _ask_llm(agent, query)
        assert _is_yes(response), f"Ожидали ДА, получили: {response!r}"


@pytest.mark.integration
def test_directory_watcher_moved_file_llm():
    """LLM проверяет, что отчёт фиксирует перемещение файла."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "old.txt"
        dst = Path(tmp) / "new.txt"
        src.write_text("content")

        results = {}

        def worker():
            results["report"] = _collect_report(tmp, 2)

        thread = Thread(target=worker)
        thread.start()
        time.sleep(0.5)

        src.rename(dst)
        thread.join(timeout=5)

        report = results["report"]

        agent = LLMAgent(local=True, ollama_model=MODEL_NAME)
        query = (
            "Ниже отчёт инструмента отслеживания файловой системы. "
            'Файл "old.txt" был переименован в "new.txt".\n\n'
            f"Отчёт:\n{report}\n\n"
            "Вопрос: зафиксировано ли в отчёте событие перемещения "
            "или переименования? Ответь строго одним словом на русском: ДА или НЕТ."
        )

        response = _ask_llm(agent, query)
        assert _is_yes(response), f"Ожидали ДА, получили: {response!r}"