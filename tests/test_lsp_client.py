from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from clangd_probe.lsp_client import LspClient, symbol_item


def fake_server_command():
    here = Path(__file__).resolve().parent / "fakes" / "fake_clangd_server.py"
    return [sys.executable, str(here)]


def test_initialize_and_open_document(tmp_path):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")

    with LspClient(fake_server_command()) as client:
        caps = client.initialize(tmp_path, initial_file=source)
        assert caps["definitionProvider"] is True
        assert source.as_uri() in client.open_documents


def test_definition_request(tmp_path):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        client.open_document(source)
        result = client.definition(source, 3, 5)

    assert result[0]["path"] == str(source.resolve())
    assert result[0]["line"] == 10
    assert result[0]["column"] == 3


def test_references_request(tmp_path):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        client.open_document(source)
        result = client.references(source, 3, 5)

    assert len(result) == 2
    assert result[0]["line"] == 13


def test_references_open_unopened_document_when_server_requires_it(tmp_path, monkeypatch):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_CLANGD_REQUIRE_OPEN_FOR_POSITIONS", "1")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        result = client.references(source, 3, 5)

    assert len(result) == 2
    assert source.as_uri() in client.open_documents


def test_hover_request(tmp_path):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        client.open_document(source)
        result = client.hover(source, 1, 1)

    assert "int demo()" in result["value"]


def test_hover_open_unopened_document_when_server_requires_it(tmp_path, monkeypatch):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_CLANGD_REQUIRE_OPEN_FOR_POSITIONS", "1")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        result = client.hover(source, 1, 1)

    assert "int demo()" in result["value"]
    assert source.as_uri() in client.open_documents


def test_hover_request_with_null_result_returns_none(tmp_path, monkeypatch):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_CLANGD_NULL_HOVER", "1")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        client.open_document(source)
        result = client.hover(source, 1, 1)

    assert result is None


def test_document_symbols_request(tmp_path):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        client.open_document(source)
        result = client.document_symbols(source)

    assert result[0]["name"] == "Demo"
    assert result[0]["path"] == str(source.resolve())


def test_document_symbols_open_unopened_document_when_server_requires_it(tmp_path, monkeypatch):
    source = tmp_path / "demo.cpp"
    source.write_text("int demo() { return 0; }\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_CLANGD_REQUIRE_OPEN_FOR_SYMBOLS", "1")

    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        result = client.document_symbols(source)

    assert result[0]["name"] == "Demo"
    assert source.as_uri() in client.open_documents


def test_workspace_symbols_request(tmp_path):
    with LspClient(fake_server_command()) as client:
        client.initialize(tmp_path)
        result = client.workspace_symbols("Demo::solve")

    assert result[0]["name"] == "Demo::solve"
    assert result[0]["path"] == "/tmp/demo.cpp"


def test_close_survives_wait_timeout(monkeypatch):
    client = LspClient(["fake-clangd"])

    class SlowProcess:
        def terminate(self):
            return None

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(["fake-clangd"], timeout)

        def kill(self):
            return None

    client.process = SlowProcess()
    monkeypatch.setattr(client, "request", lambda method, params: None)
    monkeypatch.setattr(client, "notify", lambda method, params: None)

    client.close()


def test_symbol_item_combines_container_and_name_for_workspace_results():
    item = {
        "name": "next",
        "kind": 12,
        "containerName": "SPARTA_NS::Variable",
        "location": {
            "uri": "file:///tmp/variable.cpp",
            "range": {
                "start": {"line": 10, "character": 4},
                "end": {"line": 10, "character": 8},
            },
        },
    }

    row = symbol_item(item)

    assert row["qualified_name"] == "SPARTA_NS::Variable::next"
