"""Resolve IANA service names to canonical ports and protocols.

The operating system ships a services file (on POSIX systems it's
/etc/services, on Windows it's %SystemRoot%\\System32\\drivers\\etc\\services)
that lists the canonical IANA service-name-to-port mappings. Parsing that
file ourselves is more reliable than hard-coding a subset: it stays in sync
with the host and requires zero network access and zero third-party deps.

The resolver is intentionally tiny: it looks up a name (and optionally a
protocol) and returns the canonical port plus the transport protocol as
recorded in the file. It does not reverse-resolve, it does not list all
services, and it does not know about any alias beyond what the services
file itself lists.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ServiceInfo:
    """The resolved mapping for a single IANA service entry.

    `name` is the primary service name (the first token on a non-comment
    line in the services file). `aliases` holds any additional names listed
    for the same port/protocol. We expose them because callers sometimes
    only know an alias (e.g. "www" for "http") and may want to confirm that
    it resolved to the same canonical entry.
    """

    name: str
    port: int
    protocol: str
    aliases: tuple[str, ...]


# These are the only places the well-known services file lives across the
# major desktop/server operating systems. We try them in order and use the
# first one that exists. If none exist, `resolve` returns None — failing
# softly is better than raising, because callers typically want to fall
# back to a hardcoded default rather than crash on a misconfigured host.
_DEFAULT_PATHS = (
    "/etc/services",
    "/usr/etc/services",
    "/usr/local/etc/services",
    os.path.join(
        os.environ.get("SystemRoot", r"C:\\Windows"),
        "System32",
        "drivers",
        "etc",
        "services",
    ),
)


def _find_services_file() -> Optional[str]:
    for candidate in _DEFAULT_PATHS:
        if os.path.isfile(candidate):
            return candidate
    return None


def _parse_line(line: str) -> Optional[tuple[str, int, str, tuple[str, ...]]]:
    """Parse a single non-comment line from a services file.

    The IANA format is:

        name  port/protocol [aliases ...]  # optional comment

    Returns (primary_name, port, protocol, aliases) or None for
    comment/blank lines and anything we cannot unambiguously parse. We are
    deliberately strict here: a malformed entry is skipped rather than
    guessed at, because guessing at a port number is the kind of thing that
    produces silent security bugs.
    """
    # Strip trailing comment.
    hash_pos = line.find("#")
    if hash_pos != -1:
        line = line[:hash_pos]
    line = line.strip()
    if not line:
        return None

    parts = line.split()
    if len(parts) < 2:
        return None

    name = parts[0]
    port_proto = parts[1]
    aliases = tuple(parts[2:])

    if "/" not in port_proto:
        return None
    port_str, proto = port_proto.split("/", 1)
    if not port_str.isdigit():
        # Port ranges (e.g. "6000-6001/tcp") appear in some services files.
        # We don't resolve ranges to a single port, so skip them.
        return None
    port = int(port_str)
    # Protocol names in the IANA file are lowercase by convention, but we
    # normalise defensively so lookups against "TCP" still work.
    protocol = proto.lower()
    return name, port, protocol, aliases


def _load_index(path: str) -> dict[tuple[str, str], ServiceInfo]:
    """Build a (name-or-alias, protocol) -> ServiceInfo index from `path`.

    When the same (name, protocol) maps to multiple ports we keep the first
    entry encountered. IANA conventionally orders most-specific entries
    first, and the services file is stable across releases, so "first wins"
    is deterministic.
    """
    index: dict[tuple[str, str], ServiceInfo] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            parsed = _parse_line(raw)
            if parsed is None:
                continue
            name, port, protocol, aliases = parsed
            info = ServiceInfo(
                name=name, port=port, protocol=protocol, aliases=aliases
            )
            key = (name, protocol)
            if key not in index:
                index[key] = info
            for alias in aliases:
                alias_key = (alias, protocol)
                if alias_key not in index:
                    index[alias_key] = info
    return index


def resolve(
    name: str,
    protocol: Optional[str] = None,
    *,
    path: Optional[str] = None,
) -> Optional[ServiceInfo]:
    """Resolve an IANA service name to its canonical port and protocol.

    Parameters
    ----------
    name:
        Service name as it appears in the services file (e.g. "http",
        "https", "domain"). Case-insensitive.
    protocol:
        Optional transport protocol (e.g. "tcp" or "udp"). Case-insensitive.
        If omitted, the first entry for `name` (in file order) is returned.
    path:
        Optional explicit path to a services file. If omitted, the resolver
        searches the standard OS locations.

    Returns
    -------
    ServiceInfo or None
        None if the name/protocol pair is unknown or if no services file can
        be located on the host.

    Notes
    -----
    Lookups are case-insensitive because real-world inputs (URL schemes,
    /etc/hosts conventions) vary in case and the IANA registry itself is
    case-insensitive.
    """
    services_path = path if path is not None else _find_services_file()
    if services_path is None or not os.path.isfile(services_path):
        return None

    index = _load_index(services_path)
    key_name = name.lower()
    if protocol is not None:
        key_proto = protocol.lower()
        return index.get((key_name, key_proto))

    # No protocol specified: return the first entry in file order.
    # Because dict preserves insertion order in Python 3.7+, iterating the
    # values gives us file order for the primary name.
    for info in index.values():
        if info.name.lower() == key_name:
            return info
    # Fall back to aliases, also in file order.
    for info in index.values():
        if any(a.lower() == key_name for a in info.aliases):
            return info
    return None
