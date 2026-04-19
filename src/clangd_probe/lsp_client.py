from __future__ import annotations

import json
from pathlib import Path
import subprocess


class LspClient:
    def __init__(self, command):
        self.command = list(command)
        self.process = None
        self.next_id = 1
        self.open_documents = set()
        self.capabilities = {}

    @property
    def supports_workspace_symbols(self):
        return bool(self.capabilities.get("workspaceSymbolProvider"))

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def start(self):
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def close(self):
        if self.process is None:
            return
        process = self.process
        try:
            self.request("shutdown", {})
            self.notify("exit", {})
        except Exception:
            pass
        try:
            process.terminate()
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            try:
                process.wait(timeout=1)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self.process = None

    def initialize(self, project_root, initial_file=None):
        root = Path(project_root).resolve()
        result = self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": root.as_uri(),
                "capabilities": {},
            },
        )
        self.capabilities = result.get("capabilities", {})
        self.notify("initialized", {})
        if initial_file is not None:
            self.open_document(initial_file)
        return self.capabilities

    def open_document(self, path, text=None):
        path = Path(path).resolve()
        if text is None:
            text = path.read_text(encoding="utf-8")
        uri = path.as_uri()
        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id(path),
                    "version": 1,
                    "text": text,
                }
            },
        )
        self.open_documents.add(uri)

    def definition(self, path, line, column):
        return self._locations(
            "textDocument/definition",
            path,
            line,
            column,
        )

    def references(self, path, line, column):
        return self._locations(
            "textDocument/references",
            path,
            line,
            column,
            extra={"context": {"includeDeclaration": True}},
        )

    def hover(self, path, line, column):
        self._ensure_document_open(path)
        result = self.request(
            "textDocument/hover",
            text_document_position(path, line, column),
        )
        if result is None:
            return None
        contents = result.get("contents", {})
        if isinstance(contents, dict):
            return {"kind": contents.get("kind"), "value": contents.get("value", "")}
        return {"kind": "plaintext", "value": str(contents)}

    def document_symbols(self, path):
        uri = self._ensure_document_open(path)
        result = self.request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": uri}},
        )
        return [symbol_item(item) for item in result or []]

    def workspace_symbols(self, query):
        result = self.request("workspace/symbol", {"query": query})
        return [symbol_item(item) for item in result or []]

    def request(self, method, params):
        msg_id = self.next_id
        self.next_id += 1
        self._write({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params})
        while True:
            message = self._read()
            if message is None:
                raise RuntimeError("LSP server closed unexpectedly")
            if message.get("id") != msg_id:
                continue
            if "error" in message:
                raise RuntimeError(message["error"]["message"])
            return message.get("result")

    def notify(self, method, params):
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, payload):
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self.process.stdin.write(header)
        self.process.stdin.write(body)
        self.process.stdin.flush()

    def _read(self):
        headers = {}
        while True:
            line = self.process.stdout.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            key, value = line.decode("utf-8").split(":", 1)
            headers[key.strip().lower()] = value.strip()
        length = int(headers["content-length"])
        payload = self.process.stdout.read(length)
        return json.loads(payload.decode("utf-8"))

    def _locations(self, method, path, line, column, extra=None):
        self._ensure_document_open(path)
        params = text_document_position(path, line, column)
        if extra:
            params.update(extra)
        result = self.request(method, params)
        if result is None:
            return []
        if isinstance(result, dict):
            result = [result]
        return [location_item(item) for item in result]

    def _ensure_document_open(self, path):
        uri = Path(path).resolve().as_uri()
        if uri not in self.open_documents:
            self.open_document(path)
        return uri


def text_document_position(path, line, column):
    return {
        "textDocument": {"uri": Path(path).resolve().as_uri()},
        "position": {"line": line - 1, "character": column - 1},
    }


def location_item(item):
    uri = item["uri"]
    start = item["range"]["start"]
    return {
        "path": uri_to_path(uri),
        "line": start["line"] + 1,
        "column": start["character"] + 1,
    }


def symbol_item(item):
    location = item.get("location", {})
    range_ = location.get("range", {}).get("start", {"line": 0, "character": 0})
    name = item.get("name")
    container = item.get("containerName")
    qualified_name = name
    if container:
        name_text = str(name or "")
        container_text = str(container)
        qualified_name = name if name_text.startswith(container_text) else f"{container_text}::{name_text}"
    return {
        "name": name,
        "kind": item.get("kind"),
        "path": uri_to_path(location.get("uri")),
        "line": range_["line"] + 1,
        "column": range_["character"] + 1,
        "qualified_name": qualified_name,
    }


def uri_to_path(uri):
    if uri is None:
        return None
    if uri.startswith("file://"):
        return Path(uri[7:]).as_posix()
    return uri


def language_id(path: Path):
    suffix = path.suffix
    if suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hxx", ".h"}:
        return "cpp"
    return "plaintext"
