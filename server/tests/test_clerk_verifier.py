"""Tests for Clerk token verification service (docs/03 §10, docs/07 §3)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.errors import AuthenticationError
from app.core.settings import Settings
from app.integrations.clerk.verifier import ClerkClaims, ClerkTokenVerifier


@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generate RSA key pair for testing token signing and verification."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, pem_public


def test_clerk_token_verifier_success(rsa_key_pair) -> None:
    """Verify that a valid RS256 token is successfully verified and claims extracted."""
    private_key, public_key = rsa_key_pair
    issuer = "https://clerk.devmind.warishlabs.in"
    azp = "http://localhost:3000"

    settings = Settings(
        clerk_issuer=issuer,
        clerk_authorized_parties=[azp],
    )
    verifier = ClerkTokenVerifier(settings=settings, static_public_key=public_key)

    now = int(time.time())
    payload = {
        "sub": "user_2test123456",
        "iss": issuer,
        "exp": now + 3600,
        "iat": now,
        "azp": azp,
        "sid": "sess_998877",
        "email": "dev@devmind.warishlabs.in",
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "key_1"})

    claims = verifier.verify_token(token)
    assert isinstance(claims, ClerkClaims)
    assert claims.sub == "user_2test123456"
    assert claims.iss == issuer
    assert claims.azp == azp
    assert claims.sid == "sess_998877"
    assert claims.email == "dev@devmind.warishlabs.in"


def test_clerk_token_verifier_bearer_prefix_support(rsa_key_pair) -> None:
    """Verify that Authorization: Bearer <token> format is accepted."""
    private_key, public_key = rsa_key_pair
    verifier = ClerkTokenVerifier(settings=Settings(), static_public_key=public_key)

    now = int(time.time())
    token = jwt.encode(
        {"sub": "user_bearer", "iss": "test", "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )
    claims = verifier.verify_token(f"Bearer {token}")
    assert claims.sub == "user_bearer"


def test_clerk_token_verifier_expired_token(rsa_key_pair) -> None:
    """Verify that expired token raises AuthenticationError with 401 code."""
    private_key, public_key = rsa_key_pair
    verifier = ClerkTokenVerifier(settings=Settings(), static_public_key=public_key)

    past = int(time.time()) - 3600
    token = jwt.encode(
        {"sub": "user_expired", "iss": "test", "exp": past},
        private_key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    with pytest.raises(AuthenticationError, match="Token has expired"):
        verifier.verify_token(token)


def test_clerk_token_verifier_invalid_signature(rsa_key_pair) -> None:
    """Verify that token signed by an untrusted key fails signature validation."""
    _, public_key = rsa_key_pair
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    verifier = ClerkTokenVerifier(settings=Settings(), static_public_key=public_key)

    now = int(time.time())
    token = jwt.encode(
        {"sub": "user_alien", "iss": "test", "exp": now + 300},
        other_private_key,
        algorithm="RS256",
        headers={"kid": "alien_key"},
    )

    with pytest.raises(AuthenticationError, match="Token signature verification failed"):
        verifier.verify_token(token)


def test_clerk_token_verifier_issuer_mismatch(rsa_key_pair) -> None:
    """Verify that an untrusted issuer is rejected."""
    private_key, public_key = rsa_key_pair
    settings = Settings(clerk_issuer="https://legitimate.clerk.accounts.dev")
    verifier = ClerkTokenVerifier(settings=settings, static_public_key=public_key)

    now = int(time.time())
    token = jwt.encode(
        {"sub": "user_attacker", "iss": "https://malicious.issuer.dev", "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    with pytest.raises(AuthenticationError, match="Token issuer is invalid"):
        verifier.verify_token(token)


def test_clerk_token_verifier_unauthorized_party(rsa_key_pair) -> None:
    """Verify that azp not matching clerk_authorized_parties is rejected."""
    private_key, public_key = rsa_key_pair
    settings = Settings(clerk_authorized_parties=["https://devmind.warishlabs.in"])
    verifier = ClerkTokenVerifier(settings=settings, static_public_key=public_key)

    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user_phish",
            "iss": "test",
            "exp": now + 300,
            "azp": "https://evil-phishing-site.com",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    with pytest.raises(AuthenticationError, match="Authorized party '.*' is not permitted"):
        verifier.verify_token(token)


def test_clerk_token_verifier_rejects_symmetric_algorithm() -> None:
    """Verify that non-RS256 tokens (e.g. HS256) are rejected to prevent key confusion attacks."""
    verifier = ClerkTokenVerifier(settings=Settings(), static_public_key=b"secret")

    token = jwt.encode({"sub": "user_hs256"}, "secret", algorithm="HS256")

    with pytest.raises(
        AuthenticationError, match="Invalid token algorithm: expected RS256, got HS256"
    ):
        verifier.verify_token(token)


def test_clerk_token_verifier_empty_and_malformed() -> None:
    """Verify that empty, whitespace, or malformed strings raise AuthenticationError."""
    verifier = ClerkTokenVerifier(settings=Settings())

    with pytest.raises(AuthenticationError, match="Authentication token is required"):
        verifier.verify_token("")

    with pytest.raises(AuthenticationError, match="Authentication token is required"):
        verifier.verify_token("   ")

    with pytest.raises(AuthenticationError, match="Invalid token format"):
        verifier.verify_token("not-a-jwt")
