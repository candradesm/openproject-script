"""Minimal OpenProject API v3 client (stdlib only)."""
import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Dict, List, Optional, Tuple

from openproject.dates import hours_to_iso8601


class OpenProjectClient:
    """Minimal OpenProject API v3 client (stdlib only)."""

    def __init__(self, base_url: str, api_key: str, insecure: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self._insecure = insecure
        credentials = base64.b64encode(f"apikey:{api_key}".encode()).decode()
        self._auth_header = f"Basic {credentials}"

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Authorization": self._auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        ssl_ctx: Optional[ssl.SSLContext] = None
        if self._insecure:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, context=ssl_ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                message = payload.get("message") or payload.get("error") or raw
            except json.JSONDecodeError:
                message = raw
            raise RuntimeError(
                f"HTTP {e.code} {e.reason} → {message}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection error: {e.reason}") from e

    # ── Identity ──────────────────────────────────────────────────────────────

    def get_current_user(self) -> dict:
        """Return the user resource for the authenticated API key."""
        return self._request("GET", "/api/v3/users/me")

    # ── Projects ──────────────────────────────────────────────────────────────

    def get_projects(self) -> List[dict]:
        """Return all projects the current user is a member of."""
        params = urllib.parse.urlencode({
            "pageSize": 200,
            "sortBy": '[["name","asc"]]',
        })
        result = self._request("GET", f"/api/v3/projects?{params}")
        return result.get("_embedded", {}).get("elements", [])

    # ── Work packages ─────────────────────────────────────────────────────────

    def get_work_packages(self, project_id: int) -> List[dict]:
        """Return open work packages for a given project, sorted by ID desc."""
        filters = json.dumps([
            {"project_id": {"operator": "=", "values": [str(project_id)]}},
            {"status":     {"operator": "o"}},           # 'o' = open
        ])
        params = urllib.parse.urlencode({
            "filters":  filters,
            "pageSize": 100,
            "sortBy":   '[["id","desc"]]',
        })
        result = self._request("GET", f"/api/v3/work_packages?{params}")
        return result.get("_embedded", {}).get("elements", [])

    # ── Activities ────────────────────────────────────────────────────────────

    def get_activities(
        self,
        project_id: Optional[int] = None,
        work_package_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> List[dict]:
        """Return available time entry activities.

        Strategy:
          1. Try the dedicated endpoint with project_id / work_package_id / no param.
          2. If every attempt returns 400, fall back to extracting unique activities
             from the user's own recent time entries (guaranteed to work if any exist).
        """
        attempts = []
        if project_id is not None:
            attempts.append(f"/api/v3/time_entries/activities?project_id={project_id}")
        if work_package_id is not None:
            attempts.append(f"/api/v3/time_entries/activities?work_package_id={work_package_id}")
        attempts.append("/api/v3/time_entries/activities")

        for path in attempts:
            try:
                result = self._request("GET", path)
                elements = result.get("_embedded", {}).get("elements", [])
                if elements:
                    return elements
            except RuntimeError:
                continue

        # Dedicated endpoint unavailable — extract from existing time entries
        return self._activities_from_time_entries(user_id)

    def _activities_from_time_entries(self, user_id: Optional[int] = None) -> List[dict]:
        """
        Extract unique activities from the user's recent time entries.
        Each activity link in a time entry response includes href + title, which
        is enough to build a picker list.
        """
        params_dict = {"pageSize": 100, "sortBy": '[["spentOn","desc"]]'}
        if user_id is not None:
            params_dict["filters"] = json.dumps(
                [{"user_id": {"operator": "=", "values": [str(user_id)]}}]
            )
        params = urllib.parse.urlencode(params_dict)
        try:
            result = self._request("GET", f"/api/v3/time_entries?{params}")
        except RuntimeError:
            return []

        entries = result.get("_embedded", {}).get("elements", [])
        seen: set = set()
        activities: List[dict] = []
        for entry in entries:
            link  = entry.get("_links", {}).get("activity", {})
            href  = link.get("href", "")
            title = link.get("title", "")
            if href and href not in seen:
                seen.add(href)
                activities.append({
                    "name": title or href.split("/")[-1],
                    "_links": {"self": {"href": href}},
                })
        return activities

    # ── Time entries ──────────────────────────────────────────────────────────

    def get_existing_entries_for_date(self, user_id: int, spent_on: date) -> List[dict]:
        filters = json.dumps([
            {"spent_on": {"operator": "=d", "values": [spent_on.isoformat()]}},
            {"user_id":  {"operator": "=",  "values": [str(user_id)]}},
        ])
        params = urllib.parse.urlencode({"filters": filters, "pageSize": 50})
        result = self._request("GET", f"/api/v3/time_entries?{params}")
        return result.get("_embedded", {}).get("elements", [])

    def create_time_entry(
        self,
        work_package_id: int,
        user_id: int,
        activity_id: int,
        spent_on: date,
        hours: float,
        comment: str,
    ) -> dict:
        body = {
            "comment": {
                "format": "plain",
                "raw": comment,
                "html": f"<p>{comment}</p>" if comment else "",
            },
            "spentOn": spent_on.isoformat(),
            "hours": hours_to_iso8601(hours),
            "_links": {
                "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"},
                "user":        {"href": f"/api/v3/users/{user_id}"},
                "activity":    {"href": f"/api/v3/time_entries/activities/{activity_id}"},
                "self":        {"href": None},
            },
        }
        return self._request("POST", "/api/v3/time_entries", body)
