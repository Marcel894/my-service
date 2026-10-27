# my-service

Resolves IANA service names (like `http`, `https`, `domain`) to their canonical port numbers and transport protocols by parsing the operating system's built-in services file — `/etc/services` on POSIX systems, `C:\Windows\System32\drivers\etc\services` on Windows. Zero third-party dependencies; standard library only.

```python
from my_service import resolve

info = resolve("http", "tcp")
print(info.port, info.protocol)  # 80 tcp

# Omit the protocol to get the first recorded entry for a name:
print(resolve("ssh").port)  # 22

# Unknown services resolve to None:
print(resolve("nope", "tcp"))  # None
```

## Why this exists

When you need to turn a service name into a port, the robust answer is whatever the host already believes. The IANA registry is baked into every mainstream operating system, and parsing that file is faster, simpler, and more accurate than shipping a hand-maintained copy that drifts. This library exists to do exactly that, and nothing else: no reverse lookups, no enumeration, no network calls.

The trade-off is that the result depends on the host's services file. On a stripped-down container the file may be absent; in that case `resolve` returns `None` rather than raising, so callers can fall back to a hardcoded default.

## The awkward edge

Some services (notably `http`/`www`) are registered under aliases. This resolver indexes aliases too, so `resolve("www", "tcp")` returns the canonical `http` entry with `www` listed in `aliases`. Entries that map a name to a *range* of ports (e.g. X11's `6000-6001/tcp` on some systems) are skipped — a range cannot be collapsed to a single port without a policy choice, and inventing one would be worse than refusing.
