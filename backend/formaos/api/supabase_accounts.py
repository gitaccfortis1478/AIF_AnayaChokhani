import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)
PROFILE_FIELDS = "id,name,email,location,home_type,preferred_units"


class SupabaseAuthStore:
    def __init__(
        self,
        url: str,
        secret_key: str,
        session_days: int,
        previous_profile: Callable[[str], dict[str, str] | None],
    ) -> None:
        self._client = httpx.Client(
            base_url=f"{url.rstrip('/')}/rest/v1/",
            headers={"apikey": secret_key},
            timeout=10,
        )
        self._session_days = session_days
        self._previous_profile = previous_profile

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Supabase account request failed (%s %s): %s", method, path, type(exc).__name__)
            raise HTTPException(
                503,
                detail={"code": "account_store_unavailable", "message": "Account storage is temporarily unavailable."},
            ) from exc

    def google_user(self, claims: dict[str, Any]) -> dict[str, str]:
        subject = claims["sub"]
        rows = self._request("POST", "rpc/yourspace_sign_in_google", json={
            "subject": subject,
            "verified_email": claims["email"].strip().lower(),
            "display_name": str(claims.get("name") or claims["email"]),
            "previous_profile": self._previous_profile(subject),
        })
        return {field: rows[0][field] for field in PROFILE_FIELDS.split(",")}

    def update_profile(self, user_id: str, *, name: str, location: str, home_type: str, preferred_units: str) -> dict[str, str]:
        rows = self._request(
            "PATCH", "yourspace_users",
            params={"id": f"eq.{user_id}", "select": PROFILE_FIELDS},
            headers={"Prefer": "return=representation"},
            json={
                "name": name.strip(),
                "location": location.strip(),
                "home_type": home_type,
                "preferred_units": preferred_units,
            },
        )
        if not rows:
            raise HTTPException(404, detail={"code": "not_found", "message": "Account not found."})
        return rows[0]

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self._request("POST", "yourspace_sessions", json={
            "token_hash": self._token_hash(token),
            "user_id": user_id,
            "expires_at": (datetime.now(UTC) + timedelta(days=self._session_days)).isoformat(),
        })
        return token

    def user_for_token(self, token: str | None) -> dict[str, str] | None:
        if not token:
            return None
        rows = self._request("GET", "yourspace_sessions", params={
            "token_hash": f"eq.{self._token_hash(token)}",
            "expires_at": f"gt.{datetime.now(UTC).isoformat()}",
            "select": f"user:yourspace_users({PROFILE_FIELDS})",
        })
        return rows[0]["user"] if rows else None

    def revoke(self, token: str | None) -> None:
        if token:
            self._request("DELETE", "yourspace_sessions", params={"token_hash": f"eq.{self._token_hash(token)}"})

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
