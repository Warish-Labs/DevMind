"""Clerk JWT and JWKS token verification service (docs/03 §10, docs/07 §3).

Verifies token signature via RSA JWKS keys, checks issuer, expiry, authorized party (azp),
and caches keys with automatic rotation handling.
"""

from __future__ import annotations

import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel, ConfigDict

from app.core.errors import AuthenticationError
from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.integrations.clerk")


class ClerkClaims(BaseModel):
    """Verified claims extracted from a valid Clerk session token."""

    model_config = ConfigDict(extra="allow")

    sub: str  # External Clerk User ID (e.g. user_2...)
    iss: str  # Token issuer URI
    exp: int  # Expiration timestamp (seconds since Unix epoch)
    iat: int | None = None  # Issued at timestamp
    nbf: int | None = None  # Not before timestamp
    azp: str | None = None  # Authorized party (client origin)
    sid: str | None = None  # Clerk session ID
    email: str | None = None  # User email if present in session token


class ClerkTokenVerifier:
    """Verifies Clerk JWT session tokens against RSA JWKS keys."""

    def __init__(
        self,
        settings: Settings | None = None,
        jwk_client: PyJWKClient | None = None,
        static_public_key: Any = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.static_public_key = static_public_key

        if jwk_client is not None:
            self.jwk_client = jwk_client
        elif self.settings.clerk_jwks_url:
            self.jwk_client = PyJWKClient(
                self.settings.clerk_jwks_url,
                cache_keys=True,
                max_cached_keys=16,
                cache_jwk_set=True,
                lifespan=300,
            )
        elif self.settings.clerk_issuer:
            jwks_url = f"{self.settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json"
            self.jwk_client = PyJWKClient(
                jwks_url,
                cache_keys=True,
                max_cached_keys=16,
                cache_jwk_set=True,
                lifespan=300,
            )
        else:
            self.jwk_client = None

    def verify_token(self, token: str) -> ClerkClaims:
        """Verify Clerk session token and return validated claims.

        Raises:
            AuthenticationError: If token is invalid, expired, signature verification fails,
                                 or authorized party / issuer mismatch.
        """
        if not token or not token.strip():
            raise AuthenticationError("Authentication token is required")

        token = token.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        # 1. Parse unverified header to validate algorithm and key identifier
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as exc:
            logger.warning("Failed to decode token header: %s", str(exc))
            raise AuthenticationError(f"Invalid token format: {str(exc)}") from exc

        alg = unverified_header.get("alg")
        if alg != "RS256":
            logger.warning("Unsupported token algorithm: %s; expected RS256", alg)
            raise AuthenticationError(f"Invalid token algorithm: expected RS256, got {alg}")

        # 2. Resolve signing key
        key: Any = None
        if self.static_public_key is not None:
            key = self.static_public_key
        elif self.jwk_client is not None:
            try:
                signing_key = self.jwk_client.get_signing_key_from_jwt(token)
                key = signing_key.key
            except Exception as exc:
                logger.warning("Failed to resolve JWKS key: %s", str(exc))
                raise AuthenticationError(f"Token key resolution failed: {str(exc)}") from exc
        else:
            raise AuthenticationError(
                "Clerk token verification is not configured (missing clerk_jwks_url or clerk_issuer)"
            )

        # 3. Decode and verify signature, expiry, and issuer
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256"],
            "leeway": 5,  # 5-second clock skew tolerance
            "options": {"verify_exp": True},
        }

        if self.settings.clerk_issuer:
            decode_kwargs["issuer"] = self.settings.clerk_issuer

        try:
            payload = jwt.decode(token, key, **decode_kwargs)
        except jwt.ExpiredSignatureError as exc:
            logger.warning("Token expired: %s", str(exc))
            raise AuthenticationError("Token has expired") from exc
        except jwt.InvalidIssuerError as exc:
            logger.warning("Issuer mismatch: %s", str(exc))
            raise AuthenticationError("Token issuer is invalid") from exc
        except jwt.InvalidSignatureError as exc:
            logger.warning("Invalid token signature: %s", str(exc))
            raise AuthenticationError("Token signature verification failed") from exc
        except jwt.PyJWTError as exc:
            logger.warning("JWT verification error: %s", str(exc))
            raise AuthenticationError(f"Token verification failed: {str(exc)}") from exc

        # 4. Verify authorized parties (azp) if present and configured
        azp = payload.get("azp")
        configured_azp = self.settings.clerk_authorized_parties
        if azp and configured_azp:
            allowed_parties = (
                configured_azp if isinstance(configured_azp, list) else [configured_azp]
            )
            if azp not in allowed_parties:
                logger.warning(
                    "Authorized party '%s' not in allowed parties: %s", azp, allowed_parties
                )
                raise AuthenticationError(f"Authorized party '{azp}' is not permitted")

        return ClerkClaims(**payload)
