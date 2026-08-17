import os
import hmac
import hashlib
from app.config import settings

def verify_hmac_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Verifies HMAC-SHA256 webhook signature.

    The signature header format is: 'sha256=<hex>'
    The signature is HMAC-SHA256(raw_request_body, API_KEY).

    Respects WEBHOOK_SIGNATURE_REQUIRED / VERIFY_WEBHOOK_SIGNATURE env var.
    When disabled, all requests pass (useful for local dev/testing).
    """
    # Check both env var names; WEBHOOK_SIGNATURE_REQUIRED takes precedence
    env_val = os.getenv("WEBHOOK_SIGNATURE_REQUIRED") or os.getenv("VERIFY_WEBHOOK_SIGNATURE")
    if env_val is not None:
        should_verify = env_val.lower() in ("true", "1", "yes")
    else:
        should_verify = settings.WEBHOOK_SIGNATURE_REQUIRED

    if not should_verify:
        return True

    if not signature_header:
        return False

    secret = settings.hmac_secret
    if not secret:
        # No secret configured — allow the request (misconfiguration warning)
        return True

    parts = signature_header.split("=", 1)
    if len(parts) != 2 or parts[0].lower() != "sha256":
        return False

    expected_hex = parts[1].strip()

    calculated = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(calculated.lower(), expected_hex.lower())
