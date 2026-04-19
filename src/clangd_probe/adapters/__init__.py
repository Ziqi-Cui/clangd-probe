from __future__ import annotations

from pathlib import Path

from .base import AdapterSelection, BaseAdapter
from .generic import GenericAdapter
from .sparta import SpartaAdapter


def builtin_adapters() -> list[BaseAdapter]:
    return [GenericAdapter(), SpartaAdapter()]


def resolve_adapter(
    project_root: str | Path,
    requested_profile: str | None = None,
    extra_adapters: list[BaseAdapter] | None = None,
) -> AdapterSelection:
    root = Path(project_root).resolve()
    adapters = builtin_adapters()
    if extra_adapters:
        adapters.extend(extra_adapters)

    matches = [adapter for adapter in adapters if adapter.match(root)]
    non_generic = [adapter for adapter in matches if adapter.name != "generic"]

    if len(non_generic) > 1:
        return AdapterSelection(
            status="ambiguous",
            adapter=GenericAdapter(),
            diagnostics=[
                {
                    "error_kind": "discovery_failure",
                    "message": "multiple non-generic adapters matched the project root",
                }
            ],
            conflicts=sorted(adapter.name for adapter in non_generic),
        )

    if non_generic:
        adapter = non_generic[0]
    else:
        adapter = next(adapter for adapter in matches if adapter.name == "generic")

    if requested_profile and not adapter.supports_profiles:
        return AdapterSelection(
            status="unsupported",
            adapter=adapter,
            diagnostics=[
                {
                    "error_kind": "discovery_failure",
                    "message": f"adapter {adapter.name} does not support profiles",
                }
            ],
        )

    return AdapterSelection(
        status="ok",
        adapter=adapter,
        active_profile=requested_profile,
    )


__all__ = [
    "AdapterSelection",
    "BaseAdapter",
    "GenericAdapter",
    "SpartaAdapter",
    "builtin_adapters",
    "resolve_adapter",
]
