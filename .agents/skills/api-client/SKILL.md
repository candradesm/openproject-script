---
name: api-client
description: CRITICAL: Load when modifying OpenProjectClient, adding new API endpoints, or changing HTTP/auth logic. Wrong payload shape or missing error handling = silent failures and broken time entries.
---

## When to use me
- Modifying `OpenProjectClient` class
- Adding new API endpoints
- Changing authentication or SSL logic
- Fixing HTTP error handling

## Not intended for
- Special days logic → use `special-days` skill
- CLI flags → use `cli-flags` skill

---

## Key Rules (MUST)

- Auth header: `Basic base64("apikey:<token>")`
- All HTTP errors → catch and re-raise as `RuntimeError`
- Time entry POST body: `"self": {"href": None}` is REQUIRED (not omitted)
- Hours format: ISO 8601 duration via `hours_to_iso8601()` — `"PT8H"`, `"PT7H30M"`
- Zero external dependencies — `urllib` only, never `requests`

## Blockers (MUST NOT)
- Adding `import requests` or any non-stdlib HTTP library
- Letting `urllib.error.HTTPError` or `urllib.error.URLError` propagate raw
- Omitting `"self": {"href": None}` from POST body → API returns 422
- Hardcoding activity ID without fallback

## POST Body Shape

```python
body = {
    "comment": {"format": "plain", "raw": comment, "html": f"<p>{comment}</p>"},
    "spentOn": spent_on.isoformat(),
    "hours":   hours_to_iso8601(hours),
    "_links": {
        "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"},
        "user":        {"href": f"/api/v3/users/{user_id}"},
        "activity":    {"href": f"/api/v3/time_entries/activities/{activity_id}"},
        "self":        {"href": None},   # ← REQUIRED
    },
}
```

## Activities Fallback Order

1. `GET /api/v3/time_entries/activities?project_id=X`
2. `GET /api/v3/time_entries/activities?work_package_id=X`
3. `GET /api/v3/time_entries/activities`
4. Extract from recent time entries via `_activities_from_time_entries()`

## Error Handling Pattern

```python
try:
    result = client.some_method()
except RuntimeError as e:
    log_error(f"Failed: {e}")
    stats["failed"] += 1
    continue
```

## References
- `.github/instructions/api-client.instructions.md` — full API client docs
