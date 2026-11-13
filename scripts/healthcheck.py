from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def check_http_health(url: str, timeout_s: float = 3.0) -> tuple[bool, int | None, str]:
    """Perform a fail-closed HTTP readiness check returning (ok, status_code, detail)."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            code = int(resp.status)
            return 200 <= code < 300, code, "ok"
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        exc.close()
        return False, code, f"http_error:{code}"
    except Exception as exc:
        return False, None, f"connection_error:{type(exc).__name__}"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python scripts/healthcheck.py <url> [timeout_s]", file=sys.stderr)
        return 2
    url = argv[1]
    timeout_s = float(argv[2]) if len(argv) > 2 else 3.0
    ok, code, detail = check_http_health(url, timeout_s=timeout_s)
    print(json.dumps({"url": url, "ok": ok, "status_code": code, "detail": detail}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
