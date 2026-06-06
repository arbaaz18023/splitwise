from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.config import settings


def verify_google_token(token: str) -> dict:
    """
    Verify a Google ID token and return the decoded payload.
    Returns a dict with: sub, name, email, picture
    Raises ValueError if token is invalid or expired.
    """
    try:
        request = google_requests.Request()

        if settings.GOOGLE_CLIENT_ID:
            payload = id_token.verify_oauth2_token(
                token, request, settings.GOOGLE_CLIENT_ID
            )
        else:
            payload = id_token.verify_oauth2_token(token, request)

        return payload
    except Exception as exc:
        raise ValueError(f"Google token verification failed: {exc}") from exc
