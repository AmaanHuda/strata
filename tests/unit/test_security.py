"""Unit tests for security utilities."""
from app.core.security import hash_password, verify_password, create_access_token, decode_token


def test_password_hash_and_verify():
    plain = "SecurePass123"  # keep under 72 bytes
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"