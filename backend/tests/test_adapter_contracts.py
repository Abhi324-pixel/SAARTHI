"""The SAME contract runs against the mock and the real implementation of every adapter.
If these pass for both, flipping SAARTHI_<AREA>=mock -> db/supabase changes only where data comes from."""

import jwt
import pytest

from app import adapters, db as dbm
from app.adapters import impl
from app.adapters.base import MentorRecord
from app.config import settings
from app.models import Learner, new_id


@pytest.fixture()
def s():
    dbm.configure("sqlite://")
    dbm.init_db()
    sess = dbm.SessionLocal()
    impl.seed_mentors(sess)
    impl.seed_cohort(sess)
    sess.commit()
    yield sess
    sess.close()


def mk(s, age):
    lr = Learner(id=new_id("t_"), name="X", age=age)
    s.add(lr)
    s.flush()
    return lr


# ---- mentors -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("directory", [impl.MockMentorDirectory(), impl.DbMentorDirectory()], ids=["mock", "db"])
def test_mentor_directory_contract(s, directory):
    allm = directory.list(s)
    assert len(allm) == 6
    assert {m.tier for m in allm} == {"skill_mentor", "margdarshak"}
    assert all(isinstance(m, MentorRecord) and m.verification_status == "verified" for m in allm)
    assert {m.id for m in directory.list(s, "margdarshak")} == {"mock_mg_rajesh", "mock_mg_sunita", "mock_mg_mohan"}
    assert directory.get(s, "mock_sm_ananya").name == "Ananya Rao"
    assert directory.get(s, "does_not_exist") is None


def test_mock_and_db_mentors_return_identical_data(s):
    a = {m.id: m.public() for m in impl.MockMentorDirectory().list(s)}
    b = {m.id: m.public() for m in impl.DbMentorDirectory().list(s)}
    assert a == b


# ---- consent -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("provider", [impl.MockConsent(), impl.DbConsent()], ids=["mock", "db"])
def test_consent_contract_adult(s, provider):
    adult = mk(s, 22)
    assert provider.status(s, adult, "mentor_sessions") == "granted"
    assert provider.status(s, adult, "transcript_share") == "pending"


@pytest.mark.parametrize("provider", [impl.MockConsent(), impl.DbConsent()], ids=["mock", "db"])
def test_consent_contract_minor_needs_a_guardian(s, provider):
    minor = mk(s, 16)
    assert provider.status(s, minor, "mentor_sessions") == "pending"
    req = provider.request(s, minor, "mentor_sessions")
    assert req["needs_guardian"]
    if provider.is_mock:
        assert req["guardian_token"]  # demo only
        out = provider.grant(s, minor, "mentor_sessions", "guardian")
        assert out["mock"] and "(demo)" in out["granted_by"]
    else:
        # SECURITY: the real adapter must never hand the guardian token to the learner who asked
        assert "guardian_token" not in req and set(req) == {"scope", "status", "needs_guardian", "guardian_hint"}
        with pytest.raises(PermissionError):
            provider.grant(s, minor, "mentor_sessions", "guardian")  # no token
        with pytest.raises(PermissionError):
            provider.grant(s, minor, "mentor_sessions", "guardian", token="forged")
        provider.grant(s, minor, "mentor_sessions", "guardian", token=impl.mint_guardian_token(minor, "mentor_sessions"))
    assert provider.status(s, minor, "mentor_sessions") == "granted"
    provider.revoke(s, minor, "mentor_sessions")
    assert provider.status(s, minor, "mentor_sessions") == "revoked"


def test_guardian_token_is_bound_to_one_learner(s):
    a, b = mk(s, 15), mk(s, 15)
    tok = impl.mint_guardian_token(a, "mentor_sessions")
    with pytest.raises(PermissionError):
        impl.DbConsent().grant(s, b, "mentor_sessions", "guardian", token=tok)
    with pytest.raises(PermissionError):  # and bound to one scope
        impl.DbConsent().grant(s, a, "transcript_share", "guardian", token=tok)


# ---- cohort ----------------------------------------------------------------------------------------------
def test_cohort_providers_agree_on_the_numbers(s):
    m = impl.MockCohort().summary(s, impl.MOCK_COHORT_ID)
    d = impl.DbCohort().summary(s, impl.MOCK_COHORT_ID)
    assert m["is_mock"] and not d["is_mock"]
    for k in ("n_learners", "concepts", "top_misconceptions", "needs_attention"):
        assert m[k] == d[k], k
    assert m["n_learners"] == 24 and m["top_misconceptions"]


# ---- auth ---------------------------------------------------------------------------------------------------
def test_mock_auth_roundtrip(s):
    a = impl.MockAuth()
    out = a.login(s, name="Priya", age=17, language="hindi", email=None)
    p = a.authenticate(s, out["token"])
    assert p.learner_id == out["learner_id"] and p.is_mock
    lr = s.get(Learner, p.learner_id)
    assert lr.age == 17 and lr.language_pref == "hindi" and lr.is_mock


def test_mock_auth_rejects_garbage_and_foreign_tokens(s):
    a = impl.MockAuth()
    with pytest.raises(impl.AuthError):
        a.authenticate(s, "garbage")
    forged = jwt.encode({"sub": "x", "mock": True}, "another-secret-another-secret-123", algorithm="HS256")
    with pytest.raises(impl.AuthError):
        a.authenticate(s, forged)


# ---- Supabase asymmetric JWT signing keys (JWKS) ----------------------------------------------------------------
import time as _time

from cryptography.hazmat.primitives.asymmetric import ec

SB_URL = "https://testproj.supabase.co"
ISS = SB_URL + "/auth/v1"


def _ec_key(kid):
    priv = ec.generate_private_key(ec.SECP256R1())
    jwk = jwt.algorithms.ECAlgorithm.to_jwk(priv.public_key(), as_dict=True)
    jwk.update({"kid": kid, "alg": "ES256", "use": "sig"})
    return priv, jwk


class StaticJWKS:
    """Stands in for PyJWKClient: serves a fixed JWK set (no network) and selects the key by the token's kid."""
    def __init__(self, jwks):
        self.set = jwt.PyJWKSet.from_dict({"keys": jwks})

    def get_signing_key_from_jwt(self, token):
        kid = jwt.get_unverified_header(token).get("kid")
        for k in self.set.keys:
            if k.key_id == kid:
                return k
        raise jwt.PyJWKClientError(f"Unable to find a signing key that matches: {kid}")


def _token(priv, kid="k1", **over):
    claims = {"sub": "uuid-123", "aud": "authenticated", "iss": ISS, "exp": int(_time.time()) + 600, "email": "asha@example.com",
              "user_metadata": {"name": "Asha", "age": 19, "language": "hindi"}}
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, priv, algorithm="ES256", headers={"kid": kid})


@pytest.fixture()
def sb(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", SB_URL + "/")
    monkeypatch.setattr(settings, "supabase_jwt_secret", None)
    priv, jwk = _ec_key("k1")
    other_priv, other_jwk = _ec_key("k2")
    return impl.SupabaseAuth(jwks_client=StaticJWKS([jwk, other_jwk])), priv, other_priv


def test_supabase_valid_token_creates_the_learner_on_first_sight(s, sb):
    a, priv, _ = sb
    p = a.authenticate(s, _token(priv))
    assert p.learner_id == "uuid-123" and not p.is_mock and p.email == "asha@example.com"
    lr = s.get(Learner, "uuid-123")
    assert (lr.name, lr.age, lr.language_pref, lr.is_mock) == ("Asha", 19, "hindi", False)
    lr.name = "Renamed"
    s.flush()
    assert a.authenticate(s, _token(priv)).name == "Renamed"  # second sight reuses the row


def test_supabase_picks_the_key_by_kid(s, sb):
    a, priv, other = sb
    assert a.authenticate(s, _token(other, kid="k2")).learner_id == "uuid-123"


def test_supabase_rejects_a_token_signed_with_the_wrong_key(s, sb):
    a, priv, other = sb
    with pytest.raises(impl.AuthError):
        a.authenticate(s, _token(other, kid="k1"))        # claims to be k1, signed by someone else
    with pytest.raises(impl.AuthError):
        a.authenticate(s, _token(priv, kid="unknown"))     # kid not in the key set


def test_supabase_rejects_expired_wrong_audience_wrong_issuer_and_missing_claims(s, sb):
    a, priv, _ = sb
    for bad in (_token(priv, exp=int(_time.time()) - 5), _token(priv, aud="anon"), _token(priv, aud=None),
                _token(priv, iss="https://evil.supabase.co/auth/v1"), _token(priv, sub=None), _token(priv, exp=None)):
        with pytest.raises(impl.AuthError):
            a.authenticate(s, bad)


def test_supabase_rejects_unsigned_and_hs256_tokens_by_default(s, sb):
    a, priv, _ = sb
    base = {"sub": "x", "aud": "authenticated", "iss": ISS, "exp": int(_time.time()) + 60}
    with pytest.raises(impl.AuthError):
        a.authenticate(s, jwt.encode(base, None, algorithm="none"))
    with pytest.raises(impl.AuthError):
        a.authenticate(s, jwt.encode(base, "some-shared-secret-some-shared-secret", algorithm="HS256"))
    with pytest.raises(impl.AuthError):
        a.authenticate(s, "garbage")


def test_supabase_hs256_fallback_only_when_the_secret_is_configured(s, sb, monkeypatch):
    a, _, _ = sb
    secret = "legacy-shared-secret-legacy-shared-secret"
    claims = {"sub": "legacy-1", "aud": "authenticated", "iss": ISS, "exp": int(_time.time()) + 60}
    monkeypatch.setattr(settings, "supabase_jwt_secret", secret)
    assert a.authenticate(s, jwt.encode(claims, secret, algorithm="HS256")).learner_id == "legacy-1"
    with pytest.raises(impl.AuthError):
        a.authenticate(s, jwt.encode(claims, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256"))


def test_supabase_key_server_outage_is_not_reported_as_a_bad_token(s, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", SB_URL)

    class Down:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientConnectionError("network down")
    priv, _ = _ec_key("k1")
    a = impl.SupabaseAuth(jwks_client=Down())
    with pytest.raises(impl.AuthUnavailable):
        a.authenticate(s, _token(priv))


def test_supabase_default_client_points_at_the_projects_jwks_and_caches(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", SB_URL + "/")
    a = impl.SupabaseAuth()
    assert a.jwks_url == ISS + "/.well-known/jwks.json" == a._jwks.uri
    assert a._jwks.jwk_set_cache is not None


def test_supabase_odd_metadata_does_not_break_first_sight(s, sb):
    a, priv, _ = sb
    a.authenticate(s, _token(priv, sub="u2", user_metadata={"name": None, "age": "abc", "language": "klingon"}))
    lr = s.get(Learner, "u2")
    # an unusable age is never trusted: fail-safe placeholder, flagged unconfirmed, so the learner counts as a minor until they say
    assert (lr.name, lr.age, lr.language_pref) == ("asha", 17, "english") and lr.settings["age_confirmed"] is False


def test_api_returns_401_for_bad_tokens_and_503_when_keys_are_unreachable(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    monkeypatch.setattr(settings, "supabase_url", SB_URL)
    adapters.reset()
    dbm.configure("sqlite://")
    from app.main import create_app
    c = TestClient(create_app())
    priv, jwk = _ec_key("k1")
    prov = adapters.auth()
    prov._jwks = StaticJWKS([jwk])
    assert c.get("/api/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    ok = c.get("/api/me", headers={"Authorization": "Bearer " + _token(priv)})
    assert ok.status_code == 200 and ok.json()["name"] == "Asha"

    class Down:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientConnectionError("down")
    prov._jwks = Down()
    assert c.get("/api/me", headers={"Authorization": "Bearer " + _token(priv)}).status_code == 503
    assert c.post("/api/auth/dev-login", json={"name": "x", "age": 20}).status_code == 400  # no mock login in this mode
    monkeypatch.setattr(settings, "auth_mode", "mock")
    adapters.reset()


def test_real_switch_without_configuration_fails_loudly(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", None)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        impl.SupabaseAuth()
    monkeypatch.setattr(settings, "auth_mode", "supabase")
    adapters.reset()
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):   # the API would refuse to start - no silent fallback to mock
        adapters.auth()
    with pytest.raises(RuntimeError):
        adapters.describe()
    monkeypatch.setattr(settings, "auth_mode", "bogus")
    adapters.reset()
    with pytest.raises(RuntimeError):
        adapters.auth()
    monkeypatch.setattr(settings, "auth_mode", "mock")
    adapters.reset()


def test_responder_is_mock_only_while_mentors_are_mock(monkeypatch):
    monkeypatch.setattr(settings, "mentors_mode", "mock")
    adapters.reset()
    assert adapters.responder().is_mock
    monkeypatch.setattr(settings, "mentors_mode", "db")
    adapters.reset()
    assert adapters.responder().name == "none"
    monkeypatch.setattr(settings, "mentors_mode", "mock")
    adapters.reset()
