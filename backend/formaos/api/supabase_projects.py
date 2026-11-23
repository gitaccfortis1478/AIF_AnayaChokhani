import logging
from typing import Any

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)
PROJECT_FIELDS = "project_id,project_name,updated_at,draft_progress"
DESIGN_FIELDS = "design_id,session_id,generated_at,status,design_data,project:yourspace_projects!inner(project_id,project_name,user_id)"
PROJECT_TABLE = "yourspace_projects"
DESIGN_TABLE = "yourspace_designs"


def metadata_only(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: metadata_only(item)
            for key, item in value.items()
            if not (isinstance(item, str) and item.startswith("data:image/"))
        }
    if isinstance(value, list):
        return [metadata_only(item) for item in value]
    return None if isinstance(value, str) and value.startswith("data:image/") else value


def restore_images(metadata: Any, local: Any) -> Any:
    if isinstance(metadata, dict) and isinstance(local, dict):
        result = {key: restore_images(value, local.get(key)) for key, value in metadata.items()}
        result.update({
            key: value for key, value in local.items()
            if key not in metadata and isinstance(value, str) and value.startswith("data:image/")
        })
        return result
    if isinstance(metadata, list) and isinstance(local, list):
        return [restore_images(item, local[index] if index < len(local) else None) for index, item in enumerate(metadata)]
    if metadata is None and isinstance(local, str) and local.startswith("data:image/"):
        return local
    return metadata


class SupabaseProjectStore:
    def __init__(self, url: str, secret_key: str) -> None:
        self._client = httpx.Client(
            base_url=f"{url.rstrip('/')}/rest/v1/",
            headers={"apikey": secret_key},
            timeout=10,
        )

    def _request(self, method: str, table: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, table, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except (httpx.HTTPError, ValueError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            logger.warning("Supabase project request failed (%s %s): %s %s", method, table, type(exc).__name__, status)
            raise HTTPException(503, detail={
                "code": "project_store_unavailable", "message": "Project storage is temporarily unavailable.",
            }) from exc

    def _list(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        rows = []
        page_size = 100
        while True:
            page = self._request("GET", table, params={**params, "limit": page_size, "offset": len(rows)})
            rows.extend(page)
            if len(page) < page_size:
                return rows

    def list_projects(self, owner_id: str) -> list[dict[str, Any]]:
        return self._list(PROJECT_TABLE, {
            "user_id": f"eq.{owner_id}", "select": PROJECT_FIELDS, "order": "updated_at.desc,project_id.asc",
        })

    def ensure_project(self, project_id: str, owner_id: str, name: str) -> None:
        filters = {
            "project_id": f"eq.{project_id}", "user_id": f"eq.{owner_id}", "select": "project_id",
        }
        if self._request("GET", PROJECT_TABLE, params=filters):
            return
        # A conflicting insert cannot change another account's ownership.
        inserted = self._request(
            "POST", PROJECT_TABLE, params={"on_conflict": "project_id"},
            headers={"Prefer": "resolution=ignore-duplicates,return=representation"},
            json={"project_id": project_id, "project_name": name, "user_id": owner_id},
        )
        if not inserted and not self._request("GET", PROJECT_TABLE, params=filters):
            raise HTTPException(404, detail={"code": "not_found", "message": "Project not found."})

    def save_draft(self, project_id: str, owner_id: str, name: str, draft: dict[str, Any]) -> None:
        filters = {
            "project_id": f"eq.{project_id}", "user_id": f"eq.{owner_id}", "select": "project_id",
        }
        fields = {"project_name": name, "draft_progress": metadata_only(draft)}
        headers = {"Prefer": "return=representation"}
        if self._request("PATCH", PROJECT_TABLE, params=filters, headers=headers, json=fields):
            return
        self.ensure_project(project_id, owner_id, name)
        if not self._request("PATCH", PROJECT_TABLE, params=filters, headers=headers, json=fields):
            raise HTTPException(404, detail={"code": "not_found", "message": "Project not found."})

    def delete_project(self, project_id: str, owner_id: str) -> bool:
        return bool(self._request("DELETE", PROJECT_TABLE, params={
            "project_id": f"eq.{project_id}", "user_id": f"eq.{owner_id}", "select": "project_id",
        }, headers={"Prefer": "return=representation"}))

    @staticmethod
    def design_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            **row["design_data"], **row["project"],
            "design_id": row["design_id"], "session_id": row["session_id"] or "",
            "generated_at": row["generated_at"], "status": row["status"],
        }

    def get_design(self, design_id: str, owner_id: str) -> dict[str, Any] | None:
        rows = self._request("GET", DESIGN_TABLE, params={
            "design_id": f"eq.{design_id}", "project.user_id": f"eq.{owner_id}", "select": DESIGN_FIELDS,
        })
        return self.design_payload(rows[0]) if rows else None

    def list_designs(self, owner_id: str, project_id: str | None = None) -> list[dict[str, Any]]:
        params = {"project.user_id": f"eq.{owner_id}", "select": DESIGN_FIELDS,
                  "order": "generated_at.desc,design_id.asc"}
        if project_id:
            params["project_id"] = f"eq.{project_id}"
        return [self.design_payload(row) for row in self._list(DESIGN_TABLE, params)]

    def save_design(self, design: dict[str, Any], summary: dict[str, Any]) -> None:
        self.ensure_project(summary["project_id"], summary["user_id"], design.get("project_name") or summary["project_name"])
        columns = (
            "design_id", "project_id", "session_id", "generated_at", "status",
            "room_type", "total_price_inr", "item_count", "style_words",
        )
        self._request("POST", DESIGN_TABLE, params={"on_conflict": "design_id"},
                      headers={"Prefer": "resolution=merge-duplicates"}, json={
            **{key: summary[key] for key in columns},
            "design_data": metadata_only({
                key: value for key, value in design.items()
                if key not in {"design_id", "project_id", "session_id", "generated_at", "status",
                               "user_id", "project_name", "image_data_url"}
            }),
        })
