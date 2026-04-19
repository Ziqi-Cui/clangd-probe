#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import time


def read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("utf-8").split(":", 1)
        headers[key.strip().lower()] = value.strip()

    length = int(headers["content-length"])
    payload = sys.stdin.buffer.read(length)
    if not payload:
        return None
    return json.loads(payload.decode("utf-8"))


def write_message(payload):
    body = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


STATE = {
    "opened": [],
}


def handle_request(message):
    method = message["method"]
    msg_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "capabilities": {
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "hoverProvider": True,
                    "documentSymbolProvider": True,
                    "workspaceSymbolProvider": True,
                }
            },
        }

    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    if method == "textDocument/definition":
        uri = params["textDocument"]["uri"]
        if os.environ.get("FAKE_CLANGD_REQUIRE_OPEN_FOR_POSITIONS") == "1" and uri not in STATE["opened"]:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32001, "message": "trying to get AST for non-added document"},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": [
                {
                    "uri": params["textDocument"]["uri"],
                    "range": {
                        "start": {"line": 9, "character": 2},
                        "end": {"line": 9, "character": 8},
                    },
                }
            ],
        }

    if method == "textDocument/references":
        uri = params["textDocument"]["uri"]
        if os.environ.get("FAKE_CLANGD_REQUIRE_OPEN_FOR_POSITIONS") == "1" and uri not in STATE["opened"]:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32001, "message": "trying to get AST for non-added document"},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": [
                {
                    "uri": uri,
                    "range": {
                        "start": {"line": 12, "character": 4},
                        "end": {"line": 12, "character": 10},
                    },
                },
                {
                    "uri": uri,
                    "range": {
                        "start": {"line": 20, "character": 1},
                        "end": {"line": 20, "character": 7},
                    },
                },
            ],
        }

    if method == "textDocument/hover":
        uri = params["textDocument"]["uri"]
        if os.environ.get("FAKE_CLANGD_REQUIRE_OPEN_FOR_POSITIONS") == "1" and uri not in STATE["opened"]:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32001, "message": "trying to get AST for non-added document"},
            }
        if os.environ.get("FAKE_CLANGD_NULL_HOVER") == "1":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": None,
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "contents": {
                    "kind": "markdown",
                    "value": "```cpp\nint demo()\n```",
                }
            },
        }

    if method == "textDocument/documentSymbol":
        uri = params["textDocument"]["uri"]
        if os.environ.get("FAKE_CLANGD_REQUIRE_OPEN_FOR_SYMBOLS") == "1" and uri not in STATE["opened"]:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32001, "message": "trying to get AST for non-added document"},
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": [
                {
                    "name": "Demo",
                    "kind": 5,
                    "location": {
                        "uri": uri,
                        "range": {
                            "start": {"line": 1, "character": 0},
                            "end": {"line": 5, "character": 1},
                        },
                    },
                }
            ],
        }

    if method == "workspace/symbol":
        query = params["query"]
        if query == "Missing":
            result = []
        else:
            result = [
                {
                    "name": "Demo::solve",
                    "kind": 12,
                    "location": {
                        "uri": "file:///tmp/demo.cpp",
                        "range": {
                            "start": {"line": 4, "character": 2},
                            "end": {"line": 4, "character": 7},
                        },
                    },
                }
            ]
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Unhandled method {method}"},
    }


def handle_notification(message):
    method = message["method"]
    if method == "textDocument/didOpen":
        STATE["opened"].append(message["params"]["textDocument"]["uri"])
    if method == "exit":
        if os.environ.get("FAKE_CLANGD_SLOW_EXIT") == "1":
            time.sleep(2)
        raise SystemExit(0)


def main():
    while True:
        message = read_message()
        if message is None:
            return 0
        if "id" in message:
            write_message(handle_request(message))
        else:
            handle_notification(message)


if __name__ == "__main__":
    raise SystemExit(main())
