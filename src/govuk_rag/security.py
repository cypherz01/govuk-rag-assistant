"""Access control: the shared demo key that callers of ``/chat`` must send."""

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

DEMO_KEY_HEADER = "X-Demo-Key"

_demo_key_header = APIKeyHeader(name=DEMO_KEY_HEADER, auto_error=False)


def demo_key_guard(expected: SecretStr | None) -> Callable[[str | None], None]:
    """A FastAPI dependency that rejects requests without the right demo key.

    With no key configured every request is refused, so a missing secret fails closed.
    Keys are compared in constant time so response timing doesn't reveal how much matched.
    """

    def require_demo_key(
        provided: Annotated[str | None, Security(_demo_key_header)],
    ) -> None:
        if expected is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Access is not configured: set the demo key.",
            )
        if provided is None or not secrets.compare_digest(
            provided.encode(), expected.get_secret_value().encode()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid demo key.",
            )

    return require_demo_key
