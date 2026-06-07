#!/usr/bin/env python3
"""Validate a URL against the cybersecurity-expert trusted-source allowlist.

This is the deterministic anti-poisoning gate for the skill's "update news" mode.
Before fetching ANY url while refreshing the threat landscape, run:

    python3 scripts/check_source.py <url> [<url> ...]

Exit code 0 and a line "ALLOW <url>" only if the host is on (or a subdomain of) the
allowlist in assets/trusted_sources.json AND the scheme is https. Otherwise it prints
"BLOCK <url> <reason>" and exits non-zero. The agent must skip any BLOCKed URL.

Keeping this in code (rather than trusting the model to eyeball domains) means the
allowlist is enforced the same way every time and can't be argued out of by content on
a page. The script reads the allowlist fresh each run, so it always reflects the file.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ALLOWLIST_PATH = Path(__file__).resolve().parent.parent / "assets" / "trusted_sources.json"


def load_domains() -> list[str]:
    data = json.loads(ALLOWLIST_PATH.read_text())
    domains = [d.strip().lower().lstrip(".") for d in data.get("domains", []) if d.strip()]
    if not domains:
        raise SystemExit("ERROR: allowlist is empty; refusing to allow anything.")
    return domains


def host_allowed(host: str, domains: list[str]) -> bool:
    host = host.lower().strip(".")
    # Exact match or a subdomain of an allowlisted domain. A trailing-dot/label
    # boundary check prevents "evilcisa.gov" from matching "cisa.gov".
    return any(host == d or host.endswith("." + d) for d in domains)


def check(url: str, domains: list[str]) -> tuple[bool, str]:
    try:
        parsed = urlparse(url.strip())
    except Exception as exc:  # noqa: BLE001
        return False, f"unparseable ({exc})"
    if parsed.scheme != "https":
        return False, f"scheme must be https (got '{parsed.scheme or 'none'}')"
    host = parsed.hostname or ""
    if not host:
        return False, "no hostname"
    # Reject IP-literal hosts outright; the allowlist is domain-based.
    if host.replace(".", "").isdigit() or ":" in host:
        return False, "IP-literal host not allowed"
    if not host_allowed(host, domains):
        return False, "host not on trusted-source allowlist"
    return True, "host on allowlist"


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_source.py <url> [<url> ...]", file=sys.stderr)
        return 2
    domains = load_domains()
    any_blocked = False
    for url in argv:
        ok, reason = check(url, domains)
        if ok:
            print(f"ALLOW {url}")
        else:
            print(f"BLOCK {url} -- {reason}")
            any_blocked = True
    return 1 if any_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
