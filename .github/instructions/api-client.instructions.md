# API Client Instructions

## Overview

The `OpenProjectClient` class is the sole HTTP layer. It wraps OpenProject REST API v3 using only Python stdlib (`urllib`, `ssl`, `base64`, `json`). All requests use HTTP Basic Auth with the pattern `apikey:<token>`.

## Authentication

```python
credentials = base64.b64encode(f"apikey:{api_key}".encode()).decode()
self._auth_header = f"Basic {credentials}"
```

- API key is obtained from: *My Account → Access tokens → API*
- User ID is auto-detected via `GET /api/v3/users/me`
- Never store raw credentials — pass them at construction time

## SSL Handling

```python
if self._insecure:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
```

- Use `--insecure` flag or `OPENPROJECT_INSECURE=1` for self-signed certs
- Always warn the user when SSL verification is disabled

## Error Handling Pattern

All HTTP errors are caught and re-raised as `RuntimeError`:

```python
except urllib.error.HTTPError as e:
    raw = e.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
        message = payload.get("message") or payload.get("error") or raw
    except json.JSONDecodeError:
        message = raw
    raise RuntimeError(f"HTTP {e.code} {e.reason} → {message}") from e
except urllib.error.URLError as e:
    raise RuntimeError(f"Connection error: {e.reason}") from e
```

- Callers must catch `RuntimeError` — never let HTTP errors propagate raw
- Always extract the `message` field from JSON error bodies

## Available Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v3/users/me` | Get current authenticated user |
| `GET` | `/api/v3/projects?pageSize=200&sortBy=...` | List all projects |
| `GET` | `/api/v3/work_packages?filters=...` | List open work packages for a project |
| `GET` | `/api/v3/time_entries/activities` | List available activities |
| `GET` | `/api/v3/time_entries?filters=...` | List time entries (with filters) |
| `POST` | `/api/v3/time_entries` | Create a new time entry |

## Activity Fallback Strategy

The activities endpoint can return 400 on some instances. The client uses a multi-step fallback:

1. Try `GET /api/v3/time_entries/activities?project_id=X`
2. Try `GET /api/v3/time_entries/activities?work_package_id=X`
3. Try `GET /api/v3/time_entries/activities`
4. Fall back to extracting unique activities from the user's recent time entries

```python
def _activities_from_time_entries(self, user_id: Optional[int] = None) -> List[dict]:
    # Extracts activity links from existing time entries
```

## Time Entry Payload

```python
body = {
    "comment": {"format": "plain", "raw": comment, "html": f"<p>{comment}</p>"},
    "spentOn": spent_on.isoformat(),       # "2026-03-12"
    "hours":   hours_to_iso8601(hours),    # "PT8H" or "PT7H30M"
    "_links": {
        "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"},
        "user":        {"href": f"/api/v3/users/{user_id}"},
        "activity":    {"href": f"/api/v3/time_entries/activities/{activity_id}"},
        "self":        {"href": None},
    },
}
```

- Hours must be ISO 8601 duration: `PT8H`, `PT7H30M`
- `self.href` must be `None` (not omitted) for the POST to succeed

## Duration Parsing

```python
def hours_to_iso8601(hours: float) -> str:
    total_minutes = int(hours * 60)
    h, m = divmod(total_minutes, 60)
    return f"PT{h}H{m}M" if m else f"PT{h}H"

def _parse_iso_duration(duration: str) -> float:
    # Parses "PT8H", "PT7H30M" → float hours
```

## Best Practices
1. Always call `get_current_user()` to verify credentials before any data fetch
2. Use `_href_id(href)` to extract integer IDs from HAL `_links` hrefs
3. Catch `RuntimeError` at the call site — never let it bubble to the user raw
4. Use `pageSize=200` for projects and `pageSize=100` for work packages / time entries
5. Always pass `sortBy` to get deterministic ordering

## Common Pitfalls
1. **Forgetting `self.href = None`** in the POST body → API returns 422
2. **Not handling the activities 400 fallback** → crash on some OpenProject instances
3. **Using `requests` or any non-stdlib library** → breaks the zero-dependency constraint
4. **Hardcoding activity ID 3** without a fallback → wrong activity on different instances
