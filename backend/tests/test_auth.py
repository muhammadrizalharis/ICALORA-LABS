from app.services.auth import make_session_token, verify_session_token


def test_roundtrip_valid_token():
    token = make_session_token(42)
    assert verify_session_token(token) == 42


def test_rejects_tampered_signature():
    token = make_session_token(7)
    raw, _sig = token.rsplit(".", 1)
    tampered = f"{raw}.deadbeef"
    assert verify_session_token(tampered) is None


def test_rejects_tampered_payload():
    token = make_session_token(7)
    _raw, sig = token.rsplit(".", 1)
    # Payload asli diganti dengan payload lain tetapi signature lama dipertahankan.
    other = make_session_token(9).rsplit(".", 1)[0]
    assert verify_session_token(f"{other}.{sig}") is None


def test_rejects_none_and_garbage():
    assert verify_session_token(None) is None
    assert verify_session_token("") is None
    assert verify_session_token("no-dot-here") is None
