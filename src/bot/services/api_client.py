from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from src.core.config import settings


class APIClientError(Exception):
    """Обертка для ошибок взаимодействия с внутренним API."""


class APIClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not path.startswith("/"):
            path = f"/{path}"
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise APIClientError(f"API request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise APIClientError(f"API request error: {exc}") from exc

        if response.content:
            return response.json()
        return None

    async def get_bot_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/bot/users/{telegram_id}")

    async def create_bot_user(
        self,
        telegram_id: int,
        student_id: UUID | str,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "telegram_id": telegram_id,
        "student_id": str(student_id),
            "username": username,
            "email": email,
        }
        return await self._request("POST", "/bot/users", json=payload)

    async def update_bot_user_activity(self, telegram_id: int) -> None:
        await self._request("POST", f"/bot/users/{telegram_id}/activity")

    async def delete_bot_user(self, telegram_id: int) -> None:
        await self._request("DELETE", f"/bot/users/{telegram_id}")

    async def get_student_by_participant(self, participant_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/students/by-participant/{participant_id}")

    async def get_active_events(self, limit: int = 50) -> Dict[str, Any]:
        return await self._request("GET", f"/events/active?limit={limit}")

    async def get_events_by_clusters(self, cluster_ids: List[UUID | str], limit: int = 50) -> Dict[str, Any]:
        if not cluster_ids:
            return {"events": [], "total": 0}
        encoded_ids = "&".join(f"cluster_ids={str(cid)}" for cid in cluster_ids)
        return await self._request("GET", f"/events/by-clusters?{encoded_ids}&limit={limit}")

    async def get_events_bulk(self, event_ids: List[UUID | str]) -> Dict[str, Any]:
        if not event_ids:
            return {"events": [], "total": 0}
        payload = {"ids": [str(eid) for eid in event_ids]}
        return await self._request("POST", "/events/bulk", json=payload)

    async def get_event(self, event_id: UUID) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/events/{event_id}")

    async def like_event(self, event_id: UUID) -> Dict[str, Any]:
        return await self._request("POST", f"/events/{event_id}/like")

    async def dislike_event(self, event_id: UUID) -> Dict[str, Any]:
        return await self._request("POST", f"/events/{event_id}/dislike")

    async def get_recommendations(self, student_id: UUID, limit: int = 10) -> List[Dict[str, Any]]:
        result = await self._request("GET", f"/recommendations/by-student/{student_id}?limit={limit}")
        if result is None:
            return []
        return result

    async def recalculate_recommendations(self, min_score: float = 0.0) -> Dict[str, Any]:
        return await self._request("POST", "/recommendations/recalculate", json={"min_score": min_score})

    async def recalculate_recommendations_for_student(self, student_id: UUID, min_score: float = 0.0) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/recommendations/by-student/{student_id}/recalculate",
            json={"min_score": min_score},
        )

    async def submit_feedback(self, student_id: UUID, rating: int, comment: Optional[str] = None) -> Dict[str, Any]:
        payload = {"student_id": str(student_id), "rating": rating, "comment": comment}
        return await self._request("POST", "/feedback", json=payload)


api_client = APIClient(base_url=settings.internal_api_url)

