import logging
from typing import Dict, Any, Tuple, Optional
import httpx
from app.config import settings

logger = logging.getLogger("linkplease.client")

class PseudoGramClient:
    """
    HTTP client for calling Mock PseudoGram API.
    Handles X-API-Key and Idempotency-Key headers.
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or settings.PSEUDOGRAM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.PSEUDOGRAM_API_KEY

    def _headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def send_dm(
        self,
        job_id: int,
        recipient_user_id: str,
        message: str,
        comment_id: str
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        """
        Sends DM via POST /v1/dm/send.
        Returns tuple of (status_code, response_json, response_headers).
        """
        url = f"{self.base_url}/v1/dm/send"
        idempotency_key = f"dm-job-{job_id}"
        payload = {
            "recipient_user_id": recipient_user_id,
            "message": message,
            "comment_id": comment_id
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._headers(idempotency_key)
                )
                headers_dict = dict(response.headers)
                try:
                    data = response.json()
                except Exception:
                    data = {"raw": response.text}
                return response.status_code, data, headers_dict
            except httpx.RequestError as exc:
                logger.error(f"Network error sending DM for job {job_id}: {exc}")
                return 500, {"error": f"Network error: {str(exc)}"}, {}

    async def get_dm_status(self, dm_id: str) -> Tuple[int, Dict[str, Any]]:
        """
        Checks DM status via GET /v1/dm/{dm_id}.
        Does NOT count against DM rate limit.
        """
        url = f"{self.base_url}/v1/dm/{dm_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, headers=self._headers())
                try:
                    data = response.json()
                except Exception:
                    data = {"raw": response.text}
                return response.status_code, data
            except httpx.RequestError as exc:
                logger.error(f"Network error querying status for dm_id {dm_id}: {exc}")
                return 500, {"error": f"Network error: {str(exc)}"}

pseudogram_client = PseudoGramClient()
