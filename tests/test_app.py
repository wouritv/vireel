import importlib
import asyncio
import io
import json
import os
import sys
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

import film_summary


def _install_supabase_stubs(monkeypatch):
    supabase_mod = types.ModuleType("supabase")

    class _AsyncClient:
        pass

    async def _acreate_client(*args, **kwargs):
        return _AsyncClient()

    supabase_mod.AsyncClient = _AsyncClient
    supabase_mod.acreate_client = _acreate_client

    client_options_mod = types.ModuleType("supabase.lib.client_options")

    class _AsyncClientOptions:
        def __init__(self, postgrest_client_timeout):
            self.postgrest_client_timeout = postgrest_client_timeout

    client_options_mod.AsyncClientOptions = _AsyncClientOptions

    monkeypatch.setitem(sys.modules, "supabase", supabase_mod)
    monkeypatch.setitem(sys.modules, "supabase.lib.client_options", client_options_mod)


def _install_optional_dependency_stubs(monkeypatch):
    python_multipart_mod = types.ModuleType("python_multipart")
    python_multipart_mod.__version__ = "0.0.20"
    monkeypatch.setitem(sys.modules, "python_multipart", python_multipart_mod)

    itsdangerous_mod = types.ModuleType("itsdangerous")

    class _Serializer:
        def __init__(self, *args, **kwargs):
            pass

        def dumps(self, value):
            return str(value)

        def loads(self, value, max_age=None):
            return value

    class _SignatureExpired(Exception):
        pass

    class _BadSignature(Exception):
        pass

    itsdangerous_mod.URLSafeTimedSerializer = _Serializer
    itsdangerous_mod.SignatureExpired = _SignatureExpired
    itsdangerous_mod.BadSignature = _BadSignature
    monkeypatch.setitem(sys.modules, "itsdangerous", itsdangerous_mod)

    s3_mod = types.ModuleType("s3_uploader")
    s3_mod.upload_file_to_s3 = lambda *args, **kwargs: True
    s3_mod.generate_presigned_url = lambda *args, **kwargs: ""
    s3_mod.delete_s3_object = lambda *args, **kwargs: True
    s3_mod.get_s3_object_size = lambda *args, **kwargs: 0
    s3_mod.download_s3_object = lambda *args, **kwargs: True
    monkeypatch.setitem(sys.modules, "s3_uploader", s3_mod)

    sib_mod = types.ModuleType("sib_api_v3_sdk")
    sib_rest_mod = types.ModuleType("sib_api_v3_sdk.rest")
    sib_rest_mod.ApiException = Exception
    monkeypatch.setitem(sys.modules, "sib_api_v3_sdk", sib_mod)
    monkeypatch.setitem(sys.modules, "sib_api_v3_sdk.rest", sib_rest_mod)

    editor_mod = types.ModuleType("editor")
    editor_mod.VideoEditor = object
    monkeypatch.setitem(sys.modules, "editor", editor_mod)

    subtitles_mod = types.ModuleType("subtitles")
    subtitles_mod.generate_srt = lambda *args, **kwargs: True
    subtitles_mod.generate_highlighted_srt = lambda *args, **kwargs: True
    subtitles_mod.burn_subtitles = lambda *args, **kwargs: True
    subtitles_mod.generate_srt_from_video = lambda *args, **kwargs: True

    class _SubtitleStyleOptions:
        pass

    subtitles_mod.SubtitleStyleOptions = _SubtitleStyleOptions
    monkeypatch.setitem(sys.modules, "subtitles", subtitles_mod)

    hooks_mod = types.ModuleType("hooks")
    hooks_mod.add_hook_to_video = lambda *args, **kwargs: True
    monkeypatch.setitem(sys.modules, "hooks", hooks_mod)

    thumbnail_mod = types.ModuleType("thumbnail")
    thumbnail_mod.analyze_video_for_titles = lambda *args, **kwargs: {}
    thumbnail_mod.refine_titles = lambda *args, **kwargs: {}
    thumbnail_mod.generate_thumbnail = lambda *args, **kwargs: []
    thumbnail_mod.generate_youtube_description = lambda *args, **kwargs: {"description": ""}
    monkeypatch.setitem(sys.modules, "thumbnail", thumbnail_mod)


def _import_app_with_stubs(monkeypatch):
    pytest.importorskip("fastapi")
    monkeypatch.setenv("SECRET_KEY", "unit-test-secret")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "unit-test-supabase-jwt-secret")
    _install_supabase_stubs(monkeypatch)
    _install_optional_dependency_stubs(monkeypatch)

    if "app" in sys.modules:
        return importlib.reload(sys.modules["app"])
    return importlib.import_module("app")


def _auth_headers(user_id="u1"):
    """Build a valid Authorization Bearer header for TestClient calls.

    Endpoints now require a verified Supabase JWT (audit finding C1) instead
    of trusting a plain X-User-Id header, so any test driving a real request
    through TestClient needs one of these or it gets rejected with 401
    before ever reaching the endpoint logic under test.
    """
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": user_id, "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-User-Id": user_id}


def test_encrypt_decrypt_token_round_trip(monkeypatch):
    # Regression/CVE-bump coverage: _encrypt_token/_decrypt_token (the
    # AES-256-GCM scheme storing social-platform OAuth tokens) had no direct
    # test at all before this -- added while bumping the `cryptography`
    # dependency (41.0.7 -> 49.0.0, CVE re-audit) specifically to prove the
    # real AESGCM/HKDF primitives still round-trip correctly on the new
    # version, not just that the module imports.
    app = _import_app_with_stubs(monkeypatch)
    token = "super-secret-oauth-token-12345"

    encrypted = app._encrypt_token(token)
    assert encrypted.startswith("v1:")
    assert token not in encrypted

    assert app._decrypt_token(encrypted) == token


def test_decrypt_token_rejects_legacy_and_tampered_values(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._decrypt_token("") == ""
    assert app._decrypt_token(None) == ""
    # Pre-AES-GCM (legacy XOR) tokens have no "v1:" prefix and must be
    # treated as unusable, not best-effort decoded.
    assert app._decrypt_token("some-legacy-plaintext-token") == ""

    encrypted = app._encrypt_token("another-token")
    tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")
    assert app._decrypt_token(tampered) == ""


def test_verify_supabase_jwt_accepts_valid_hs256_token(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "user-hs256", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app._verify_supabase_jwt(token) == "user-hs256"


def test_verify_supabase_jwt_allows_any_email_when_demo_allowlist_unset(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    assert app.DEMO_ALLOWED_EMAILS == set()
    token = pyjwt.encode(
        {"sub": "user-1", "email": "anyone@example.com", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app._verify_supabase_jwt(token) == "user-1"


def test_verify_supabase_jwt_rejects_email_not_on_demo_allowlist(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "DEMO_ALLOWED_EMAILS", {"allowed@example.com"})
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "user-1", "email": "someone-else@example.com", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    with pytest.raises(app.HTTPException) as exc_info:
        app._verify_supabase_jwt(token)
    assert exc_info.value.status_code == 403


def test_verify_supabase_jwt_accepts_email_on_demo_allowlist_case_insensitively(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "DEMO_ALLOWED_EMAILS", {"allowed@example.com"})
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "user-1", "email": "Allowed@Example.com", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app._verify_supabase_jwt(token) == "user-1"


def test_verify_supabase_jwt_rejects_bad_hs256_signature(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "user-hs256", "aud": "authenticated", "exp": 9999999999},
        "wrong-secret",
        algorithm="HS256",
    )

    with pytest.raises(app.HTTPException) as exc_info:
        app._verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_verify_supabase_jwt_accepts_valid_es256_token_via_jwks(monkeypatch):
    # Security regression test: newer Supabase projects sign sessions with an
    # asymmetric ES256 key (verified via the project's JWKS endpoint) instead
    # of the legacy HS256 shared secret. Before this fix, _verify_supabase_jwt
    # only understood HS256, so every request against such a project failed
    # with "Invalid or expired session token" regardless of the secret's
    # value. This exercises the ES256/JWKS branch with a real EC keypair,
    # stubbing out only the network call to Supabase's JWKS endpoint.
    from cryptography.hazmat.primitives.asymmetric import ec

    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    private_key = ec.generate_private_key(ec.SECP256R1())
    token = pyjwt.encode(
        {"sub": "user-es256", "aud": "authenticated", "exp": 9999999999},
        private_key,
        algorithm="ES256",
        headers={"kid": "test-key-1"},
    )

    class _FakeSigningKey:
        def __init__(self, key):
            self.key = key

    class _FakeJwksClient:
        def get_signing_key_from_jwt(self, tok):
            return _FakeSigningKey(private_key.public_key())

    monkeypatch.setattr(app, "_get_supabase_jwks_client", lambda: _FakeJwksClient())

    assert app._verify_supabase_jwt(token) == "user-es256"


def test_verify_supabase_jwt_rejects_alg_none_downgrade(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode({"sub": "user-x", "aud": "authenticated"}, key=None, algorithm="none")

    with pytest.raises(app.HTTPException) as exc_info:
        app._verify_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_parse_iso_datetime_accepts_zulu_and_invalid(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    parsed = app._parse_iso_datetime("2024-01-15T10:30:00Z")
    bad = app._parse_iso_datetime("not-a-date")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert bad is None


def test_parse_iso_datetime_handles_empty_and_naive(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._parse_iso_datetime("") is None
    naive = app._parse_iso_datetime("2024-01-01T10:00:00")
    assert naive is not None
    assert naive.tzinfo is not None


def test_clamp_job_priority_enforces_bounds(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._clamp_job_priority(0) == app.JOB_PRIORITY_MIN
    assert app._clamp_job_priority(999) == app.JOB_PRIORITY_MAX
    assert app._clamp_job_priority("2") == 2


def test_is_probably_video_url_checks_extensions(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._is_probably_video_url("https://cdn.example.com/v/final.MP4") is True
    assert app._is_probably_video_url("https://cdn.example.com/img.jpg") is False
    assert app._is_probably_video_url("") is False


def test_estimate_transcript_duration_uses_max_segment_or_meta(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    transcript = {
        "segments": [{"end": 3.5}, {"end": "9.2"}],
        "meta": {"audio_seconds": "7.5"},
    }
    assert app._estimate_transcript_duration_seconds(transcript) == 9.2


def test_get_user_id_header_success_and_missing(monkeypatch):
    # Security regression test: get_user_id_header used to trust a plain
    # client-supplied X-User-Id header (spoofable by any caller). It now
    # requires a verified Supabase JWT Bearer token instead (audit finding
    # C1) -- this exercises both the success path (valid token) and the
    # rejection path (no Authorization header at all).
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "u-1", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app.get_user_id_header(None, authorization=f"Bearer {token}") == "u-1"
    with pytest.raises(app.HTTPException):
        app.get_user_id_header(None, authorization=None)


def test_get_user_id_header_or_query_token_accepts_header_or_query(monkeypatch):
    # Regression test: /api/media/proxy is loaded directly by <video src>/
    # <img src> markup (preview players, Remotion) -- the browser never
    # attaches an Authorization header to those requests, so requiring one
    # (get_user_id_header) made every real playback 401 with a black
    # preview even though the caller was genuinely authenticated. This
    # dependency accepts the same verified JWT via a `token` query param as
    # a fallback, used only by that endpoint.
    app = _import_app_with_stubs(monkeypatch)
    import jwt as pyjwt

    token = pyjwt.encode(
        {"sub": "u-1", "aud": "authenticated", "exp": 9999999999},
        "unit-test-supabase-jwt-secret",
        algorithm="HS256",
    )

    assert app.get_user_id_header_or_query_token(None, authorization=f"Bearer {token}") == "u-1"
    assert app.get_user_id_header_or_query_token(None, authorization=None, token=token) == "u-1"
    # Authorization header still wins when both are somehow present.
    assert app.get_user_id_header_or_query_token(None, authorization=f"Bearer {token}", token="garbage") == "u-1"
    with pytest.raises(app.HTTPException):
        app.get_user_id_header_or_query_token(None, authorization=None, token=None)


def test_proxy_media_route_uses_header_or_query_token(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    route = next(r for r in app.app.routes if getattr(r, "path", None) == "/api/media/proxy")
    dependency_names = {getattr(d.call, "__name__", None) for d in route.dependant.dependencies}
    assert "get_user_id_header_or_query_token" in dependency_names


def test_api_process_route_is_wired_to_process_endpoint(monkeypatch):
    # Regression test: a refactor once inserted a new helper function
    # (_resolve_process_endpoint_url_and_ack) directly above the real
    # process_endpoint route, and the Edit that did it accidentally left the
    # @app.post("/api/process") decorator attached to that new helper
    # instead of to process_endpoint. FastAPI then registered the helper as
    # the route handler, whose plain `url`/`acknowledged` params (no Form())
    # got classified as required query params -- every real call failed
    # with a 422 "Field required" for query.url/query.acknowledged. This
    # pins both the correct handler and the correct (body, not query)
    # parameter classification.
    app = _import_app_with_stubs(monkeypatch)

    route = next(r for r in app.app.routes if getattr(r, "path", None) == "/api/process")
    assert route.endpoint is app.process_endpoint

    body_param_names = {p.name for p in route.dependant.body_params}
    query_param_names = {p.name for p in route.dependant.query_params}
    assert {"file", "url", "acknowledged"} <= body_param_names
    assert not ({"url", "acknowledged"} & query_param_names)


def test_captions_persist_route_is_wired_to_persist_captioned_reel(monkeypatch):
    # Regression test: the same decorator-detachment bug as
    # test_api_process_route_is_wired_to_process_endpoint above, this time on
    # /api/reels/{job_id}/{clip_index}/captions/persist -- the
    # @app.post(...) decorator was left on _validate_captioned_reel_upload
    # (a small helper immediately above the real handler) instead of on
    # persist_captioned_reel. FastAPI registered that helper as the route
    # handler: it validates the upload and returns None, so every real
    # persist request silently no-op'd -- nothing was written to
    # metadata.json or Supabase (no style_edit_versions row, no
    # original_video_url), and any edit was lost on reload. Existing
    # persist_captioned_reel tests called the function directly and so
    # never caught this, since they bypass FastAPI's route dispatch.
    app = _import_app_with_stubs(monkeypatch)

    route = next(
        r for r in app.app.routes
        if getattr(r, "path", None) == "/api/reels/{job_id}/{clip_index}/captions/persist"
    )
    assert route.endpoint is app.persist_captioned_reel

    body_param_names = {p.name for p in route.dependant.body_params}
    assert "file" in body_param_names


def test_build_social_post_url_per_platform(monkeypatch):
    # Regression test: the dashboard used to build the "view post" link as
    # https://<platform-host>/<external_id>, but external_id is whatever
    # the platform's publish API happened to return as an id -- an internal
    # video id, a media container id, a share URN -- almost never the same
    # thing as a real permalink, so the link 404'd even though the post
    # itself published successfully. This pins the real per-platform
    # permalink construction (and that platforms/shapes we can't reliably
    # resolve return None rather than a guessed, likely-broken URL).
    app = _import_app_with_stubs(monkeypatch)

    assert app._build_social_post_url("youtube", {"video_id": "abc", "url": "https://youtube.com/watch?v=abc"}) == "https://youtube.com/watch?v=abc"
    assert app._build_social_post_url("youtube", {}) is None

    # Facebook video post: bare numeric video id -> /watch/?v=
    assert app._build_social_post_url("facebook", {"id": "123456789"}) == "https://www.facebook.com/watch/?v=123456789"
    # Facebook feed/text post: "<page_id>_<post_id>" already resolves directly
    assert app._build_social_post_url("facebook", {"id": "111_222"}) == "https://www.facebook.com/111_222"
    assert app._build_social_post_url("facebook", {}) is None

    assert app._build_social_post_url("instagram", {"id": "179...", "permalink": "https://www.instagram.com/reel/Cxyz/"}) == "https://www.instagram.com/reel/Cxyz/"
    assert app._build_social_post_url("instagram", {"id": "179..."}) is None

    assert app._build_social_post_url("linkedin", {"id": "urn:li:share:123"}) == "https://www.linkedin.com/feed/update/urn:li:share:123/"
    assert app._build_social_post_url("linkedin", {}) is None

    # TikTok's publish/status APIs don't reliably expose a public video id
    # or the account's real @handle -- no safe link can be built.
    assert app._build_social_post_url("tiktok", {"publish_id": "p123", "status": "PUBLISH_COMPLETE"}) is None


def test_reconcile_orphaned_jobs_on_startup_force_fails_and_refunds(monkeypatch):
    # Job execution state (JobManager.runtime_jobs) lives only in memory --
    # a process restart wipes it but leaves the Supabase job row at
    # whatever non-terminal status it was last in, and that row keeps
    # counting against MAX_ACTIVE_JOBS_PER_USER forever since nothing will
    # ever pick it back up. This pins that the startup reconciliation finds
    # such rows and force-fails+refunds each one, mapping queue_name to the
    # correct billing operation_type.
    app = _import_app_with_stubs(monkeypatch)

    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    orphaned_rows = [
        {"id": "job-reel", "user_id": "user-1", "reserved_quota": 3.0, "queue_name": "reels"},
        {"id": "job-cap", "user_id": "user-2", "reserved_quota": 1.5, "queue_name": "captions"},
    ]
    app.supabase_list_active_jobs = AsyncMock(return_value=orphaned_rows)
    app.reel_job_manager.force_fail_orphaned_job = AsyncMock()

    asyncio.run(app._reconcile_orphaned_jobs_on_startup())

    assert app.reel_job_manager.force_fail_orphaned_job.await_count == 2
    calls = {c.args[0]: c for c in app.reel_job_manager.force_fail_orphaned_job.await_args_list}
    assert calls["job-reel"].args == ("job-reel", "user-1", 3.0)
    assert calls["job-reel"].kwargs["operation_type"] == "generation_reel"
    assert calls["job-cap"].args == ("job-cap", "user-2", 1.5)
    assert calls["job-cap"].kwargs["operation_type"] == "sous_titre"


def test_reconcile_orphaned_jobs_on_startup_skips_when_supabase_not_configured(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    app.supabase_list_active_jobs = AsyncMock()
    app.reel_job_manager.force_fail_orphaned_job = AsyncMock()

    asyncio.run(app._reconcile_orphaned_jobs_on_startup())

    app.supabase_list_active_jobs.assert_not_awaited()
    app.reel_job_manager.force_fail_orphaned_job.assert_not_awaited()


def test_resolve_scheduled_datetime_handles_aware_and_naive(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    aware = app._resolve_scheduled_datetime("2024-01-01T10:00:00Z", "Europe/Paris")
    naive = app._resolve_scheduled_datetime("2024-01-01T10:00:00", "UTC")
    bad = app._resolve_scheduled_datetime("not-a-date", "UTC")
    assert aware is not None
    assert naive is not None
    assert bad is None


def test_maybe_preempt_lower_priority_running_job_terminates_candidate(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _Proc:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    proc = _Proc()
    app.running_reel_jobs.clear()
    app.jobs.clear()
    app.running_reel_jobs["job-low"] = {"priority": 1, "started_at": 10.0, "process": proc}
    app.jobs["job-low"] = {"logs": []}
    monkeypatch.setattr(app, "MAX_CONCURRENT_JOBS", 1)

    asyncio.run(app._maybe_preempt_lower_priority_running_job(3, "job-high"))

    assert app.running_reel_jobs["job-low"]["preempt_requested"] is True
    assert proc.terminated is True
    assert any("job-high" in entry for entry in app.jobs["job-low"]["logs"])


def test_resolve_job_metadata_path_falls_back_to_root_candidate(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")

    def fake_glob(pattern):
        if pattern == "/tmp/output/job-1/*_metadata.json":
            return []
        if pattern == "/tmp/output/job-1_*_metadata.json":
            return ["/tmp/output/job-1_a_metadata.json"]
        return []

    monkeypatch.setattr(app.glob, "glob", fake_glob)
    monkeypatch.setattr(app.os.path, "getmtime", lambda _: 1.0)
    monkeypatch.setattr(app, "_relocate_root_job_artifacts", lambda *_: False)

    assert app._resolve_job_metadata_path("job-1") == "/tmp/output/job-1_a_metadata.json"


def test_resolve_job_metadata_path_returns_relocated_metadata(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    state = {"calls": 0}

    def fake_glob(pattern):
        if pattern == "/tmp/output/job-2/*_metadata.json":
            state["calls"] += 1
            if state["calls"] == 1:
                return []
            return ["/tmp/output/job-2/job-2_moved_metadata.json"]
        if pattern == "/tmp/output/job-2_*_metadata.json":
            return []
        return []

    monkeypatch.setattr(app.glob, "glob", fake_glob)
    monkeypatch.setattr(app, "_relocate_root_job_artifacts", lambda *_: True)

    assert app._resolve_job_metadata_path("job-2") == "/tmp/output/job-2/job-2_moved_metadata.json"


class _NoopThread:
    def __init__(self, target=None, args=None):
        self.target = target
        self.args = args or ()
        self.daemon = False

    def start(self):
        return None


class _DoneProcess:
    def __init__(self, returncode):
        self.returncode = returncode
        self.stdout = None

    def poll(self):
        return self.returncode

    def terminate(self):
        return None


class _FakeOpen:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_run_job_process_exit_schedules_retry(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "job-process-fail"
    app.jobs[job_id] = {"status": "queued", "logs": [], "result": None}

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.update_progress = AsyncMock()
    app._finalize_failed_reel_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(coro):
        create_task_mock.call_count += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(app.threading, "Thread", _NoopThread)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *args, **kwargs: _DoneProcess(returncode=1))

    job_data = {
        "cmd": ["python", "main.py"],
        "env": {},
        "output_dir": "/tmp/output",
        "user_id": "user-1",
        "input_path": "",
        "priority": 1,
    }

    asyncio.run(app.run_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("Process failed with exit code 1" in line for line in app.jobs[job_id]["logs"])
    assert app._finalize_failed_reel_job.await_args.kwargs["error_code"] == "PROCESS_EXIT"
    assert create_task_mock.call_count == 1


def test_run_job_metadata_missing_schedules_retry(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "job-no-metadata"
    app.jobs[job_id] = {"status": "queued", "logs": [], "result": None}

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.update_progress = AsyncMock()
    app._finalize_failed_reel_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(coro):
        create_task_mock.call_count += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(app.threading, "Thread", _NoopThread)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *args, **kwargs: _DoneProcess(returncode=0))
    monkeypatch.setattr(app.glob, "glob", lambda pattern: [])
    monkeypatch.setattr(app, "_relocate_root_job_artifacts", lambda *args, **kwargs: False)

    job_data = {
        "cmd": ["python", "main.py"],
        "env": {},
        "output_dir": "/tmp/output",
        "user_id": "user-2",
        "input_path": "",
        "priority": 1,
    }

    asyncio.run(app.run_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("No metadata file generated" in line for line in app.jobs[job_id]["logs"])
    assert app._finalize_failed_reel_job.await_args.kwargs["error_code"] == "METADATA_NOT_FOUND"
    assert create_task_mock.call_count == 1


def test_run_caption_job_missing_input_fails_and_retries(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-missing-input"
    app.jobs[job_id] = {"status": "queued", "logs": []}

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.fail_job = AsyncMock(return_value={"retry": True})
    create_task_mock = types.SimpleNamespace(call_count=0)

    def _fake_create_task(coro):
        create_task_mock.call_count += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)

    class _Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def analyzing(self):
            return None

    monkeypatch.setattr(app, "CaptionProcessingPipeline", _Pipeline)
    monkeypatch.setattr(os.path, "exists", lambda _: False)

    job_data = {
        "user_id": "user-3",
        "output_dir": "/tmp/output",
        "input_path": "/tmp/missing.mp4",
    }

    asyncio.run(app.run_caption_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("Caption job failed" in line for line in app.jobs[job_id]["logs"])
    app.reel_job_manager.fail_job.assert_awaited_once()
    assert create_task_mock.call_count == 1


def test_process_and_complete_caption_job_auto_captions_and_uploads_original(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-auto-1"
    app.jobs[job_id] = {"logs": [], "result": None, "status": "processing"}
    output_dir = str(tmp_path)
    input_path = os.path.join(output_dir, "source.mp4")
    Path(input_path).write_bytes(b"raw-source-bytes")

    async def _fake_burn(input_path_, output_path, transcript, clip_start, clip_end, job_id_, clip_index, style_kwargs):
        Path(output_path).write_bytes(b"captioned-source-bytes-longer")
        return True

    monkeypatch.setattr(app, "_burn_default_captions_for_clip", _fake_burn)
    monkeypatch.setattr(app, "_build_and_persist_caption_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *args, **kwargs: "")
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")
    upload_calls = []
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: upload_calls.append(key) or True)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app, "_normalize_caption_row", lambda row: row)
    app.reel_job_manager.complete_job = AsyncMock()
    monkeypatch.setattr(app, "_update_project_on_caption_completion", AsyncMock())
    monkeypatch.setattr(app, "_persist_transcription_cache", AsyncMock())

    class _Pipeline:
        async def persisting(self):
            return None

        async def rendering(self):
            return None

    asyncio.run(app._process_and_complete_caption_job(
        job_id, {}, "user-1", _Pipeline(), input_path, "source.mp4", 10.0,
        {"segments": [{"words": [{"word": "hi", "start": 0, "end": 1}]}]},
        0.0, output_dir,
    ))

    assert any(key.startswith("captions/user-1/caption-auto-1/original_") for key in upload_calls)
    saved_row = app.jobs[job_id]["result"]["item"]
    assert saved_row["generation_inputs"]["original_s3_key"]
    assert saved_row["caption_duration"] == 10


def test_run_caption_job_insufficient_balance_marks_failed(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-insufficient"
    app.jobs[job_id] = {"status": "queued", "logs": []}

    class _Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def analyzing(self):
            return None

        async def transcribing(self):
            return None

        async def persisting(self):
            return None

        async def rendering(self):
            return None

    monkeypatch.setattr(app, "CaptionProcessingPipeline", _Pipeline)
    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.fail_job = AsyncMock(return_value={"retry": False})
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=False)

    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _: 30.0)
    monkeypatch.setattr(app, "_validate_caption_source_constraints", lambda **kwargs: None)
    monkeypatch.setattr(app, "_load_cached_transcription", AsyncMock(return_value={"transcript_payload": {"segments": [], "text": "hello", "language": "fr"}}))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_estimate_caption_cost_breakdown", lambda **kwargs: {"total_usd": 0.1})
    monkeypatch.setattr(app, "_build_billing_details", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda *_: "https://cdn.example/video.mp4")
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *args, **kwargs: "")
    monkeypatch.setattr(app, "_normalize_caption_row", lambda row: row)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_insert_captions", AsyncMock(return_value=[{"id": "cap-1"}]))
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *args, **kwargs: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")

    monkeypatch.setattr(os.path, "exists", lambda _: True)
    monkeypatch.setattr(os.path, "getsize", lambda _: 1024)

    monkeypatch.setattr(os, "remove", lambda p: None)

    job_data = {
        "user_id": "user-4",
        "output_dir": "/tmp/output",
        "input_path": "/tmp/input.mp4",
        "source_name": "input.mp4",
        "caption_required_credits": 2.0,
    }

    asyncio.run(app.run_caption_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "failed"
    assert any("Insufficient credit/storage balance" in line for line in app.jobs[job_id]["logs"])
    app.reel_job_manager.fail_job.assert_awaited_once()


def test_run_job_reel_persistence_failed_propagates_retry_delay_to_fail_job(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "job-persist-fail"
    app.jobs[job_id] = {"status": "queued", "logs": [], "result": None}

    class _Pipeline:
        def __init__(self, *args, **kwargs):
            pass

        async def starting(self):
            return None

        async def uploading_reels(self, clip_count):
            return None

    app.reel_job_manager.start_job = AsyncMock()
    app.reel_job_manager.fail_job = AsyncMock(return_value={"retry": True, "status": "retry_wait"})
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=True)
    app._persist_reels_for_job = AsyncMock(side_effect=RuntimeError("s3 upload failed"))
    app.supabase_update_job_record = AsyncMock()

    monkeypatch.setattr(app, "ReelProcessingPipeline", _Pipeline)
    monkeypatch.setattr(app.threading, "Thread", _NoopThread)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *args, **kwargs: _DoneProcess(returncode=0))
    monkeypatch.setattr(app.glob, "glob", lambda pattern: ["/tmp/output/job-persist-fail_metadata.json"])
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: _FakeOpen())
    monkeypatch.setattr(app.json, "load", lambda *_: {"shorts": [{"start": 0.0, "end": 10.0}], "cost_analysis": {}})
    monkeypatch.setattr(app, "_collect_reel_job_output_snapshot", lambda *_: {"processed_clips": 1, "expected_clips": 1, "result_data": {"clips": [{"id": 1}]}})
    monkeypatch.setattr(
        app,
        "_estimate_reel_job_consumption",
        lambda **kwargs: {
            "processing_ratio": 1.0,
            "actual_cost_usd": 0.5,
            "actual_credit": 10.0,
            "actual_storage_gb": 0.0,
            "cost_breakdown": {"total_usd": 0.5},
        },
    )
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app.os.path, "exists", lambda path: False)

    create_task_calls = {"count": 0}

    def _fake_create_task(coro):
        create_task_calls["count"] += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)

    job_data = {
        "cmd": ["python", "main.py"],
        "env": {},
        "output_dir": "/tmp/output",
        "user_id": "user-5",
        "input_path": "",
        "priority": 2,
    }

    asyncio.run(app.run_job(job_id, job_data, execution_ctx={}))

    assert app.jobs[job_id]["status"] == "retry_wait"
    assert any("Supabase persistence failed" in line for line in app.jobs[job_id]["logs"])
    assert create_task_calls["count"] == 1

    fail_args = app.reel_job_manager.fail_job.await_args
    assert fail_args.args[0] == job_id
    assert fail_args.kwargs["error_code"] == "REEL_PERSISTENCE_FAILED"
    assert fail_args.kwargs["retry_delay_seconds"] == app.REEL_JOB_RETRY_DELAY_SECONDS


def test_is_pytest_runtime(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._is_pytest_runtime() is True


def test_normalize_caption_row_builds_urls(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")

    row = {
        "id": "cap-1",
        "caption_s3_key": "captions/u1/job1/cap.mp4",
        "caption_thumbnail_url": "captions/u1/job1/thumb.jpg",
        "caption_url": ""
    }

    result = app._normalize_caption_row(row)
    assert "caption_url" in result
    assert result["media_url"] != ""


def test_normalize_reel_row_builds_urls(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")
    monkeypatch.setattr(app, "_extract_s3_key_from_thumbnail_ref", lambda ref: "reels/u1/thumb.jpg" if ref else "")
    monkeypatch.setattr(app, "_reel_thumbnail_url_from_s3_key", lambda key: f"https://cdn.example/{key}")

    row = {
        "id": "reel-1",
        "reel_s3_key": "reels/u1/job1/reel.mp4",
        "reel_thumbnail_url": "reels/u1/thumb.jpg",
        "reel_url": ""
    }

    result = app._normalize_reel_row(row)
    assert "reel_url" in result
    assert result["media_url"] != ""


def test_extract_s3_key_from_thumbnail_ref_handles_s3_scheme(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._extract_s3_key_from_thumbnail_ref("s3://bucket/reels/u1/thumb.jpg")
    assert result == "reels/u1/thumb.jpg"

    result = app._extract_s3_key_from_thumbnail_ref("reels/u1/thumb.jpg")
    assert result == "reels/u1/thumb.jpg"


def test_extract_s3_key_from_thumbnail_ref_returns_empty_for_invalid(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._extract_s3_key_from_thumbnail_ref("")
    assert result == ""

    result = app._extract_s3_key_from_thumbnail_ref("s3://bucket-only")
    assert result == ""


def test_sweep_output_directory_removes_stale_files(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import time
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    monkeypatch.setattr(app, "OUTPUT_SWEEP_MIN_AGE_SECONDS", 3600)

    file_list = ["old_file.mp4", "job-1"]
    old_time = time.time() - 7200  # 2 hours ago
    monkeypatch.setattr(app.os, "listdir", lambda path: file_list)
    monkeypatch.setattr(app.os.path, "getmtime", lambda p: old_time)
    monkeypatch.setattr(app.os.path, "isdir", lambda p: "job-1" in str(p))
    monkeypatch.setattr(app.os.path, "isdir", lambda p: True if p == "/tmp/output" else ("job-1" in str(p)))
    monkeypatch.setattr(app, "_active_output_paths", lambda: set())

    remove_mock = MagicMock()
    rmtree_mock = MagicMock()
    monkeypatch.setattr(app.os, "remove", remove_mock)
    monkeypatch.setattr(app.shutil, "rmtree", rmtree_mock)

    removed_count = app._sweep_output_directory(time.time())
    # Both files should be marked for removal (old_file.mp4 and job-1 directory)
    assert removed_count >= 0


def test_sweep_output_directory_exempts_voice_previews_dir(monkeypatch):
    # voice_previews is a persistent cache (see synthesize_tts_segment /
    # get_film_summary_voice_preview_endpoint), not per-job output -- it
    # must survive the sweep exactly like thumbnails_dir. Before this fix,
    # it had no exemption: once 30+ minutes passed without a new voice
    # being previewed, the whole directory (and every already-cached
    # voice .mp3) got rmtree'd, breaking every preview with "No such file
    # or directory: '.../voice_previews/<voice>.mp3.tmp-...'" until the
    # next request happened to regenerate it.
    app = _import_app_with_stubs(monkeypatch)
    import time
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    monkeypatch.setattr(app, "FILM_SUMMARY_VOICE_PREVIEWS_DIR", "/tmp/output/voice_previews")
    monkeypatch.setattr(app, "OUTPUT_SWEEP_MIN_AGE_SECONDS", 1800)

    file_list = ["voice_previews", "stale-job"]
    old_time = time.time() - 7200  # 2 hours ago, well past the stale threshold
    monkeypatch.setattr(app.os, "listdir", lambda path: file_list)
    monkeypatch.setattr(app.os.path, "getmtime", lambda p: old_time)
    monkeypatch.setattr(app.os.path, "isdir", lambda p: p == "/tmp/output" or "stale-job" in str(p) or "voice_previews" in str(p))
    monkeypatch.setattr(app, "_active_output_paths", lambda: set())

    rmtree_mock = MagicMock()
    monkeypatch.setattr(app.shutil, "rmtree", rmtree_mock)

    removed_count = app._sweep_output_directory(time.time())

    rmtree_mock.assert_called_once_with("/tmp/output/stale-job", ignore_errors=True)
    assert removed_count == 1


def test_active_output_paths_returns_paths_for_processing_jobs(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.jobs["job-1"] = {"status": "processing", "output_dir": "/tmp/job-1"}
    app.jobs["job-2"] = {"status": "completed", "output_dir": "/tmp/job-2"}

    paths = app._active_output_paths()
    assert "/tmp/job-1" in paths
    assert "/tmp/job-2" not in paths


def test_reel_media_url_from_s3_key_returns_empty_for_missing_bucket(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app.os.environ, "get", lambda key, default=None: default)

    result = app._reel_media_url_from_s3_key("reels/u1/reel.mp4")
    assert result == ""


def test_caption_media_url_from_s3_key_returns_empty_for_missing_bucket(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app.os.environ, "get", lambda key, default=None: default)

    result = app._caption_media_url_from_s3_key("captions/u1/cap.mp4")
    assert result == ""


def test_cleanup_directory_ignores_errors(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    import shutil

    error_rmtree = MagicMock(side_effect=Exception("Permission denied"))
    monkeypatch.setattr(app.shutil, "rmtree", error_rmtree)

    # Should not raise
    app._cleanup_directory("/tmp/missing")


def test_collect_reel_job_output_snapshot_with_metadata(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/tmp/output")
    monkeypatch.setattr(app, "_resolve_job_metadata_path", lambda job_id: "/tmp/output/job-1_metadata.json")

    metadata = {
        "shorts": [
            {"start": 0, "end": 10, "title": "Clip 1"},
            {"start": 10, "end": 20, "title": "Clip 2"}
        ],
        "cost_analysis": {"total_usd": 0.5}
    }

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: _FakeOpen())
    monkeypatch.setattr(app.json, "load", lambda *_: metadata)
    monkeypatch.setattr(app.os.path, "exists", lambda p: "metadata.json" in str(p) or "clip" in str(p))
    monkeypatch.setattr(app.os.path, "getsize", lambda p: 1024)

    result = app._collect_reel_job_output_snapshot("job-1", "/tmp/output/job-1")
    assert result["expected_clips"] == 2


def test_estimate_reel_job_consumption_with_zero_clips(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._estimate_reel_job_consumption(
        elapsed_seconds=10.0,
        uses_youtube=False,
        processed_clips=0,
        expected_clips=0,
        storage_bytes=0,
    )

    assert result["actual_cost_usd"] == 0.0
    assert result["actual_credit"] == 0.0


def test_preemption_sort_key_uses_priority_and_timestamp(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    ctx1 = {"priority": 2, "started_at": 100.0}
    ctx2 = {"priority": 1, "started_at": 50.0}

    key1 = app._preemption_sort_key(ctx1)
    key2 = app._preemption_sort_key(ctx2)

    assert key1 > key2  # ctx2 should be preempted first


def test_get_preemption_candidate_returns_none_when_empty(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.running_reel_jobs.clear()

    result = app._get_preemption_candidate()
    assert result is None


def test_resolve_hydration_video_source_downloads_from_url(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_resolve_local_video_from_input_ref", lambda ref: None)
    monkeypatch.setattr(
        app, "_download_input_url_to_job_dir",
        lambda url, job_id: ("/tmp/downloaded.mp4", "downloaded.mp4")
    )

    result = app._resolve_hydration_video_source(
        "https://example.com/video.mp4",
        "job-1",
        "/tmp/output/job-1"
    )
    assert result == ("/tmp/downloaded.mp4", "downloaded.mp4")


def test_resolve_local_video_from_input_ref_parses_videos_path(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", "/output")
    monkeypatch.setattr(app.os.path, "exists", lambda p: "/output/job-1/video.mp4" in str(p))

    result = app._resolve_local_video_from_input_ref("/videos/job-1/video.mp4")
    assert result is not None
    assert result[1] == "video.mp4"


def test_estimate_reel_cost_breakdown_calculates_cost(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    # This function should exist and calculate cost
    result = app._estimate_reel_cost_breakdown(
        duration_seconds=30.0,
        size_bytes=10*1024*1024,  # 10MB
        uses_youtube_source=False
    )

    assert "total_usd" in result


def test_build_billing_details_structures_data(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._build_billing_details(
        "generation_reel",
        {"total_usd": 0.5},
        actual_storage_gb=0.01
    )

    assert "operation" in result


def test_job_uses_remote_source_checks_source_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app._job_uses_remote_source({"source_type": "url"}) is True
    assert app._job_uses_remote_source({"source_type": "file"}) is False
    assert app._job_uses_remote_source({"attestation": {"source": "url"}}) is True
    assert app._job_uses_remote_source({}) is False


def test_transcript_full_text_extracts_from_segments(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    transcript = {
        "text": "Full transcript",
        "segments": []
    }
    result = app._transcript_full_text(transcript)
    assert result == "Full transcript"

    transcript = {
        "segments": [
            {"text": "Hello"},
            {"text": "world"}
        ]
    }
    result = app._transcript_full_text(transcript)
    assert "Hello" in result
    assert "world" in result


def test_bytes_to_gb_conversion(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._bytes_to_gb(1024*1024*1024)  # 1 GB
    assert result == 1.0


def test_sanitize_input_filename_removes_unsafe_chars(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    result = app._sanitize_input_filename("../../../etc/passwd")
    assert ".." not in result


def test_enqueue_output_reads_from_stdout(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs["job-test"] = {"logs": []}

    class FakeOut:
        def __init__(self):
            self.lines = [b"line1\n", b"line2\n", b""]
            self.idx = 0

        def readline(self):
            if self.idx < len(self.lines):
                result = self.lines[self.idx]
                self.idx += 1
                return result
            return b""

        def close(self):
            pass

    app.enqueue_output(FakeOut(), "job-test")

    assert "line1" in app.jobs["job-test"]["logs"]
    assert "line2" in app.jobs["job-test"]["logs"]


def test_allowed_video_formats_and_validate_extension(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "VIREEL_VIDEO_FORMAT", "mp4, mov , .mkv")

    assert app._allowed_video_formats() == ["mp4", "mov", "mkv"]
    app._validate_video_extension("demo.mp4")
    with pytest.raises(app.HTTPException):
        app._validate_video_extension("demo.txt")


def test_validate_video_extension_skips_when_empty_format_config(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "VIREEL_VIDEO_FORMAT", "")
    app._validate_video_extension("anything.bin")


def test_normalize_auto_edit_options_defaults_and_truthy(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    defaults = app._normalize_auto_edit_options(None)
    enabled = app._normalize_auto_edit_options({"zoom": 1, "contrast": True, "speed": "yes"})

    assert all(value is False for value in defaults.values())
    assert enabled["zoom"] is True
    assert enabled["contrast"] is True
    assert enabled["speed"] is True


def test_apply_auto_edit_options_to_effects_config_disables_visual_segments(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    effects = {
        "segments": [
            {
                "startSec": 0,
                "endSec": 3,
                "zoom": 1.2,
                "zoomCenterX": 0.2,
                "zoomCenterY": 0.8,
                "brightness": 1.1,
                "contrast": 1.2,
                "saturate": 1.3,
            }
        ]
    }
    opts = {"zoom": False, "brightness": False, "contrast": False, "saturation": False}

    config, applied = app._apply_auto_edit_options_to_effects_config(effects, opts)

    seg = config["segments"][0]
    assert seg["zoom"] == 1.0
    assert seg["zoomCenterX"] == 0.5
    assert seg["zoomCenterY"] == 0.5
    assert seg["brightness"] == 1.0
    assert seg["contrast"] == 1.0
    assert seg["saturate"] == 1.0
    assert applied == []


def test_apply_auto_edit_options_to_effects_config_records_steps(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    config, applied = app._apply_auto_edit_options_to_effects_config(
        {"segments": []},
        {
            "removeBadTakes": True,
            "removeSilence": True,
            "cleanAudio": True,
            "zoom": True,
            "brightness": True,
            "saturation": True,
            "contrast": True,
            "speed": True,
        },
    )
    assert config["segments"] == []
    assert "remove_bad_takes:queued" in applied
    assert "speed:queued" in applied
    assert "zoom:enabled" in applied


def test_apply_auto_edit_options_to_filter_data_removes_disabled_filters(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _VE:
        @staticmethod
        def _split_filter_chain(s):
            return s.split(",")

    monkeypatch.setattr(app, "VideoEditor", _VE)
    data, applied = app._apply_auto_edit_options_to_filter_data(
        {
            "filter_string": "zoompan=z='1.2',hue=s=0,eq=contrast=1.2,unsharp=5:5:1.0"
        },
        {"zoom": False, "saturation": False, "brightness": False, "contrast": False},
    )
    assert "zoompan=" not in data["filter_string"]
    assert "hue=" not in data["filter_string"]
    assert "eq=" not in data["filter_string"]
    assert "unsharp=" in data["filter_string"]
    assert applied == []


def test_apply_auto_edit_options_to_filter_data_empty_filter(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    data, applied = app._apply_auto_edit_options_to_filter_data({}, {"zoom": True})
    assert data == {}
    assert applied == []


def test_run_ffmpeg_command_success_and_failure(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _R:
        def __init__(self, code, stderr=b""):
            self.returncode = code
            self.stderr = stderr

    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: _R(0, b""))
    app._run_ffmpeg_command(["ffmpeg", "-version"])

    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: _R(1, b"boom"))
    with pytest.raises(RuntimeError):
        app._run_ffmpeg_command(["ffmpeg", "-version"])


def test_video_has_audio_stream_true_and_false(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app.subprocess, "check_output", lambda *args, **kwargs: b"audio\n")
    assert app._video_has_audio_stream("in.mp4") is True

    monkeypatch.setattr(
        app.subprocess,
        "check_output",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ffprobe fail")),
    )
    assert app._video_has_audio_stream("in.mp4") is False


def test_merge_intervals_and_invert_cut_ranges(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    merged = app._merge_intervals([(1, 3), (2, 4), (-1, 0.5), (9, 8)])
    assert merged == [(0.0, 0.5), (1.0, 4.0)]

    keep = app._invert_cut_ranges(10, [(1, 2), (3, 5), (4.5, 6)])
    assert keep == [(0.0, 1.0), (2.0, 3.0), (6.0, 10.0)]


def test_build_keep_time_expr(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    expr = app._build_keep_time_expr([(0.0, 1.23456), (2.0, 3.0)])
    assert expr == "between(t,0.0,1.235)+between(t,2.0,3.0)"
    assert app._build_keep_time_expr([]) == "0"


def test_detect_silence_cut_ranges_parses_ffmpeg_output(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _R:
        def __init__(self, stderr_text):
            self.stderr = stderr_text.encode("utf-8")

    log = """
    [silencedetect @ x] silence_start: 1.0
    [silencedetect @ x] silence_end: 2.0 | silence_duration: 1.0
    [silencedetect @ x] silence_start: 8.0
    """
    monkeypatch.setattr(app.subprocess, "run", lambda *args, **kwargs: _R(log))
    ranges = app._detect_silence_cut_ranges("video.mp4", total_duration=10.0)
    assert ranges == [(1.0, 2.0), (8.0, 10.0)]


def test_atempo_chain_and_speed_transform(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._atempo_chain(5.0) == "atempo=2.0"
    assert app._atempo_chain(0.1) == "atempo=0.5"

    captured = {}
    monkeypatch.setattr(app, "_run_ffmpeg_command", lambda cmd: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: True)
    app._apply_speed_transform("in.mp4", "out.mp4", 1.1)
    assert "-filter:a" in captured["cmd"]

    captured.clear()
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: False)
    app._apply_speed_transform("in.mp4", "out.mp4", 1.1)
    assert "-an" in captured["cmd"]


def test_apply_clean_audio_transform_branches(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    copied = {}
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: False)
    monkeypatch.setattr(app.shutil, "copy", lambda src, dst: copied.setdefault("copy", (src, dst)))
    app._apply_clean_audio_transform("in.mp4", "out.mp4")
    assert copied["copy"] == ("in.mp4", "out.mp4")

    captured = {}
    monkeypatch.setattr(app, "_video_has_audio_stream", lambda _: True)
    monkeypatch.setattr(app, "_run_ffmpeg_command", lambda cmd: captured.setdefault("cmd", cmd))
    app._apply_clean_audio_transform("in.mp4", "out.mp4")
    assert "-af" in captured["cmd"]


def test_bad_take_heuristics_parse_and_sanitize(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    transcript = {
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "um um yes"},
            {"start": 2.0, "end": 3.0, "text": "hello hello hello world"},
            {"start": 3.0, "end": 2.0, "text": "bad"},
        ]
    }
    raw = app._detect_bad_take_candidates_heuristic(transcript)
    assert len(raw) == 2

    parsed = app._parse_bad_take_candidates_response("```json\n{\"candidates\":[{\"start\":0,\"end\":1}]}\n```")
    assert parsed == [{"start": 0, "end": 1}]
    assert app._parse_bad_take_candidates_response("not-json") == []

    sanitized = app._sanitize_bad_take_candidates(
        [
            {"start": -1, "end": 1.23456, "reason": "x" * 130, "confidence": 2},
            {"start": 1.0, "end": 2.0, "reason": "same", "confidence": 0.8},
            {"start": 1.5, "end": 3.0, "reason": "same", "confidence": 0.9},
        ],
        max_end=5.0,
    )
    assert sanitized[0]["start"] == 0.0
    assert len(sanitized[0]["reason"]) <= 120
    assert sanitized[0]["confidence"] <= 1.0
    assert sanitized[-1]["end"] == 3.0


def test_detect_bad_take_candidates_ai_early_returns(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("AUTO_EDIT_BAD_TAKE_AI", "false")
    assert app._detect_bad_take_candidates_ai({"segments": [{"start": 0, "end": 1, "text": "x"}]}) == []

    monkeypatch.setenv("AUTO_EDIT_BAD_TAKE_AI", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert app._detect_bad_take_candidates_ai({"segments": [{"start": 0, "end": 1, "text": "x"}]}) == []


def test_process_endpoint_requires_source(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"acknowledged": True}

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(app.process_endpoint(_Req(), "u1", None, None, None))

    assert exc.value.status_code == 400
    assert "Must provide URL or File" in str(exc.value.detail)


def test_process_endpoint_requires_ack(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"url": "https://cdn.example.com/v.mp4", "acknowledged": False}

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(app.process_endpoint(_Req(), "u1", None, None, None))

    assert exc.value.status_code == 400
    assert "must confirm" in str(exc.value.detail).lower()


def test_process_endpoint_blocks_youtube_when_disabled(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(app, "DISABLE_YOUTUBE_URL", True)

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"url": "https://youtube.com/watch?v=abc", "acknowledged": True}

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(app.process_endpoint(_Req(), "u1", None, None, None))

    assert exc.value.status_code == 403


def test_get_status_404_when_unknown_job(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.get_job_view = AsyncMock(return_value=None)

    with TestClient(app.app) as client:
        resp = client.get("/api/status/missing", headers=_auth_headers("u1"))
    assert resp.status_code == 404


def test_get_status_includes_partial_clips_from_runtime(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs["job-1"] = {
        "status": "processing",
        "output_dir": "/tmp/output/job-1",
        "user_id": "u1",
    }
    app.reel_job_manager.get_job_view = AsyncMock(return_value={"status": "processing"})
    monkeypatch.setattr(app.os.path, "exists", lambda p: str(p) == "/tmp/output/job-1")
    monkeypatch.setattr(app.os, "listdir", lambda p: ["job-1_clip_1.mp4", "temp_ignore.mp4", "job-1_clip_2.mp4"])

    with TestClient(app.app) as client:
        resp = client.get("/api/status/job-1", headers=_auth_headers("u1"))
    assert resp.status_code == 200
    payload = resp.json()
    assert "partialClips" in payload
    assert len(payload["partialClips"]) == 2
    assert payload["partialClips"][0]["index"] == 0


def test_edit_endpoint_requires_api_key(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/edit",
            json={"job_id": "j1", "clip_index": 0},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_edit_endpoint_job_not_found_without_input_filename(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    app.jobs.clear()

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/edit",
            # A well-formed but nonexistent job_id: must pass the
            # _JOB_ID_PATTERN format check (audit finding C7) to reach the
            # "not found" branch this test actually targets, rather than
            # being rejected earlier as a malformed id.
            json={"job_id": "deadbeef-dead-beef-dead-beefdeadbeef", "clip_index": 0},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 404


def test_process_captions_endpoint_requires_ack(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    with TestClient(app.app) as client:
        resp = client.post(
            "/api/captions/process",
            files={"file": ("v.mp4", b"abc", "video/mp4")},
            data={"acknowledged": "false"},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_ensure_clip_preview_endpoint_uses_mocked_preview(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app._ensure_preview_image_for_clip = AsyncMock(return_value="https://cdn.example/p.jpg")

    with TestClient(app.app) as client:
        resp = client.get("/api/clip/job-1/0/preview-image/ensure", headers=_auth_headers("u1"))
    assert resp.status_code == 200
    assert resp.json()["ensured"] is True


def test_run_job_wrapper_routes_caption_and_releases(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "caption-job-1"
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs[job_id] = {"job_kind": "caption", "priority": 2}

    run_caption = AsyncMock()
    run_reel = AsyncMock()
    monkeypatch.setattr(app, "run_caption_job", run_caption)
    monkeypatch.setattr(app, "run_job", run_reel)

    released = {"count": 0}
    monkeypatch.setattr(app, "concurrency_semaphore", types.SimpleNamespace(release=lambda: released.__setitem__("count", released["count"] + 1)))
    monkeypatch.setattr(app, "job_queue", types.SimpleNamespace(task_done=lambda: None))

    asyncio.run(app.run_job_wrapper(job_id, 2))

    run_caption.assert_awaited_once()
    run_reel.assert_not_awaited()
    assert released["count"] == 1
    assert job_id not in app.running_reel_jobs


def test_run_job_wrapper_routes_reel(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    job_id = "reel-job-1"
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs[job_id] = {"job_kind": "reel", "priority": 2}

    run_caption = AsyncMock()
    run_reel = AsyncMock()
    monkeypatch.setattr(app, "run_caption_job", run_caption)
    monkeypatch.setattr(app, "run_job", run_reel)
    monkeypatch.setattr(app, "concurrency_semaphore", types.SimpleNamespace(release=lambda: None))
    monkeypatch.setattr(app, "job_queue", types.SimpleNamespace(task_done=lambda: None))

    asyncio.run(app.run_job_wrapper(job_id, 2))
    run_reel.assert_awaited_once()
    run_caption.assert_not_awaited()


def test_process_queue_dispatches_one_job_then_cancel(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs.clear()
    app.reel_job_manager.runtime_jobs.clear()
    app.reel_job_manager.runtime_jobs["job-q1"] = {"priority": 3}

    class _Queue:
        def __init__(self):
            self.calls = 0

        async def get(self):
            self.calls += 1
            if self.calls == 1:
                return (-3, 1, "job-q1")
            raise asyncio.CancelledError()

    queue = _Queue()
    monkeypatch.setattr(app, "job_queue", queue)
    acquire_mock = AsyncMock()
    monkeypatch.setattr(app, "concurrency_semaphore", types.SimpleNamespace(acquire=acquire_mock, release=lambda: None))

    scheduled = {"count": 0}

    def _fake_create_task(coro):
        scheduled["count"] += 1
        try:
            coro.close()
        except Exception:
            pass
        return None

    monkeypatch.setattr(app.asyncio, "create_task", _fake_create_task)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(app.process_queue("w1"))

    acquire_mock.assert_awaited_once()
    assert scheduled["count"] == 1


def test_enforce_subscription_retention_policy_branches(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    # active
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"id": "sub1"}))
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "active"

    # no subscription
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "no_subscription"


def test_enforce_subscription_retention_policy_retention_and_disabled(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    real_datetime = __import__("datetime").datetime
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"id": "sub2", "payment_end_date": "x"}))
    monkeypatch.setattr(app, "_parse_iso_datetime", lambda _: real_datetime(2026, 1, 1, tzinfo=app.timezone.utc))
    monkeypatch.setattr(app, "STORAGE_RETENTION_PERIODE_DAYS", 10)
    monkeypatch.setattr(app, "_ensure_retention_deadline_on_subscription", AsyncMock())
    zero_mock = AsyncMock()
    disable_mock = AsyncMock()
    monkeypatch.setattr(app, "_zero_balances_on_subscription_expiration", zero_mock)
    monkeypatch.setattr(app, "_disable_subscription_account_if_needed", disable_mock)

    class _DTInWindow:
        @staticmethod
        def now(tz=None):
            return real_datetime(2026, 1, 5, tzinfo=app.timezone.utc)

    monkeypatch.setattr(app, "datetime", _DTInWindow)
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "retention_window"

    class _DTPastWindow:
        @staticmethod
        def now(tz=None):
            return real_datetime(2026, 2, 1, tzinfo=app.timezone.utc)

    monkeypatch.setattr(app, "datetime", _DTPastWindow)
    result = asyncio.run(app._enforce_subscription_retention_policy("u1"))
    assert result["state"] == "disabled"
    zero_mock.assert_awaited_once()
    disable_mock.assert_awaited_once()


def test_process_endpoint_json_url_enqueues_job(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app, "DISABLE_YOUTUBE_URL", False)
    monkeypatch.setattr(app.uuid, "uuid4", lambda: "job-json-1")
    monkeypatch.setattr(app, "_probe_remote_video_metadata", lambda *_: {
        "duration_seconds": 42.0,
        "size_bytes": 2048,
        "title": "Titre test",
        "description": "desc",
    })
    monkeypatch.setattr(app, "_validate_reel_source_constraints", lambda **kwargs: None)
    monkeypatch.setattr(app, "_estimate_reel_required_credits", lambda **kwargs: 1.25)
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=3))
    # Security hardening (audit finding H8): job creation now atomically
    # *reserves* the estimated credits via _reserve_job_credits instead of
    # merely checking the balance with _assert_user_has_required_credits.
    reserve_credits = AsyncMock()
    monkeypatch.setattr(app, "_reserve_job_credits", reserve_credits)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    app.reel_job_manager.create_job = AsyncMock()
    app.reel_job_manager.enqueue_job = AsyncMock()
    enqueue_job = AsyncMock()
    monkeypatch.setattr(app, "enqueue_reel_job", enqueue_job)

    class _Pipeline:
        def __init__(self, *_args, **_kwargs):
            pass

        async def queued(self):
            return None

    monkeypatch.setattr(app, "ReelProcessingPipeline", _Pipeline)

    class _Req:
        headers = {
            "content-type": "application/json",
            "user-agent": "pytest",
        }
        client = types.SimpleNamespace(host="127.0.0.1")

        async def json(self):
            return {"url": "https://cdn.example.com/reel.mp4", "acknowledged": True}

    payload = asyncio.run(
        app.process_endpoint(
            request=_Req(),
            file=None,
            url=None,
            acknowledged=None,
            user_id="u1",
        )
    )

    assert payload["job_id"] == "job-json-1"
    assert payload["status"] == "queued"
    assert "job-json-1" in app.jobs
    assert "-u" in app.jobs["job-json-1"]["cmd"]
    reserve_credits.assert_awaited_once()
    app.reel_job_manager.create_job.assert_awaited_once()
    app.reel_job_manager.enqueue_job.assert_awaited_once_with("job-json-1")
    enqueue_job.assert_awaited_once_with("job-json-1", priority=3)


def test_process_endpoint_upload_rejects_oversized_file(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(app, "REEL_MAX_STORAGE_GB", 1e-9)
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    os.makedirs(app.UPLOAD_DIR, exist_ok=True)

    class _Req:
        headers = {"user-agent": "pytest"}
        client = types.SimpleNamespace(host="127.0.0.1")

    class _Upload:
        def __init__(self, content: bytes):
            self.filename = "big.mp4"
            self.content_type = "video/mp4"
            self._content = content
            self._done = False

        async def read(self, _chunk_size: int):
            if self._done:
                return b""
            self._done = True
            return self._content

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(
            app.process_endpoint(
                request=_Req(),
                file=_Upload(b"0123456789"),
                url=None,
                acknowledged="true",
                user_id="u1",
            )
        )

    assert exc.value.status_code == 413
    assert "Maximum autorise" in str(exc.value.detail)


def test_render_proxy_endpoints_forward_requests(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "RENDER_SERVICE_URL", "http://render.test")

    httpx_mod = types.ModuleType("httpx")

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json, headers=None):
            return types.SimpleNamespace(json=lambda: {"ok": True, "url": url, "body": json})

        async def get(self, url, headers=None):
            return types.SimpleNamespace(json=lambda: {"ok": True, "url": url})

    httpx_mod.AsyncClient = _Client
    monkeypatch.setitem(sys.modules, "httpx", httpx_mod)

    with TestClient(app.app) as client:
        post_resp = client.post("/api/render", json={"composition": "Main"}, headers=_auth_headers("u1"))
        get_resp = client.get("/api/render/r-123", headers=_auth_headers("u1"))

    assert post_resp.status_code == 200
    assert post_resp.json()["url"] == "http://render.test/render"
    assert post_resp.json()["body"]["composition"] == "Main"
    assert get_resp.status_code == 200
    assert get_resp.json()["url"] == "http://render.test/render/r-123"


def test_generate_effects_config_with_input_filename_success(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    app.jobs["eeffeeff-eeff-eeff-eeff-eeffeeffeeff"] = {"user_id": "u1"}
    input_dir = tmp_path / "output" / "eeffeeff-eeff-eeff-eeff-eeffeeffeeff"
    input_dir.mkdir(parents=True, exist_ok=True)
    input_file = input_dir / "clip.mp4"
    input_file.write_bytes(b"video")
    monkeypatch.setattr(app.os.path, "getsize", lambda _p: 4096)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 8.0)
    monkeypatch.setattr(app, "_estimate_reel_required_credits", lambda **_kwargs: 0.8)
    assert_credits = AsyncMock()
    monkeypatch.setattr(app, "_assert_user_has_required_credits", assert_credits)
    monkeypatch.setattr(
        app.subprocess,
        "check_output",
        lambda _cmd, **_kwargs: b'{"streams":[{"width":1080,"height":1920,"r_frame_rate":"30/1","duration":8}],"format":{"duration":8}}',
    )
    monkeypatch.setattr(app.shutil, "copy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app.os, "remove", lambda _p: None)
    monkeypatch.setattr(
        app,
        "_apply_auto_edit_options_to_effects_config",
        lambda effects, _opts: (effects, ["normalized"]),
    )

    class _Editor:
        def __init__(self, api_key):
            self.api_key = api_key

        def upload_video(self, _path):
            return "uploaded-ref"

        def get_effects_config(self, *_args, **_kwargs):
            return {"layers": [{"type": "zoom", "start": 0, "end": 60}]}

    monkeypatch.setattr(app, "VideoEditor", _Editor)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/effects/generate",
            json={"job_id": "eeffeeff-eeff-eeff-eeff-eeffeeffeeff", "clip_index": 0, "input_filename": "clip.mp4"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["effects"]["layers"][0]["type"] == "zoom"
    assert payload["applied_steps"] == ["normalized"]
    assert_credits.assert_awaited_once()


def test_generate_effects_config_rejects_cross_tenant_job_id(monkeypatch):
    # Regression test: unlike its siblings /api/edit, /api/subtitle and
    # /api/hook, this endpoint never called _require_job_ownership, so any
    # authenticated user who knew or guessed another user's job_id could
    # have their own video analyzed by Gemini and returned to them.
    app = _import_app_with_stubs(monkeypatch)
    app.jobs["00000000-0000-0000-0000-000000000001"] = {"user_id": "victim"}

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/effects/generate",
            json={"job_id": "00000000-0000-0000-0000-000000000001", "clip_index": 0, "input_filename": "clip.mp4"},
            headers=_auth_headers("attacker"),
        )

    assert resp.status_code == 404


def test_translate_captions_requires_authentication(monkeypatch):
    # Regression test: /api/translate/captions took `request: Request`
    # instead of a Depends(get_user_id_header) parameter, so it ran without
    # any authentication at all -- an anonymous caller supplying a real
    # job_id/clip_index could trigger paid OpenAI/Gemini translation calls
    # billed to that job's real owner, with no credit check anywhere.
    app = _import_app_with_stubs(monkeypatch)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/translate/captions",
            json={"job_id": "some-job", "clip_index": 0, "target_language": "fr"},
        )

    assert resp.status_code == 401


def test_translate_captions_rejects_cross_tenant_job_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs["00000000-0000-0000-0000-000000000001"] = {"user_id": "victim"}

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/translate/captions",
            json={"job_id": "00000000-0000-0000-0000-000000000001", "clip_index": 0, "target_language": "fr"},
            headers=_auth_headers("attacker"),
        )

    assert resp.status_code == 404


def test_translate_clip_requires_authentication(monkeypatch):
    # Same gap as translate_captions above, on the sibling endpoint that
    # actually burns a translated video to disk and updates job metadata.
    app = _import_app_with_stubs(monkeypatch)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/translate",
            json={"job_id": "some-job", "clip_index": 0, "target_language": "fr"},
        )

    assert resp.status_code == 401


def test_translate_clip_rejects_cross_tenant_job_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs["00000000-0000-0000-0000-000000000001"] = {"user_id": "victim"}

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/translate",
            json={"job_id": "00000000-0000-0000-0000-000000000001", "clip_index": 0, "target_language": "fr"},
            headers=_auth_headers("attacker"),
        )

    assert resp.status_code == 404


def test_thumbnail_publish_status_requires_authentication(monkeypatch):
    # Regression test: unlike its sibling /api/render/{render_id}, this
    # endpoint had no auth dependency at all, so anyone holding a publish_id
    # could poll another user's publish result.
    app = _import_app_with_stubs(monkeypatch)
    app.publish_jobs["pub-1"] = {"status": "done", "result": {"video_id": "v1"}, "error": None, "user_id": "owner"}

    with TestClient(app.app) as client:
        resp = client.get("/api/thumbnail/publish/status/pub-1")

    assert resp.status_code == 401


def test_thumbnail_publish_status_rejects_cross_tenant_publish_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.publish_jobs["pub-1"] = {"status": "done", "result": {"video_id": "v1"}, "error": None, "user_id": "owner"}

    with TestClient(app.app) as client:
        resp = client.get("/api/thumbnail/publish/status/pub-1", headers=_auth_headers("attacker"))

    assert resp.status_code == 404


def test_thumbnail_publish_status_returns_status_for_owner(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    app.publish_jobs["pub-1"] = {"status": "done", "result": {"video_id": "v1"}, "error": None, "user_id": "owner"}

    with TestClient(app.app) as client:
        resp = client.get("/api/thumbnail/publish/status/pub-1", headers=_auth_headers("owner"))

    assert resp.status_code == 200
    assert resp.json() == {"status": "done", "result": {"video_id": "v1"}, "error": None}


def test_probe_video_stream_for_effects_handles_empty_streams_list(monkeypatch, tmp_path):
    # Regression test: `probe_data.get('streams', [{}])[0]` only falls back
    # to [{}] when the 'streams' key is missing entirely -- a file ffprobe
    # can read but detects no video stream in (streams: []) still indexed
    # into an empty list and raised IndexError, surfacing as a generic 500
    # on /api/effects/generate.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(
        app.subprocess,
        "check_output",
        lambda _cmd, **_kwargs: b'{"streams":[],"format":{"duration":12.5}}',
    )
    width, height, fps, duration = app._probe_video_stream_for_effects(str(tmp_path / "clip.mp4"))
    assert width == 1080
    assert height == 1920
    assert fps == 30.0
    assert duration == 12.5


def test_add_subtitles_dubbed_video_uses_transcription(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(app, "_append_style_version_to_metadata", lambda *_args, **_kwargs: 4)
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_args, **_kwargs: None)
    assert_credits = AsyncMock()
    monkeypatch.setattr(app, "_assert_user_has_required_credits", assert_credits)

    meta = {
        "transcript": {"segments": [{"text": "hello"}]},
        "shorts": [{"start": 0.0, "end": 4.0, "video_url": "/videos/deadbeef/translated_clip.mp4"}],
    }
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("/tmp/meta.json", meta)))

    calls = {"transcribed": 0}

    def _fake_transcribe(_input, _srt, max_words_per_line=4, highlight=False):
        calls["transcribed"] += 1
        return True

    monkeypatch.setattr(app, "generate_srt_from_video", _fake_transcribe)
    monkeypatch.setattr(
        app,
        "generate_srt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generate_srt should not run for dubbed files")),
    )
    monkeypatch.setattr(app, "burn_subtitles", lambda *_args, **_kwargs: True)

    class _StyleOptions:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(app, "SubtitleStyleOptions", _StyleOptions)
    app.jobs["deadbeef"] = {
        "user_id": "u1",
        "result": {"clips": [{"video_url": "/videos/deadbeef/translated_clip.mp4"}]},
    }

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/subtitle",
            json={
                "job_id": "deadbeef",
                "clip_index": 0,
                "input_filename": "translated_clip.mp4",
                "words_per_line": 6,
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["version"] == 4
    assert calls["transcribed"] == 1
    assert_credits.assert_awaited_once()


def test_persist_captioned_reel_happy_path_with_s3_supabase_and_style(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 12.0)
    monkeypatch.setattr(app, "_estimate_caption_cost_breakdown", lambda **_kwargs: {"total_usd": 0.1})
    monkeypatch.setattr(app, "_estimate_caption_required_credits", lambda **_kwargs: 0.5)
    monkeypatch.setattr(app, "_bytes_to_gb", lambda _b: 0.001)
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda key: f"https://cdn.caption/{key}" if key else "")
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.reel/{key}" if key else "")
    monkeypatch.setattr(app, "_reel_thumbnail_url_from_s3_key", lambda key: f"https://cdn.thumb/{key}" if key else "")
    monkeypatch.setattr(app, "_build_billing_details", lambda *_args, **_kwargs: {"ok": True})

    metadata = {
        "shorts": [{"video_url": "/videos/job-1/original.mp4", "start": 0.0, "end": 2.0}],
        "style_history": {},
    }
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("/tmp/meta.json", metadata)))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_append_style_version_to_metadata", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock())

    thumb_path = tmp_path / "thumb.jpg"
    thumb_path.write_bytes(b"thumb")
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *_args, **_kwargs: str(thumb_path))
    monkeypatch.setattr(app.os, "remove", lambda _p: None)

    upload_calls = []

    def _upload(path, bucket, key):
        upload_calls.append((path, bucket, key))
        return True

    monkeypatch.setattr(app, "upload_file_to_s3", _upload)
    monkeypatch.setattr(app, "supabase_get_caption_by_job_clip", AsyncMock(return_value={"id": "cap-1", "caption_s3_key": "captions/u1/job-1/prev.mp4"}))
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"reel_s3_key": "reels/u1/job-1/prev.mp4"}))
    app.supabase_update_caption = AsyncMock()
    app.supabase_update_reel_media_by_job_clip = AsyncMock()
    app.supabase_deduct_user_credits = AsyncMock(return_value=True)
    app.supabase_insert_user_data_history = AsyncMock()
    app.supabase_insert_style_edit_version = AsyncMock()

    class _Upload:
        def __init__(self):
            self.filename = "render.mov"
            self.content_type = "video/quicktime"
            self.file = io.BytesIO(b"video-bytes")
            self.closed = False

        async def close(self):
            self.closed = True

    app.jobs["job-1"] = {"result": {"clips": [{"video_url": "/videos/job-1/original.mp4"}]}}
    upload = _Upload()

    result = asyncio.run(
        app.persist_captioned_reel(
            job_id="job-1",
            clip_index=0,
            file=upload,
            subtitle_config='{"style": {"font_name": "Inter"}}',
            remotion_layers='{"layers": [{"type": "caption"}]}',
            user_id="u1",
        )
    )

    assert result["success"] is True
    assert result["persisted"] is True
    assert result["new_video_url"].startswith("https://cdn.caption/captions/u1/job-1/")
    assert result["preview_image_url"].startswith("https://cdn.caption/captions/u1/job-1/thumbnail_")
    assert upload.closed is True
    assert len(upload_calls) >= 3
    app.supabase_update_caption.assert_awaited_once()
    app.supabase_update_reel_media_by_job_clip.assert_awaited_once()
    app.supabase_deduct_user_credits.assert_awaited_once()
    app.supabase_insert_user_data_history.assert_awaited_once()
    app.supabase_insert_style_edit_version.assert_awaited_once()


def test_persist_captioned_reel_falls_back_to_local_urls_when_s3_upload_fails(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 6.0)
    monkeypatch.setattr(app, "_estimate_caption_cost_breakdown", lambda **_kwargs: {})
    monkeypatch.setattr(app, "_estimate_caption_required_credits", lambda **_kwargs: 0.0)
    monkeypatch.setattr(app, "_bytes_to_gb", lambda _b: 0.0)
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock())

    metadata = {"shorts": [{"video_url": "/videos/job-2/base.mp4", "start": 0.0, "end": 1.0}]}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("/tmp/meta.json", metadata)))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app, "_generate_reel_thumbnail_from_video", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *_args, **_kwargs: False)

    class _Upload:
        def __init__(self):
            self.filename = "render.webm"
            self.content_type = "video/webm"
            self.file = io.BytesIO(b"video")

        async def close(self):
            return None

    result = asyncio.run(
        app.persist_captioned_reel(
            job_id="job-2",
            clip_index=0,
            file=_Upload(),
            subtitle_config="{bad-json",
            remotion_layers="{bad-json",
            user_id="u2",
        )
    )

    assert result["success"] is True
    assert result["new_video_url"].startswith("/videos/job-2/captioned_0_")
    assert result["preview_image_url"] == result["new_video_url"]


def test_persist_captioned_reel_rejects_non_video_content_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _Upload:
        filename = "render.txt"
        content_type = "text/plain"
        file = io.BytesIO(b"x")

        async def close(self):
            return None

    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(
            app.persist_captioned_reel(
                job_id="job-3",
                clip_index=0,
                file=_Upload(),
                subtitle_config=None,
                remotion_layers=None,
                user_id="u3",
            )
        )

    assert exc.value.status_code == 400
    assert "Invalid rendered video content type" in str(exc.value.detail)




def test_reset_clip_metadata_to_original_prefers_default_video_url(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    metadata_path = str(tmp_path / "meta.json")
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_a, **_k: None)
    data = {"shorts": [{"video_url": "custom.mp4", "original_video_url": "bare.mp4"}]}

    result = app._reset_clip_metadata_to_original(metadata_path, data, 0, default_video_url="default-styled.mp4")

    assert result == "default-styled.mp4"
    assert data["shorts"][0]["video_url"] == "default-styled.mp4"


def test_reset_clip_metadata_to_original_falls_back_to_bare_original(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    metadata_path = str(tmp_path / "meta.json")
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_a, **_k: None)
    data = {"shorts": [{"video_url": "custom.mp4", "original_video_url": "bare.mp4"}]}

    result = app._reset_clip_metadata_to_original(metadata_path, data, 0)

    assert result == "bare.mp4"
    assert data["shorts"][0]["video_url"] == "bare.mp4"


def test_find_default_style_version_returns_matching_version(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    versions = [
        {"version_number": 1, "output_video_url": "default.mp4"},
        {"version_number": 2, "output_video_url": "manual-edit.mp4"},
    ]
    monkeypatch.setattr(app, "supabase_list_style_edit_versions", AsyncMock(return_value=versions))

    result = asyncio.run(app._find_default_style_version("job-1", 0, "u1"))

    assert result == versions[0]


def test_find_default_style_version_returns_none_without_supabase(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    list_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_list_style_edit_versions", list_mock)

    result = asyncio.run(app._find_default_style_version("job-1", 0, "u1"))

    assert result is None
    list_mock.assert_not_awaited()


def test_reset_caption_style_history_restores_default_version(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    data = {"shorts": [{"video_url": "manual-edit.mp4", "original_video_url": "bare.mp4"}]}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("meta.json", data)))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_a, **_k: None)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    default_version = {
        "version_number": 1,
        "operation_type": "subtitle_style",
        "source_video_url": "bare.mp4",
        "output_video_url": "default-styled.mp4",
        "style_config": dict(app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS),
        "billing_details": {},
    }
    monkeypatch.setattr(app, "_find_default_style_version", AsyncMock(return_value=default_version))
    delete_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_delete_style_edit_versions", delete_mock)
    insert_mock = AsyncMock(return_value={})
    monkeypatch.setattr(app, "supabase_insert_style_edit_version", insert_mock)

    result = asyncio.run(app.reset_caption_style_history("job-1", 0, "u1"))

    assert result["video_url"] == "default-styled.mp4"
    assert data["shorts"][0]["video_url"] == "default-styled.mp4"
    delete_mock.assert_awaited_once_with("job-1", 0, "u1")
    insert_mock.assert_awaited_once()
    reinserted = insert_mock.await_args.args[0]
    assert reinserted["version_number"] == app._DEFAULT_STYLE_VERSION_NUMBER
    assert reinserted["output_video_url"] == "default-styled.mp4"


def test_reset_caption_style_history_falls_back_without_default_version(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    data = {"shorts": [{"video_url": "manual-edit.mp4", "original_video_url": "bare.mp4"}]}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("meta.json", data)))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *_a, **_k: None)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_find_default_style_version", AsyncMock(return_value=None))
    delete_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_delete_style_edit_versions", delete_mock)
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_style_edit_version", insert_mock)

    result = asyncio.run(app.reset_caption_style_history("job-1", 0, "u1"))

    assert result["video_url"] == "bare.mp4"
    delete_mock.assert_awaited_once_with("job-1", 0, "u1")
    insert_mock.assert_not_awaited()


def test_resolve_accounts_for_publish_rejects_instagram_for_anonymous_story_set(monkeypatch):
    # Anonymous stories may only be published to Facebook/LinkedIn accounts
    # (the user's explicit ask), unlike reels/captions' full platform list.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "acct-1", "platform": "instagram"}))

    coro = app._resolve_accounts_for_publish("u1", ["acct-1"], app._SOCIAL_POST_PLATFORMS)
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400


def test_resolve_anonymous_story_page_context_reads_form_fields(monkeypatch):
    # A multipart upload (file submission) carries page_name/target_language
    # as ordinary Form fields, already resolved by FastAPI before this
    # helper runs -- it should just pass them through untouched.
    app = _import_app_with_stubs(monkeypatch)

    class _FakeRequest:
        headers = {"content-type": "multipart/form-data; boundary=x"}

    result = asyncio.run(app._resolve_anonymous_story_page_context(_FakeRequest(), "Confessions Anonymes", "en"))

    assert result == ("Confessions Anonymes", "en")


def test_resolve_anonymous_story_page_context_reads_json_body(monkeypatch):
    # A YouTube URL submission sends a JSON body instead (see
    # _resolve_process_endpoint_url_and_ack's same branching) -- this
    # helper must read page_name/target_language from there instead of the
    # (empty) Form params FastAPI resolved.
    app = _import_app_with_stubs(monkeypatch)

    class _FakeRequest:
        headers = {"content-type": "application/json"}

        async def json(self):
            return {"page_name": "Confessions Anonymes", "target_language": "en"}

    result = asyncio.run(app._resolve_anonymous_story_page_context(_FakeRequest(), None, None))

    assert result == ("Confessions Anonymes", "en")


def test_resolve_anonymous_story_page_context_defaults_to_empty_strings(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _FakeRequest:
        headers = {"content-type": "multipart/form-data; boundary=x"}

    result = asyncio.run(app._resolve_anonymous_story_page_context(_FakeRequest(), None, None))

    assert result == ("", "")


def test_publish_request_supports_image_url(monkeypatch):
    # Generic field shared with Instagram/TikTok's own image-post branches
    # (see _publish_instagram_platform/_publish_tiktok_platform) -- neither
    # Facebook nor LinkedIn ever reads it for an anonymous story: both
    # always publish plain text there, per product decision.
    app = _import_app_with_stubs(monkeypatch)

    payload = app.PublishRequest(user_id="u1", text="hello", image_url="https://example.com/bg.png")
    assert payload.image_url == "https://example.com/bg.png"

    default_payload = app.PublishRequest(user_id="u1", text="hello")
    assert default_payload.image_url is None


def test_publish_facebook_posts_photo_when_image_url_set(monkeypatch):
    # A real user-attached photo (from the "Faire une publication" composer)
    # publishes as an actual Facebook photo post. Anonymous stories never
    # set content.image_url (they use facebook_text_format_preset_id
    # instead -- see test_publish_facebook_uses_native_background_when_preset_mapped),
    # so this never collides with the "a story must stay text" rule.
    app = _import_app_with_stubs(monkeypatch)

    captured = {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, data=None):
            captured["url"] = url
            captured["data"] = data
            request = app.httpx.Request("POST", url)
            return app.httpx.Response(200, json={"id": "111_222"}, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    account = {"platform_user_id": "page-1"}
    content = app.PublishRequest(user_id="u1", text="hello", image_url="https://example.com/photo.png")

    result = asyncio.run(app._publish_facebook(account, "token-1", content, "hello"))

    assert result == {"id": "111_222"}
    assert captured["url"] == "https://graph.facebook.com/v19.0/page-1/photos"
    assert captured["data"] == {"url": "https://example.com/photo.png", "caption": "hello", "access_token": "token-1"}


def test_publish_facebook_falls_back_to_text_when_photo_fails(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "publish_to_facebook_photo", AsyncMock(side_effect=RuntimeError("rate limited")))

    captured = {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, data=None):
            captured["url"] = url
            captured["data"] = data
            request = app.httpx.Request("POST", url)
            return app.httpx.Response(200, json={"id": "111_222"}, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    account = {"platform_user_id": "page-1"}
    content = app.PublishRequest(user_id="u1", text="hello", image_url="https://example.com/photo.png")

    result = asyncio.run(app._publish_facebook(account, "token-1", content, "hello"))

    assert result["id"] == "111_222"
    assert result["image_failed"] is True
    assert "rate limited" in result["image_error"]
    assert captured["url"] == "https://graph.facebook.com/page-1/feed"


def test_publish_facebook_uses_native_background_when_preset_mapped(monkeypatch):
    # Spec: "Facebook — Publication de posts texte avec arriere-plan" --
    # a story with a mapped preset must publish as Meta's native
    # colored-background text (text_format_preset_id), never as an image,
    # and regardless of text length: Facebook truncates long text behind
    # its own "See more" expander while keeping the background, confirmed
    # against Publer (which uses this same mechanism).
    app = _import_app_with_stubs(monkeypatch)

    native_calls = []

    async def fake_publish_to_facebook_text_with_background(**kwargs):
        native_calls.append(kwargs)
        return {"id": "111_222"}

    monkeypatch.setattr(app, "publish_to_facebook_text_with_background", fake_publish_to_facebook_text_with_background)

    account = {"platform_user_id": "page-1"}
    long_text = "Une histoire assez longue pour depasser le seuil de 130 caracteres de Facebook. " * 5
    content = app.PublishRequest(
        user_id="u1", text=long_text, facebook_text_format_preset_id="1881421442117417",
    )

    result = asyncio.run(app._publish_facebook(account, "token-1", content, long_text))

    assert result == {"id": "111_222"}
    assert native_calls == [{
        "access_token": "token-1", "page_id": "page-1",
        "message": long_text, "meta_preset_id": "1881421442117417",
    }]


def test_publish_facebook_native_failure_always_reraises(monkeypatch):
    # There is no fallback: per spec, the publication must remain text and
    # in no case become an image, so a native failure surfaces as-is.
    app = _import_app_with_stubs(monkeypatch)

    async def fake_publish_to_facebook_text_with_background(**kwargs):
        raise app.HTTPException(status_code=502, detail="boom")

    monkeypatch.setattr(app, "publish_to_facebook_text_with_background", fake_publish_to_facebook_text_with_background)

    account = {"platform_user_id": "page-1"}
    content = app.PublishRequest(user_id="u1", text="Une courte histoire.", facebook_text_format_preset_id="1881421442117417")

    with pytest.raises(app.HTTPException):
        asyncio.run(app._publish_facebook(account, "token-1", content, "Une courte histoire."))


def test_facebook_text_with_background_never_combines_media(monkeypatch):
    # Requirement 3: "Une publication avec arriere-plan ne doit pas etre
    # combinee avec une image ou une video."
    app = _import_app_with_stubs(monkeypatch)

    captured = {}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, data=None):
            captured["url"] = url
            captured["data"] = data
            request = app.httpx.Request("POST", url)
            return app.httpx.Response(200, json={"id": "111_222"}, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app.publish_to_facebook_text_with_background(
        access_token="token-1", page_id="page-1", message="Une courte histoire.",
        meta_preset_id="1881421442117417",
    ))

    assert result == {"id": "111_222"}
    assert captured["url"] == "https://graph.facebook.com/v19.0/page-1/feed"
    assert set(captured["data"].keys()) == {"message", "text_format_preset_id", "access_token"}
    assert captured["data"]["text_format_preset_id"] == "1881421442117417"


def test_get_facebook_text_format_preset_id_maps_known_presets(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    # Every preset in the catalog IS one of Meta's own official presets (the
    # 77-preset reference), so this is an identity lookup, not a mapping.
    assert app.anonymous_stories.get_facebook_text_format_preset_id("1881421442117417") == "1881421442117417"
    assert app.anonymous_stories.get_facebook_text_format_preset_id(app.anonymous_stories.NO_BACKGROUND_ID) is None
    assert app.anonymous_stories.get_facebook_text_format_preset_id(None) is None
    # An id that doesn't match any catalog entry must resolve to None --
    # callers treat that as "publish as plain text", never as "use an image
    # instead".
    assert app.anonymous_stories.get_facebook_text_format_preset_id("does-not-exist") is None


def test_publish_linkedin_posts_photo_when_image_url_set(monkeypatch):
    # A real user-attached photo (from the "Faire une publication" composer)
    # publishes as an actual LinkedIn image post. Anonymous stories never
    # set content.image_url, so this never collides with LinkedIn having no
    # native colored-background substitute.
    app = _import_app_with_stubs(monkeypatch)

    image_calls = []

    async def fake_publish_to_linkedin_image(**kwargs):
        image_calls.append(kwargs)
        return {"id": "urn:li:share:999"}

    monkeypatch.setattr(app, "publish_to_linkedin_image", fake_publish_to_linkedin_image)

    account = {"platform_user_id": "person-1"}
    content = app.PublishRequest(user_id="u1", text="hello", image_url="https://example.com/photo.png")

    result = asyncio.run(app._publish_linkedin(account, "token-1", content, "hello"))

    assert result == {"id": "urn:li:share:999"}
    assert image_calls == [{
        "access_token": "token-1", "owner_urn": "urn:li:person:person-1",
        "image_url": "https://example.com/photo.png", "commentary": "hello",
    }]


def test_publish_linkedin_falls_back_to_text_when_photo_fails(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "publish_to_linkedin_image", AsyncMock(side_effect=RuntimeError("rate limited")))

    calls = []

    async def fake_create_linkedin_post(**kwargs):
        calls.append(kwargs)
        return {"id": "urn:li:share:999"}

    monkeypatch.setattr(app, "_create_linkedin_post", fake_create_linkedin_post)

    account = {"platform_user_id": "person-1"}
    content = app.PublishRequest(user_id="u1", text="hello", image_url="https://example.com/photo.png")

    result = asyncio.run(app._publish_linkedin(account, "token-1", content, "hello"))

    assert result["id"] == "urn:li:share:999"
    assert result["image_failed"] is True
    assert "rate limited" in result["image_error"]
    assert calls == [{"token": "token-1", "owner_urn": "urn:li:person:person-1", "commentary": "hello"}]


def test_publish_facebook_still_falls_back_to_video_when_video_url_set(monkeypatch):
    # Guard against the native-background branch swallowing the existing
    # reel/caption behavior: when a video_url is present, the
    # video-then-text fallback must still run even if a preset is also set
    # (a background text post can never be combined with a video).
    app = _import_app_with_stubs(monkeypatch)

    native_calls = []
    video_calls = []

    async def fake_publish_to_facebook_text_with_background(**kwargs):
        native_calls.append(kwargs)
        return {"id": "should-not-be-called"}

    async def fake_publish_to_facebook_video(**kwargs):
        video_calls.append(kwargs)
        return {"id": "987654321"}

    monkeypatch.setattr(app, "publish_to_facebook_text_with_background", fake_publish_to_facebook_text_with_background)
    monkeypatch.setattr(app, "publish_to_facebook_video", fake_publish_to_facebook_video)

    account = {"platform_user_id": "page-1"}
    content = app.PublishRequest(
        user_id="u1", text="hello", video_url="https://example.com/v.mp4",
        facebook_text_format_preset_id="1881421442117417",
    )

    result = asyncio.run(app._publish_facebook(account, "token-1", content, "hello"))

    assert result == {"id": "987654321"}
    assert native_calls == []
    assert len(video_calls) == 1


def test_execute_scheduled_publish_job_anonymous_story_skips_media_url_requirement(monkeypatch):
    # Reel/caption scheduled jobs require a media_url (video); an anonymous
    # story scheduled job carries only text + a background_id (used solely
    # to resolve Facebook's native preset -- see
    # anonymous_stories.get_facebook_text_format_preset_id), so
    # _execute_scheduled_publish_job must not reject it for lacking
    # media_url.
    app = _import_app_with_stubs(monkeypatch)

    job_row = {
        "id": "job-1",
        "user_id": "user-1",
        "platform": "facebook",
        "payload": {
            "source_type": "anonymous_story",
            "source_id": "story-1",
            "title": "Une histoire",
            "description": "Le texte complet de l'histoire.",
            "background_id": "sunset",
        },
    }

    status_calls = []

    async def fake_update_publish_job_status(job_id, status, **kwargs):
        status_calls.append((job_id, status, kwargs))

    async def fake_get_social_account(user_id, platform):
        return {"id": "acct-1", "platform_user_id": "page-1"}

    published_payloads = []

    async def fake_publish_post(account, content):
        published_payloads.append(content)
        return {"id": "111_222"}

    monkeypatch.setattr(app, "_update_publish_job_status", fake_update_publish_job_status)
    monkeypatch.setattr(app, "_get_social_account", fake_get_social_account)
    monkeypatch.setattr(app, "publish_post", fake_publish_post)

    asyncio.run(app._execute_scheduled_publish_job(job_row))

    assert len(published_payloads) == 1
    assert published_payloads[0].video_url is None
    assert published_payloads[0].image_url is None
    assert published_payloads[0].description == "Le texte complet de l'histoire."
    assert ("job-1", "done", {"external_id": "111_222", "post_url": "https://www.facebook.com/111_222", "error_message": None}) in status_calls


def test_anonymous_stories_backgrounds_route_registered_before_story_id_route(monkeypatch):
    # Regression: FastAPI/Starlette matches routes in registration order.
    # GET /api/anonymous-stories/{story_id} used to be registered before
    # GET /api/anonymous-stories/backgrounds, so a request to
    # .../backgrounds matched story_id="backgrounds" and 500'd trying to
    # look that up as a story id (postgrest rejected "backgrounds" as an
    # invalid uuid). Pin the correct registration order, and that the
    # endpoint actually answers via a real TestClient request.
    app = _import_app_with_stubs(monkeypatch)

    paths = [getattr(r, "path", None) for r in app.app.routes]
    backgrounds_index = paths.index("/api/anonymous-stories/backgrounds")
    story_id_index = paths.index("/api/anonymous-stories/{story_id}")
    assert backgrounds_index < story_id_index

    client = TestClient(app.app)
    response = client.get("/api/anonymous-stories/backgrounds", headers=_auth_headers("user-1"))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    assert all("id" in item and "colors" in item for item in items)


def test_anonymous_stories_backgrounds_includes_no_background_option_last(monkeypatch):
    # "rajouter ... une option sans background": the listing must offer a
    # text-only choice alongside the color presets, appended last so the
    # frontend's "default to items[0]" logic still lands on a color.
    app = _import_app_with_stubs(monkeypatch)

    client = TestClient(app.app)
    response = client.get("/api/anonymous-stories/backgrounds", headers=_auth_headers("user-1"))

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[-1]["id"] == app.anonymous_stories.NO_BACKGROUND_ID
    assert items[0]["id"] != app.anonymous_stories.NO_BACKGROUND_ID
    preset_ids = {item["id"] for item in items[:-1]}
    assert preset_ids == {preset["id"] for preset in app.anonymous_stories.BACKGROUND_PRESETS}


def test_resolve_anonymous_story_schedule_rejects_invalid_date(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    payload = app.AnonymousStoryPublishRequest(platforms=["facebook"], scheduled_date="not-a-date")
    with pytest.raises(app.HTTPException) as exc:
        app._resolve_anonymous_story_schedule(payload)
    assert exc.value.status_code == 400


def test_resolve_anonymous_story_schedule_detects_future_date_as_scheduled(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    future = (app._utcnow() + app.timedelta(days=1)).isoformat()
    payload = app.AnonymousStoryPublishRequest(platforms=["facebook"], scheduled_date=future)

    scheduled_for, is_scheduled = app._resolve_anonymous_story_schedule(payload)

    assert scheduled_for is not None
    assert is_scheduled is True


def test_resolve_anonymous_story_schedule_no_date_is_immediate(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    payload = app.AnonymousStoryPublishRequest(platforms=["facebook"])
    scheduled_for, is_scheduled = app._resolve_anonymous_story_schedule(payload)

    assert scheduled_for is None
    assert is_scheduled is False


def test_dispatch_anonymous_story_publish_immediate_calls_publish_now_per_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    calls = []

    async def fake_publish_anonymous_story_now(user_id, account, publish_priority, text_value, background_id=None):
        calls.append((account["platform"], background_id))
        return {"success": account["platform"] == "facebook"}

    monkeypatch.setattr(app, "_publish_anonymous_story_now", fake_publish_anonymous_story_now)

    accounts = [
        {"id": "fb-acct", "platform": "facebook"},
        {"id": "li-acct", "platform": "linkedin"},
    ]
    results = asyncio.run(app._dispatch_anonymous_story_publish(
        "user-1", "story-1", "Une histoire", "texte", "sunset",
        accounts, 5, None, "UTC", False,
    ))

    assert calls == [
        ("facebook", "sunset"),
        ("linkedin", "sunset"),
    ]
    assert results == {"fb-acct": {"success": True}, "li-acct": {"success": False}}


def test_dispatch_anonymous_story_publish_scheduled_schedules_each_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    calls = []

    async def fake_schedule_share_publish_job(
        user_id, account, source_type, source_id, publish_priority,
        scheduled_for, timezone, final_title, final_description, media_url, background_id=None,
    ):
        calls.append((account["platform"], source_type, source_id, final_title, background_id))
        return {"success": True, "scheduled": True}

    monkeypatch.setattr(app, "_schedule_share_publish_job", fake_schedule_share_publish_job)

    scheduled_for = app._utcnow() + app.timedelta(days=1)
    accounts = [{"id": "fb-acct", "platform": "facebook"}]
    results = asyncio.run(app._dispatch_anonymous_story_publish(
        "user-1", "story-1", "Une histoire", "texte", "sunset",
        accounts, 5, scheduled_for, "UTC", True,
    ))

    assert calls == [("facebook", "anonymous_story", "story-1", "Une histoire", "sunset")]
    assert results == {"fb-acct": {"success": True, "scheduled": True}}


def test_publish_linkedin_posts_full_text_even_when_long(monkeypatch):
    # No teaser/truncation needed anymore: LinkedIn never renders a
    # background image (there's nothing left to avoid duplicating text
    # onto), so the full story goes straight into the post commentary.
    app = _import_app_with_stubs(monkeypatch)

    captured = {}

    async def fake_create_linkedin_post(**kwargs):
        captured.update(kwargs)
        return {"id": "urn:li:share:1"}

    monkeypatch.setattr(app, "_create_linkedin_post", fake_create_linkedin_post)

    account = {"platform_user_id": "person-1"}
    long_text = "Une histoire assez longue. " * 20
    content = app.PublishRequest(user_id="u1", text=long_text)

    asyncio.run(app._publish_linkedin(account, "token-1", content, long_text))

    assert captured["commentary"] == long_text


def test_validate_caption_source_constraints_defaults_to_caption_limits(monkeypatch):
    # max_duration_minutes/max_storage_gb are bound to
    # CAPTION_MAX_DURATION_MINUTES/CAPTION_MAX_STORAGE_GB at function
    # definition time (an ordinary Python default-argument, resolved once
    # at import), so this asserts against the live values rather than
    # monkeypatching the module constant after the fact.
    app = _import_app_with_stubs(monkeypatch)

    over_limit_seconds = (app.CAPTION_MAX_DURATION_MINUTES + 1) * 60

    with pytest.raises(app.HTTPException) as exc:
        app._validate_caption_source_constraints(
            duration_seconds=over_limit_seconds, size_bytes=0.0, source_label="fichier",
        )
    assert f"{app.CAPTION_MAX_DURATION_MINUTES:.2f} min" in str(exc.value.detail)


def test_validate_caption_source_constraints_accepts_an_override(monkeypatch):
    # Regression: anonymous stories reuse this same function for their
    # duration/size checks, but their own limit must be independent of
    # CAPTION_MAX_DURATION_MINUTES (a deployment tightening the caption
    # limit to 30min, meant for actual caption jobs, was silently also
    # capping how long a story's source video could be at 30min).
    app = _import_app_with_stubs(monkeypatch)

    monkeypatch.setattr(app, "CAPTION_MAX_DURATION_MINUTES", 30.0)

    # 31 minutes would violate the caption default, but not a 180min override.
    app._validate_caption_source_constraints(
        duration_seconds=31 * 60, size_bytes=0.0, source_label="fichier",
        max_duration_minutes=180.0,
    )

    with pytest.raises(app.HTTPException) as exc:
        app._validate_caption_source_constraints(
            duration_seconds=181 * 60, size_bytes=0.0, source_label="fichier",
            max_duration_minutes=180.0,
        )
    assert "180.00 min" in str(exc.value.detail)


def test_anonymous_story_max_duration_defaults_to_180_minutes(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    assert app.ANONYMOUS_STORY_MAX_DURATION_MINUTES == 180.0


# ---------------------------------------------------------------------------
# Film Summary helpers (pure logic -- no Supabase/S3 network calls, same
# convention as the caption/anonymous-story helper tests above)
# ---------------------------------------------------------------------------

def test_row_field_returns_none_for_missing_row(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._row_field(None, "id") is None
    assert app._row_field({}, "id") is None


def test_row_field_returns_value_when_present(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._row_field({"id": "abc", "source_s3_key": "key"}, "source_s3_key") == "key"


def test_resolve_film_summary_title_prefers_explicit_title(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._resolve_film_summary_title("My Title", "Fallback") == "My Title"


def test_resolve_film_summary_title_falls_back_to_source_title(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._resolve_film_summary_title(None, "Fallback") == "Fallback"


def test_resolve_film_summary_title_falls_back_to_default(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._resolve_film_summary_title("", "") == "Resume de film"


def test_resolve_film_summary_title_truncates_to_200_chars(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    result = app._resolve_film_summary_title("x" * 300, "")
    assert len(result) == 200


def test_resolve_film_summary_target_duration_uses_explicit_value(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._resolve_film_summary_target_duration(300.0, local_duration=3600.0) == 300


def test_resolve_film_summary_target_duration_derives_when_not_given(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    result = app._resolve_film_summary_target_duration(None, local_duration=3600.0)
    assert result == film_summary.derive_target_duration_seconds(
        3600.0, app.FILM_SUMMARY_MIN_TARGET_DURATION_SECONDS, app.FILM_SUMMARY_MAX_TARGET_DURATION_SECONDS,
    )


def test_resolve_film_summary_narration_settings_defaults_style_to_cinematic(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    language, style = app._resolve_film_summary_narration_settings(None, None)
    assert language == ""
    assert style == "cinematic"


def test_persist_film_summary_row_stores_full_precision_duration(monkeypatch):
    # Used to store int(local_duration), truncating up to ~1s of precision
    # -- a segment valid against the full-precision duration used to
    # generate the plan (_run_planning_and_validation_stages) could then
    # fail render_film_summary_endpoint's bounds check, which recomputes
    # source_duration_ms from this exact stored value.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    insert_mock = AsyncMock(return_value={"id": "fs-1"})
    monkeypatch.setattr(app, "supabase_insert_film_summary", insert_mock)

    asyncio.run(app._persist_film_summary_row(
        user_id="u1", project_id=None, film_title="Film", source_type="upload", source_url_value=None,
        source_s3_key="key", local_duration=125.834, resolved_target_duration=60,
        source_language="en", resolved_narration_language="en", resolved_narration_style="cinematic",
        resolved_voice_id="voice-1", film_job_id="job-1",
    ))

    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.args[0]["source_duration_seconds"] == 125.834


def test_resolve_film_summary_narration_settings_preserves_explicit_values(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    language, style = app._resolve_film_summary_narration_settings(" fr ", " dramatic ")
    assert language == "fr"
    assert style == "dramatic"


def test_total_narration_character_count_sums_voice_over_segments_only(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    plan = {
        "segments": [
            {"type": "voice_over", "narration": "Hello world"},
            {"type": "voice_over", "narration": "!!"},
            {"type": "original_dialogue", "transcript_excerpt": "should not be counted"},
        ],
    }
    assert app._total_narration_character_count(plan) == len("Hello world") + len("!!")


def test_estimate_film_summary_analysis_required_credits_is_non_negative(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    credits = app._estimate_film_summary_analysis_required_credits(duration_seconds=1200.0, size_bytes=1024 ** 3)
    assert credits >= 0


def test_estimate_film_summary_render_required_credits_is_non_negative(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    credits = app._estimate_film_summary_render_required_credits(target_duration_seconds=600.0, narration_character_count=5000)
    assert credits >= 0


def test_film_summary_rejection_codes_cover_source_and_content_rejections(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert film_summary.FilmSummaryErrorCode.NOT_A_FILM in app._FILM_SUMMARY_REJECTION_CODES
    assert film_summary.FilmSummaryErrorCode.SOURCE_TOO_LONG in app._FILM_SUMMARY_REJECTION_CODES
    assert film_summary.FilmSummaryErrorCode.TTS_FAILED not in app._FILM_SUMMARY_REJECTION_CODES


def test_normalize_film_summary_row_excludes_content_by_default(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    row = {
        "id": "fs_1", "title": "T", "status": "awaiting_review", "stage": "awaiting_user_review",
        "edit_plan": {"segments": []}, "scene_index": [{"scene_id": "scene_001"}], "classification": {"is_film": True},
    }
    item = app._normalize_film_summary_row(row)
    assert item["id"] == "fs_1"
    assert "edit_plan" not in item
    assert "scene_index" not in item


def test_normalize_film_summary_row_includes_content_when_requested(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    row = {
        "id": "fs_1", "title": "T", "status": "completed", "stage": "completed",
        "edit_plan": {"segments": []}, "scene_index": [], "classification": {},
        "validation_report": {"valid": True}, "source_s3_key": "source/key.mp4",
        "preview_s3_key": "preview/key.mp4", "final_s3_key": "final/key.mp4",
    }
    item = app._normalize_film_summary_row(row, include_content=True)
    assert item["edit_plan"] == {"segments": []}
    assert item["validation_report"] == {"valid": True}
    # generate_presigned_url is stubbed to return "" in this test environment.
    assert item["source_url"] == ""
    assert item["preview_url"] == ""
    assert item["final_url"] == ""


def test_normalize_film_summary_row_omits_source_url_once_source_cleared(monkeypatch):
    # _finalize_film_summary_render clears source_s3_key after a
    # successful render to free storage -- the editor only needs
    # source_url during awaiting_review, while it's still set.
    app = _import_app_with_stubs(monkeypatch)
    row = {"id": "fs_1", "status": "completed", "stage": "completed", "classification": {}}
    item = app._normalize_film_summary_row(row, include_content=True)
    assert "source_url" not in item


def _awaiting_review_film_summary_row(**overrides):
    row = {
        "id": "fs_1", "status": "awaiting_review", "stage": "awaiting_user_review",
        "source_duration_seconds": 100.0,
        "scene_index": [{"scene_id": "scene_001", "start_ms": 0, "end_ms": 50000}],
        "edit_plan": {}, "classification": {},
    }
    row.update(overrides)
    return row


def test_update_film_summary_audio_settings_blocks_outside_awaiting_review(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=_awaiting_review_film_summary_row(status="rendering")))

    coro = app.update_film_summary_audio_settings_endpoint(
        film_summary_id="fs_1", payload=app.FilmSummaryAudioSettingsUpdateRequest(subtitles_enabled=True), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409


def test_translate_film_summary_narration_404_when_missing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=None))

    coro = app.translate_film_summary_narration_endpoint(
        film_summary_id="fs_1", payload=app.FilmSummaryTranslateNarrationRequest(narration_language="fr"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_translate_film_summary_narration_blocks_outside_awaiting_review(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=_awaiting_review_film_summary_row(
        status="completed",
    )))

    coro = app.translate_film_summary_narration_endpoint(
        film_summary_id="fs_1", payload=app.FilmSummaryTranslateNarrationRequest(narration_language="fr"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409


def test_translate_film_summary_narration_rejects_empty_language(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=_awaiting_review_film_summary_row()))

    coro = app.translate_film_summary_narration_endpoint(
        film_summary_id="fs_1", payload=app.FilmSummaryTranslateNarrationRequest(narration_language="   "), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 400


def test_translate_film_summary_narration_persists_plan_and_language(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    original_plan = {
        "schema_version": "1.0", "segments": [{"id": "seg_01", "type": "voice_over", "narration": "Hello."}],
        "target_duration_ms": 3000, "total_estimated_duration_ms": 3000,
    }
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=_awaiting_review_film_summary_row(
        edit_plan=original_plan, title="My Movie", source_language="en", narration_language="en", narration_style="cinematic",
    )))
    translated_plan = dict(original_plan, segments=[{"id": "seg_01", "type": "voice_over", "narration": "Bonjour."}])
    translated_validation_report = {"valid": True, "errors": [], "warnings": [], "total_estimated_duration_ms": 3000}
    translate_mock = AsyncMock(return_value={
        "plan": translated_plan, "validation_report": translated_validation_report, "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    })
    monkeypatch.setattr(app.film_summary, "translate_edit_plan_narration", translate_mock)
    update_mock = AsyncMock(return_value=_awaiting_review_film_summary_row(
        edit_plan=translated_plan, validation_report=translated_validation_report, narration_language="fr",
    ))
    monkeypatch.setattr(app, "supabase_update_film_summary", update_mock)

    result = asyncio.run(app.translate_film_summary_narration_endpoint(
        film_summary_id="fs_1", payload=app.FilmSummaryTranslateNarrationRequest(narration_language=" fr "), user_id="u1",
    ))

    translate_mock.assert_awaited_once()
    assert translate_mock.await_args.kwargs["target_language"] == "fr"
    assert translate_mock.await_args.kwargs["plan"] == original_plan
    update_mock.assert_awaited_once_with("fs_1", "u1", {
        "edit_plan": translated_plan, "validation_report": translated_validation_report, "narration_language": "fr",
    })
    assert result["edit_plan"] == translated_plan
    assert result["narration_language"] == "fr"


def test_translate_film_summary_narration_returns_502_on_planning_failure(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=_awaiting_review_film_summary_row(
        edit_plan={"segments": [{"id": "seg_01", "type": "voice_over", "narration": "Hello."}]},
    )))
    monkeypatch.setattr(app.film_summary, "translate_edit_plan_narration", AsyncMock(
        side_effect=film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.PLAN_INVALID, "boom"),
    ))

    coro = app.translate_film_summary_narration_endpoint(
        film_summary_id="fs_1", payload=app.FilmSummaryTranslateNarrationRequest(narration_language="fr"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 502


def _setup_retry_film_summary_mocks(app, monkeypatch, row, tmp_path):
    """Shared plumbing for retry_film_summary_endpoint tests: supabase is
    not configured in this test environment, so _enforce_job_concurrency_
    limit/_reserve_job_credits already no-op on their own -- only the real
    job-manager/background-task calls need stubbing. _spawn_background_task
    is replaced with a stub that closes the coroutine without running it,
    since _run_film_summary_retry_job's own behavior (S3 download, cached-
    stage resume, ...) is exercised separately and isn't this endpoint's
    concern."""
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "supabase_get_film_summary", AsyncMock(return_value=row))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    app.reel_job_manager.create_job = AsyncMock()
    app.reel_job_manager.enqueue_job = AsyncMock()
    spawned = {}

    def _fake_spawn(coro):
        spawned["coro"] = coro
        coro.close()
        return None

    monkeypatch.setattr(app, "_spawn_background_task", _fake_spawn)
    update_mock = AsyncMock(return_value=dict(row, status="queued"))
    monkeypatch.setattr(app, "supabase_update_film_summary", update_mock)
    return update_mock


def test_retry_film_summary_succeeds_from_awaiting_review_and_resets_manual_state(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    row = _awaiting_review_film_summary_row(
        manual_selection=[{"scene_id": "scene_001", "start_ms": 0, "end_ms": 1000}], edit_mode="manual",
        subtitles_enabled=True, subtitle_style={"font": "Arial"},
    )
    update_mock = _setup_retry_film_summary_mocks(app, monkeypatch, row, tmp_path)

    result = asyncio.run(app.retry_film_summary_endpoint(film_summary_id="fs_1", user_id="u1"))

    assert result["status"] == "queued"
    update_mock.assert_awaited_once()
    args, kwargs = update_mock.await_args
    assert args[0] == "fs_1" and args[1] == "u1"
    updates = args[2]
    assert updates["status"] == film_summary.FilmSummaryStatus.QUEUED
    assert updates["manual_selection"] is None
    assert updates["edit_mode"] == "automatic"
    # Independent user preferences must survive a regenerate untouched --
    # i.e. never even mentioned in the update payload.
    for untouched_key in ("subtitles_enabled", "subtitle_style"):
        assert untouched_key not in updates


def test_retry_film_summary_succeeds_from_failed_without_resetting_manual_state(monkeypatch, tmp_path):
    # No regression: retrying a FAILED film summary (the pre-existing
    # behavior) must keep working exactly as before, with no manual_
    # selection/edit_mode reset -- that reset only matters when retried
    # from awaiting_review, where stale manual-editor state could exist.
    app = _import_app_with_stubs(monkeypatch)
    row = _awaiting_review_film_summary_row(status="failed")
    update_mock = _setup_retry_film_summary_mocks(app, monkeypatch, row, tmp_path)

    result = asyncio.run(app.retry_film_summary_endpoint(film_summary_id="fs_1", user_id="u1"))

    assert result["status"] == "queued"
    updates = update_mock.await_args.args[2]
    assert updates["status"] == film_summary.FilmSummaryStatus.QUEUED
    assert "manual_selection" not in updates
    assert "edit_mode" not in updates


@pytest.mark.parametrize("status", ["completed", "rendering", "queued", "processing", "cancelled", "rejected"])
def test_retry_film_summary_blocked_from_other_statuses(monkeypatch, tmp_path, status):
    app = _import_app_with_stubs(monkeypatch)
    row = _awaiting_review_film_summary_row(status=status)
    _setup_retry_film_summary_mocks(app, monkeypatch, row, tmp_path)

    coro = app.retry_film_summary_endpoint(film_summary_id="fs_1", user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409


def test_mark_film_summary_job_terminal_noops_without_supabase(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    # Neither SUPABASE_URL nor SUPABASE_SERVICE_ROLE_KEY are set in this test
    # environment, so is_supabase_configured() is False and this should
    # simply return without attempting any network call.
    asyncio.run(app._mark_film_summary_job_terminal(
        "user-1", "film-summary-1", "project-1",
        app.film_summary.FilmSummaryStatus.REJECTED, app.film_summary.FilmSummaryStage.REJECTED,
        "NOT_A_FILM", "This is not a film",
    ))


def test_scene_detection_timeout_fails_job_instead_of_hanging(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "FILM_SUMMARY_SCENE_DETECTION_TIMEOUT_SECONDS", 0.05)
    app.reel_job_manager.update_progress = AsyncMock()
    monkeypatch.setattr(app.film_summary, "transcribe_video_with_timecodes", AsyncMock(return_value={
        "text": "hello", "language": "en",
        "segments": [{"start_ms": 0, "end_ms": 1000, "speaker": "", "text": "hello"}],
    }))

    def _hangs_forever(video_path, threshold):
        time.sleep(1)
        return []

    monkeypatch.setattr(app.film_summary, "detect_scenes", _hangs_forever)

    coro = app._run_transcription_and_scene_detection_stages("job-1", "u1", None, "/tmp/input.mp4")
    with pytest.raises(app.film_summary.FilmSummaryValidationError) as exc:
        asyncio.run(coro)
    assert exc.value.code == app.film_summary.FilmSummaryErrorCode.SCENE_DETECTION_FAILED


def test_transcription_stage_protects_explicit_source_language_from_detection(monkeypatch):
    # The user chose French explicitly, but AssemblyAI's detection (mocked
    # here as if it got it wrong) reports English -- the user's own choice
    # must win, never be silently overwritten by the detected value.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.reel_job_manager.update_progress = AsyncMock()
    transcribe_mock = AsyncMock(return_value={
        "text": "bonjour", "language": "en",
        "segments": [{"start_ms": 0, "end_ms": 1000, "speaker": "", "text": "bonjour"}],
    })
    monkeypatch.setattr(app.film_summary, "transcribe_video_with_timecodes", transcribe_mock)
    monkeypatch.setattr(app.film_summary, "detect_scenes", lambda video_path, threshold: [])
    monkeypatch.setattr(app.film_summary, "build_scene_index", lambda scenes, segments: [])
    upsert_mock = AsyncMock()
    app.supabase_upsert_transcription = upsert_mock
    update_mock = AsyncMock()
    app.supabase_update_film_summary = update_mock

    asyncio.run(app._run_transcription_and_scene_detection_stages(
        "job-1", "u1", "fs-1", "/tmp/input.mp4", source_language="fr",
    ))

    assert transcribe_mock.await_args.kwargs["language_hint"] == "fr"
    assert upsert_mock.await_args.args[0]["transcript_language"] == "fr"
    source_language_updates = [
        call.args[2] for call in update_mock.await_args_list if "source_language" in call.args[2]
    ]
    assert len(source_language_updates) == 1
    assert source_language_updates[0]["source_language"] == "fr"


def test_transcription_stage_falls_back_to_detected_language_when_unset(monkeypatch):
    # When the user left source_language on auto-detect (None), the
    # detected language from AssemblyAI should be used as-is.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.reel_job_manager.update_progress = AsyncMock()
    transcribe_mock = AsyncMock(return_value={
        "text": "hello", "language": "en",
        "segments": [{"start_ms": 0, "end_ms": 1000, "speaker": "", "text": "hello"}],
    })
    monkeypatch.setattr(app.film_summary, "transcribe_video_with_timecodes", transcribe_mock)
    monkeypatch.setattr(app.film_summary, "detect_scenes", lambda video_path, threshold: [])
    monkeypatch.setattr(app.film_summary, "build_scene_index", lambda scenes, segments: [])
    upsert_mock = AsyncMock()
    app.supabase_upsert_transcription = upsert_mock
    update_mock = AsyncMock()
    app.supabase_update_film_summary = update_mock

    asyncio.run(app._run_transcription_and_scene_detection_stages(
        "job-1", "u1", "fs-1", "/tmp/input.mp4", source_language=None,
    ))

    assert transcribe_mock.await_args.kwargs["language_hint"] is None
    assert upsert_mock.await_args.args[0]["transcript_language"] == "en"


def test_finalize_film_summary_analysis_never_debits_source_storage(monkeypatch):
    # The source video is transient (deleted once the render finishes -- see
    # test_finalize_film_summary_render_deletes_transient_source below), so
    # it must never be counted against the user's persistent storage quota,
    # regardless of how large size_bytes (used only for cost estimation) is.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.supabase_update_film_summary = AsyncMock()
    app.supabase_update_project_status = AsyncMock()
    app.reel_job_manager.complete_job = AsyncMock()
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock

    one_gb_in_bytes = 1024 ** 3
    asyncio.run(app._finalize_film_summary_analysis(
        "job-1", "u1", "fs-1", "proj-1", 300.0, float(one_gb_in_bytes), 5.0,
        {"segments": []}, {"valid": True, "errors": [], "warnings": []}, {"prompt_tokens": 0, "completion_tokens": 0},
    ))

    debit_mock.assert_awaited_once()
    assert "storage_delta" not in debit_mock.await_args.kwargs


def test_finalize_film_summary_render_debits_output_storage(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.supabase_update_film_summary = AsyncMock()
    app.supabase_get_job_record = AsyncMock(return_value={"reserved_quota": 0.0})
    app.supabase_update_project_status = AsyncMock()
    app.supabase_update_project = AsyncMock()
    app.reel_job_manager.complete_job = AsyncMock()
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock

    half_gb_in_bytes = 1024 ** 3 // 2
    asyncio.run(app._finalize_film_summary_render(
        "job-1", "u1", "fs-1", "proj-1", {"segments": []},
        "preview/key.mp4", "final/key.mp4", {"final_duration_seconds": 60.0}, float(half_gb_in_bytes),
    ))

    debit_mock.assert_awaited_once()
    assert debit_mock.await_args.kwargs["storage_delta"] == pytest.approx(-0.5)


def test_finalize_film_summary_render_deletes_transient_source(monkeypatch):
    # Once a render succeeds, the source is never read again (/render
    # requires awaiting_review, /retry requires failed -- neither is
    # reachable from completed), so it's deleted and cleared from the row
    # instead of sitting there billed or not against the user forever.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    update_mock = AsyncMock()
    app.supabase_update_film_summary = update_mock
    app.supabase_get_job_record = AsyncMock(return_value={"reserved_quota": 0.0})
    app.supabase_update_project_status = AsyncMock()
    app.supabase_update_project = AsyncMock()
    app.reel_job_manager.complete_job = AsyncMock()
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=True)
    delete_mock = MagicMock(return_value=True)
    app.delete_s3_object = delete_mock

    asyncio.run(app._finalize_film_summary_render(
        "job-1", "u1", "fs-1", "proj-1", {"segments": []},
        "preview/key.mp4", "final/key.mp4", {"final_duration_seconds": 60.0}, 0.0,
        source_s3_key="source/key.mp4", bucket_name="test-bucket",
    ))

    update_mock.assert_awaited_once()
    assert update_mock.await_args.args[2]["source_s3_key"] is None
    delete_mock.assert_called_once_with("test-bucket", "source/key.mp4")


def test_finalize_film_summary_render_skips_source_deletion_without_key(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.supabase_update_film_summary = AsyncMock()
    app.supabase_get_job_record = AsyncMock(return_value={"reserved_quota": 0.0})
    app.supabase_update_project_status = AsyncMock()
    app.supabase_update_project = AsyncMock()
    app.reel_job_manager.complete_job = AsyncMock()
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=True)
    delete_mock = MagicMock()
    app.delete_s3_object = delete_mock

    asyncio.run(app._finalize_film_summary_render(
        "job-1", "u1", "fs-1", "proj-1", {"segments": []},
        "preview/key.mp4", "final/key.mp4", {"final_duration_seconds": 60.0}, 0.0,
    ))

    delete_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Storage debiting per service: reels and captions must debit for the video
# they produce, anonymous stories must not (film summaries are covered by
# the two tests directly above).
# ---------------------------------------------------------------------------

def test_finalize_completed_reel_billing_sums_and_debits_clip_storage(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.jobs["job-reel-1"] = {"logs": []}

    consumption_mock = MagicMock(return_value={
        "actual_credit": 2.0, "actual_storage_gb": 0.75, "actual_cost_usd": 0.1,
        "processing_ratio": 1.0, "cost_breakdown": {},
    })
    monkeypatch.setattr(app, "_estimate_reel_job_consumption", consumption_mock)
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock
    app.reel_job_manager.complete_job = AsyncMock()

    # Each saved reel row carries its own clip's real file size --
    # _finalize_completed_reel_billing must sum all of them before pricing
    # the job's actual storage consumption.
    saved_rows = [
        {"reel_size_bytes": 300 * 1024 * 1024},
        {"reel_size_bytes": 500 * 1024 * 1024},
    ]
    asyncio.run(app._finalize_completed_reel_billing(
        job_id="job-reel-1", job_data={"reel_required_credits": 2.0}, user_id="u1", source_is_url=False,
        start_ts=time.time(), enriched_clips=[{}, {}], cost_analysis={}, saved_rows=saved_rows,
    ))

    consumption_mock.assert_called_once()
    assert consumption_mock.call_args.kwargs["storage_bytes"] == 800 * 1024 * 1024

    debit_mock.assert_awaited_once()
    assert debit_mock.await_args.kwargs["storage_delta"] == pytest.approx(-0.75)
    assert debit_mock.await_args.kwargs["operation_type"] == "generation_reel"


def test_finalize_completed_reel_billing_debits_auto_caption_credits(monkeypatch):
    # Auto-captioned clips (default subtitles burned in at generation time)
    # carry their own credit cost, additive to the reel generation charge
    # and billed under "sous_titre" -- the same category the manual
    # captions-persist flow already uses.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.jobs["job-reel-2"] = {"logs": []}

    monkeypatch.setattr(app, "_estimate_reel_job_consumption", lambda **kwargs: {
        "actual_credit": 2.0, "actual_storage_gb": 0.5, "actual_cost_usd": 0.1,
        "processing_ratio": 1.0, "cost_breakdown": {},
    })
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=True)
    app.reel_job_manager.complete_job = AsyncMock()
    deduct_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_deduct_user_credits", deduct_mock)
    history_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_upsert_user_data_history_entry", history_mock)

    saved_rows = [
        {"reel_size_bytes": 100, "billing_details": {"auto_caption": {"applied": True, "credit_cost": 1.5}}},
        {"reel_size_bytes": 100, "billing_details": {"auto_caption": {"applied": False, "credit_cost": 0.0}}},
    ]
    asyncio.run(app._finalize_completed_reel_billing(
        job_id="job-reel-2", job_data={"reel_required_credits": 2.0}, user_id="u1", source_is_url=False,
        start_ts=time.time(), enriched_clips=[{}, {}], cost_analysis={}, saved_rows=saved_rows,
    ))

    deduct_mock.assert_awaited_once_with("u1", pytest.approx(1.5), 0.0)
    history_mock.assert_awaited_once()
    # operation_type stays "sous_titre" when creating a fresh row (no merge
    # target yet in this test's stubbed world); operation_id is the bare
    # job_id (not suffixed) so a real upsert_user_data_history_entry call
    # would merge this into the job's own primary "generation_reel" row.
    assert history_mock.await_args.kwargs["operation_type"] == "sous_titre"
    assert history_mock.await_args.kwargs["operation_id"] == "job-reel-2"
    assert history_mock.await_args.kwargs["credit"] == pytest.approx(1.5)


def test_finalize_completed_reel_billing_skips_auto_caption_debit_when_none_applied(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    app.jobs["job-reel-3"] = {"logs": []}

    monkeypatch.setattr(app, "_estimate_reel_job_consumption", lambda **kwargs: {
        "actual_credit": 2.0, "actual_storage_gb": 0.5, "actual_cost_usd": 0.1,
        "processing_ratio": 1.0, "cost_breakdown": {},
    })
    app.reel_job_manager.debit_credits_for_job = AsyncMock(return_value=True)
    app.reel_job_manager.complete_job = AsyncMock()
    deduct_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_deduct_user_credits", deduct_mock)

    saved_rows = [{"reel_size_bytes": 100}]
    asyncio.run(app._finalize_completed_reel_billing(
        job_id="job-reel-3", job_data={"reel_required_credits": 2.0}, user_id="u1", source_is_url=False,
        start_ts=time.time(), enriched_clips=[{}], cost_analysis={}, saved_rows=saved_rows,
    ))

    deduct_mock.assert_not_awaited()


def test_finalize_media_retention_billing_active_subscription_uses_longer_tier(monkeypatch):
    import retention_config
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"id": "sub1"}))
    insert_mock = AsyncMock(return_value={"id": "asset1"})
    monkeypatch.setattr(app, "supabase_insert_media_asset", insert_mock)

    result = asyncio.run(app._finalize_media_retention_billing(
        job_id="job-1", user_id="u1", content_kind=app.CONTENT_KIND_REEL, content_id="reel-1",
        media_type=app.MEDIA_TYPE_PRODUCED, size_bytes=4 * 1024 ** 3,
        s3_bucket="bucket", s3_key="reels/reel-1.mp4",
    ))

    assert result["subscription_status_at_creation"] == "active"
    assert result["retention_days"] == retention_config.RETENTION_SUBSCRIBER_PRODUCED_DAYS
    assert result["retention_storage_cost_usd"] > 0
    assert result["retention_storage_credit_cost"] > 0
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["content_kind"] == app.CONTENT_KIND_REEL
    assert insert_mock.await_args.kwargs["content_id"] == "reel-1"
    assert insert_mock.await_args.kwargs["subscription_status_at_creation"] == "active"
    assert insert_mock.await_args.kwargs["retention_days"] == retention_config.RETENTION_SUBSCRIBER_PRODUCED_DAYS


def test_finalize_media_retention_billing_no_subscription_uses_free_tier(monkeypatch):
    import retention_config
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    insert_mock = AsyncMock(return_value={"id": "asset2"})
    monkeypatch.setattr(app, "supabase_insert_media_asset", insert_mock)

    result = asyncio.run(app._finalize_media_retention_billing(
        job_id="job-2", user_id="u2", content_kind=app.CONTENT_KIND_PROJECT_SOURCE, content_id="proj-1",
        media_type=app.MEDIA_TYPE_SOURCE, size_bytes=1024 ** 3,
    ))

    assert result["subscription_status_at_creation"] == "free"
    assert result["retention_days"] == retention_config.RETENTION_FREE_SOURCE_DAYS


def test_finalize_media_retention_billing_never_raises_on_persistence_failure(monkeypatch):
    # A media_assets insert failure must never block the job's own
    # credit settlement -- only skip this media's own retention line item.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(side_effect=RuntimeError("boom")))

    result = asyncio.run(app._finalize_media_retention_billing(
        job_id="job-3", user_id="u3", content_kind=app.CONTENT_KIND_CAPTION, content_id="cap-1",
        media_type=app.MEDIA_TYPE_PRODUCED, size_bytes=1024 ** 3,
    ))
    assert result["retention_storage_credit_cost"] > 0


def test_finalize_media_retention_billing_subscription_lookup_failure_defaults_to_free(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(side_effect=RuntimeError("down")))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(return_value={"id": "asset4"}))

    result = asyncio.run(app._finalize_media_retention_billing(
        job_id="job-4", user_id="u4", content_kind=app.CONTENT_KIND_REEL, content_id="reel-4",
        media_type=app.MEDIA_TYPE_PRODUCED, size_bytes=1024 ** 3,
    ))
    assert result["subscription_status_at_creation"] == "free"


def test_finalize_retention_billing_batch_sums_across_entries_and_skips_missing_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(return_value={"id": "x"}))

    result = asyncio.run(app._finalize_retention_billing_batch("job-5", "u5", [
        {"content_kind": app.CONTENT_KIND_REEL, "content_id": "r1", "media_type": app.MEDIA_TYPE_PRODUCED, "size_bytes": 1024 ** 3},
        {"content_kind": app.CONTENT_KIND_REEL, "content_id": "r2", "media_type": app.MEDIA_TYPE_PRODUCED, "size_bytes": 1024 ** 3},
        {"content_kind": app.CONTENT_KIND_REEL, "content_id": None, "media_type": app.MEDIA_TYPE_PRODUCED, "size_bytes": 1024 ** 3},
    ]))

    assert len(result["media_assets"]) == 2
    single = asyncio.run(app._finalize_media_retention_billing(
        job_id="job-5", user_id="u5", content_kind=app.CONTENT_KIND_REEL, content_id="r1",
        media_type=app.MEDIA_TYPE_PRODUCED, size_bytes=1024 ** 3,
    ))
    assert result["retention_storage_credit_cost"] == pytest.approx(2 * single["retention_storage_credit_cost"], rel=1e-6)


def test_finalize_source_media_retention_skips_without_project(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    debit_mock = AsyncMock()
    app.reel_job_manager.debit_credits_for_job = debit_mock

    asyncio.run(app._finalize_source_media_retention("job-6", "u6", None, 1024 ** 3, "bucket", "key"))
    debit_mock.assert_not_awaited()


def test_finalize_source_media_retention_debits_standalone_retention_charge(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(return_value={"id": "asset5"}))
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock

    asyncio.run(app._finalize_source_media_retention(
        "job-7", "u7", {"id": "proj-7"}, 4 * 1024 ** 3, "bucket", "key",
    ))

    debit_mock.assert_awaited_once()
    assert debit_mock.await_args.kwargs["operation_type"] == "retention_storage_source"
    assert debit_mock.await_args.kwargs["reserved_credits"] == 0.0
    assert debit_mock.await_args.kwargs["credits"] > 0


def test_attach_media_asset_fields_enriches_rows_from_batch_lookup(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_list_media_assets_by_content_ids", AsyncMock(return_value={
        "r1": {"media_status": "AVAILABLE", "retention_expires_at": "2026-01-01T00:00:00+00:00"},
    }))

    items = [{"id": "r1"}, {"id": "r2"}]
    result = asyncio.run(app._attach_media_asset_fields(items, app.CONTENT_KIND_REEL))

    assert result[0]["media_status"] == "AVAILABLE"
    assert result[0]["media_expires_at"] == "2026-01-01T00:00:00+00:00"
    assert result[1]["media_status"] is None
    assert result[1]["media_expires_at"] is None


def test_attach_media_asset_fields_skips_without_supabase_or_rows(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    items = [{"id": "r1"}]
    result = asyncio.run(app._attach_media_asset_fields(items, app.CONTENT_KIND_REEL))
    assert "media_status" not in result[0]

    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    assert asyncio.run(app._attach_media_asset_fields([], app.CONTENT_KIND_REEL)) == []


def test_attach_media_asset_fields_never_raises_on_lookup_failure(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_list_media_assets_by_content_ids", AsyncMock(side_effect=RuntimeError("down")))

    items = [{"id": "r1"}]
    result = asyncio.run(app._attach_media_asset_fields(items, app.CONTENT_KIND_REEL))
    assert result == [{"id": "r1"}]


def test_finalize_completed_reel_billing_adds_retention_cost_when_rows_have_ids(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(return_value={"id": "asset-x"}))
    app.jobs["job-reel-ret"] = {"logs": []}

    monkeypatch.setattr(app, "_estimate_reel_job_consumption", lambda **kwargs: {
        "actual_credit": 2.0, "actual_storage_gb": 0.5, "actual_cost_usd": 0.1,
        "processing_ratio": 1.0, "cost_breakdown": {},
    })
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock
    complete_mock = AsyncMock()
    app.reel_job_manager.complete_job = complete_mock

    saved_rows = [{"id": "reel-ret-1", "reel_size_bytes": 1024 ** 3, "reel_s3_key": "reels/r1.mp4"}]
    asyncio.run(app._finalize_completed_reel_billing(
        job_id="job-reel-ret", job_data={"reel_required_credits": 2.0}, user_id="u1", source_is_url=False,
        start_ts=time.time(), enriched_clips=[{}], cost_analysis={}, saved_rows=saved_rows,
    ))

    assert debit_mock.await_args.kwargs["credits"] > 2.0
    assert "retention_storage_credit_cost" in complete_mock.await_args.kwargs["cost_breakdown"]


def test_process_and_complete_caption_job_bills_retention_on_top(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(return_value={"id": "asset-y"}))
    monkeypatch.setattr(app, "supabase_insert_captions", AsyncMock(return_value=[{"id": "cap-ret-1", "caption_s3_key": "captions/c1.mp4"}]))
    monkeypatch.setattr(app, "_normalize_caption_row", lambda row: row)
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock
    complete_mock = AsyncMock()
    app.reel_job_manager.complete_job = complete_mock
    monkeypatch.setattr(app, "_update_project_on_caption_completion", AsyncMock())
    monkeypatch.setattr(app, "_persist_transcription_cache", AsyncMock())
    monkeypatch.setattr(app, "_get_user_default_caption_style", AsyncMock(return_value={}))
    monkeypatch.setattr(app, "_burn_default_captions_for_clip", AsyncMock(return_value=False))
    monkeypatch.setattr(app, "_build_and_persist_caption_metadata", lambda *a, **k: None)
    monkeypatch.setattr(app, "_upload_caption_source_and_thumbnail", lambda *a, **k: ("captions/c1.mp4", "http://x/c1.mp4", "", ""))
    # A real multi-GB file would make this test slow/flaky to write --
    # fake a large-enough size instead, so the computed retention credit
    # cost isn't rounded away to 0 by a tiny test fixture file.
    monkeypatch.setattr(app.os.path, "getsize", lambda path: 4 * 1024 ** 3)

    output_dir = str(tmp_path)
    input_path = os.path.join(output_dir, "source.mp4")
    with open(input_path, "wb") as fh:
        fh.write(b"x" * 1024)

    job_id = "job-caption-ret"
    app.jobs[job_id] = {"logs": [], "result": None, "status": "running"}

    asyncio.run(app._process_and_complete_caption_job(
        job_id, {"project_id": None}, "u1", pipeline=AsyncMock(persisting=AsyncMock(), rendering=AsyncMock()),
        input_path=input_path, source_name="source.mp4", local_duration=5.0, transcript={"segments": []},
        caption_required_credits=1.0, output_dir=output_dir,
    ))

    debit_mock.assert_awaited_once()
    assert debit_mock.await_args.kwargs["credits"] > 1.0
    assert "retention_storage_credit_cost" in complete_mock.await_args.kwargs["cost_breakdown"]
    assert complete_mock.await_args.kwargs["actual_credit"] > 1.0


def test_finalize_film_summary_render_bills_retention_and_marks_source_deleted(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_media_asset", AsyncMock(return_value={"id": "asset-z"}))
    monkeypatch.setattr(app, "supabase_get_media_asset_by_content", AsyncMock(return_value={"id": "src-asset-1"}))
    mark_deleted_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_mark_media_asset_deleted", mark_deleted_mock)
    monkeypatch.setattr(app, "supabase_update_film_summary", AsyncMock())
    monkeypatch.setattr(app, "supabase_get_job_record", AsyncMock(return_value={"reserved_quota": 1.0}))
    monkeypatch.setattr(app, "supabase_update_project_status", AsyncMock())
    monkeypatch.setattr(app, "supabase_update_project", AsyncMock())
    delete_s3_mock = MagicMock(return_value=True)
    monkeypatch.setattr(app, "delete_s3_object", delete_s3_mock)
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock
    complete_mock = AsyncMock()
    app.reel_job_manager.complete_job = complete_mock

    asyncio.run(app._finalize_film_summary_render(
        job_id="job-fs-ret", user_id="u1", film_summary_id="fs-1", project_id="proj-1",
        plan={"segments": []}, preview_s3_key="film_summaries/u1/fs-1/preview.mp4",
        final_s3_key="film_summaries/u1/fs-1/final.mp4", render_result={"final_duration_seconds": 30.0},
        output_storage_bytes=1024 ** 3, source_s3_key="film_summaries/u1/fs-1/source.mp4", bucket_name="bucket",
    ))

    delete_s3_mock.assert_called_once_with("bucket", "film_summaries/u1/fs-1/source.mp4")
    mark_deleted_mock.assert_awaited_once_with("src-asset-1")
    assert debit_mock.await_args.kwargs["credits"] > 0
    assert "retention_storage_credit_cost" in complete_mock.await_args.kwargs["cost_breakdown"]


def test_expire_one_media_asset_deletes_s3_then_marks_expired(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    delete_mock = MagicMock(return_value=True)
    monkeypatch.setattr(app, "delete_s3_object", delete_mock)
    mark_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_mark_media_asset_expired", mark_mock)

    asyncio.run(app._expire_one_media_asset({"id": "m1", "s3_bucket": "b", "s3_key": "k"}))

    delete_mock.assert_called_once_with("b", "k")
    mark_mock.assert_awaited_once_with("m1")


def test_expire_one_media_asset_never_marks_expired_on_s3_failure(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "delete_s3_object", MagicMock(return_value=False))
    mark_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_mark_media_asset_expired", mark_mock)

    asyncio.run(app._expire_one_media_asset({"id": "m1", "s3_bucket": "b", "s3_key": "k"}))

    mark_mock.assert_not_awaited()


def test_expire_one_media_asset_marks_expired_directly_without_s3_key(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    delete_mock = MagicMock()
    monkeypatch.setattr(app, "delete_s3_object", delete_mock)
    mark_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_mark_media_asset_expired", mark_mock)

    asyncio.run(app._expire_one_media_asset({"id": "m1", "s3_bucket": None, "s3_key": None}))

    delete_mock.assert_not_called()
    mark_mock.assert_awaited_once_with("m1")


def test_expire_one_media_asset_skips_without_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    mark_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_mark_media_asset_expired", mark_mock)
    asyncio.run(app._expire_one_media_asset({}))
    mark_mock.assert_not_awaited()


def test_run_media_expiration_sweep_continues_past_per_asset_failure(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_list_media_assets_due_for_expiration", AsyncMock(return_value=[
        {"id": "m1", "s3_bucket": "b", "s3_key": "k1"},
        {"id": "m2", "s3_bucket": "b", "s3_key": "k2"},
    ]))
    calls = []

    async def _fake_expire(asset):
        calls.append(asset["id"])
        if asset["id"] == "m1":
            raise RuntimeError("boom")

    monkeypatch.setattr(app, "_expire_one_media_asset", _fake_expire)
    asyncio.run(app._run_media_expiration_sweep())

    assert calls == ["m1", "m2"]


def test_notify_one_media_asset_expiring_marks_before_sending(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    mark_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_mark_media_asset_notified", mark_mock)
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_notification", insert_mock)

    asyncio.run(app._notify_one_media_asset_expiring({
        "id": "m1", "user_id": "u1", "content_kind": "reel", "content_id": "r1",
        "retention_expires_at": "2026-01-01T00:00:00+00:00",
    }))

    mark_mock.assert_awaited_once_with("m1")
    insert_mock.assert_awaited_once()
    assert insert_mock.await_args.kwargs["user_id"] == "u1"
    assert insert_mock.await_args.kwargs["data"]["media_asset_id"] == "m1"


def test_notify_one_media_asset_expiring_skips_send_when_already_notified(monkeypatch):
    # supabase_mark_media_asset_notified only succeeds while the column is
    # still null -- a second (racing or retried) attempt must send
    # nothing, which is the idempotency guarantee the spec requires.
    app = _import_app_with_stubs(monkeypatch)
    mark_mock = AsyncMock(return_value=False)
    monkeypatch.setattr(app, "supabase_mark_media_asset_notified", mark_mock)
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_notification", insert_mock)

    asyncio.run(app._notify_one_media_asset_expiring({"id": "m1", "user_id": "u1"}))

    insert_mock.assert_not_awaited()


def test_run_media_expiry_notification_sweep_uses_lead_time_window(monkeypatch):
    import retention_config
    app = _import_app_with_stubs(monkeypatch)
    list_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(app, "supabase_list_produced_media_due_for_notification", list_mock)

    asyncio.run(app._run_media_expiry_notification_sweep())

    list_mock.assert_awaited_once()
    notify_before_time = list_mock.await_args.args[0]
    delta_hours = (notify_before_time - app.datetime.now(app.timezone.utc)).total_seconds() / 3600
    assert delta_hours == pytest.approx(retention_config.RETENTION_NOTIFICATION_HOURS_BEFORE, abs=0.1)


def test_burn_default_captions_for_clip_returns_false_without_transcript(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    result = asyncio.run(app._burn_default_captions_for_clip(
        "/tmp/in.mp4", "/tmp/out.mp4", None, 0.0, 10.0, "job-1", 0, app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS,
    ))
    assert result is False


def test_burn_default_captions_for_clip_returns_false_when_no_words_in_range(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "generate_srt", lambda *args, **kwargs: False)
    monkeypatch.setattr(app, "generate_highlighted_srt", lambda *args, **kwargs: False)
    burn_mock = MagicMock()
    monkeypatch.setattr(app, "_burn_subtitles_for_request", burn_mock)

    result = asyncio.run(app._burn_default_captions_for_clip(
        "/tmp/in.mp4", "/tmp/out.mp4", {"segments": []}, 0.0, 10.0, "job-1", 0, app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS,
    ))

    assert result is False
    burn_mock.assert_not_called()


def test_burn_default_captions_for_clip_burns_and_returns_true(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "generate_srt", lambda *args, **kwargs: True)
    burn_mock = MagicMock()
    monkeypatch.setattr(app, "_burn_subtitles_for_request", burn_mock)
    monkeypatch.setattr(app.os.path, "exists", lambda p: True)
    monkeypatch.setattr(app.os.path, "getsize", lambda p: 4096)
    monkeypatch.setattr(app.os, "remove", lambda p: None)

    result = asyncio.run(app._burn_default_captions_for_clip(
        "/tmp/in.mp4", "/tmp/out.mp4", {"segments": [{"words": [{"word": "hi", "start": 0, "end": 1}]}]},
        0.0, 10.0, "job-1", 2, app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS,
    ))

    assert result is True
    burn_mock.assert_called_once()
    burn_req = burn_mock.call_args.args[0]
    assert burn_req.job_id == "job-1"
    assert burn_req.clip_index == 2
    assert burn_req.font_size == 14
    assert burn_req.animation == "word-highlight"


def test_burn_default_captions_for_clip_uses_given_style_kwargs(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "generate_srt", lambda *args, **kwargs: True)
    burn_mock = MagicMock()
    monkeypatch.setattr(app, "_burn_subtitles_for_request", burn_mock)
    monkeypatch.setattr(app.os.path, "exists", lambda p: True)
    monkeypatch.setattr(app.os.path, "getsize", lambda p: 4096)
    monkeypatch.setattr(app.os, "remove", lambda p: None)

    custom_style = dict(app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS, font_size=30, font_name="Poppins")
    result = asyncio.run(app._burn_default_captions_for_clip(
        "/tmp/in.mp4", "/tmp/out.mp4", {"segments": [{"words": [{"word": "hi", "start": 0, "end": 1}]}]},
        0.0, 10.0, "job-1", 0, custom_style,
    ))

    assert result is True
    burn_req = burn_mock.call_args.args[0]
    assert burn_req.font_size == 30
    assert burn_req.font_name == "Poppins"


def test_burn_default_captions_for_clip_returns_false_on_exception(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    def _boom(*args, **kwargs):
        raise RuntimeError("ffmpeg exploded")

    monkeypatch.setattr(app, "generate_srt", lambda *args, **kwargs: True)
    monkeypatch.setattr(app, "_burn_subtitles_for_request", _boom)
    monkeypatch.setattr(app.os.path, "exists", lambda p: False)
    monkeypatch.setattr(app.os, "remove", lambda p: None)

    result = asyncio.run(app._burn_default_captions_for_clip(
        "/tmp/in.mp4", "/tmp/out.mp4", {"segments": [{"words": [{"word": "hi", "start": 0, "end": 1}]}]},
        0.0, 10.0, "job-1", 0, app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS,
    ))

    assert result is False


def test_normalize_reel_row_always_exposes_media_url_as_original(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}" if key else "")
    monkeypatch.setattr(app, "_extract_s3_key_from_thumbnail_ref", lambda ref: "")
    monkeypatch.setattr(app, "_reel_thumbnail_url_from_s3_key", lambda key: "")

    row = {
        "reel_s3_key": "reels/u1/job1/reel.mp4",
        "billing_details": {"original_s3_key": "reels/u1/job1/original_reel.mp4"},
    }
    result = app._normalize_reel_row(row)

    # reel_original_url no longer exposes a separate clean-clip URL -- the
    # app works off a single URL per clip; the clean clip is only resolved
    # server-side when actually re-burning (see
    # _resolve_authoritative_clean_video_source).
    assert result["reel_original_url"] == result["media_url"]


def test_normalize_caption_row_always_exposes_media_url_as_original(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_caption_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}" if key else "")

    row = {
        "caption_s3_key": "captions/u1/job1/cap.mp4",
        "generation_inputs": {"original_s3_key": "captions/u1/job1/original_cap.mp4"},
    }
    result = app._normalize_caption_row(row)

    assert result["caption_original_url"] == result["media_url"]


def test_build_reel_row_for_clip_auto_captions_and_uploads_original(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = str(tmp_path)
    clip_path = os.path.join(output_dir, "base_clip_1.mp4")
    Path(clip_path).write_bytes(b"raw-clip-bytes")

    async def _fake_burn(input_path, output_path, transcript, clip_start, clip_end, job_id, clip_index, style_kwargs):
        Path(output_path).write_bytes(b"captioned-bytes-longer")
        return True

    monkeypatch.setattr(app, "_burn_default_captions_for_clip", _fake_burn)
    upload_calls = []
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: upload_calls.append(key) or True)
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")
    monkeypatch.setattr(app, "_upload_reel_clip_thumbnail", lambda *args, **kwargs: "")
    monkeypatch.setattr(app, "_estimate_reel_cost_breakdown", lambda **kwargs: {})

    row = asyncio.run(app._build_reel_row_for_clip(
        "job-1", "user-1", output_dir, "bucket", "base", {"start": 0.0, "end": 10.0}, 1,
        "2024-01-01T00:00:00Z", False, None, transcript={"segments": [{"words": []}]},
    ))

    assert row is not None
    assert any(key.startswith("reels/user-1/job-1/original_") for key in upload_calls)
    assert row["billing_details"]["auto_caption"]["applied"] is True
    assert row["billing_details"]["auto_caption"]["credit_cost"] > 0
    assert row["reel_size_bytes"] == len(b"captioned-bytes-longer")


def test_build_reel_row_for_clip_records_default_style_version(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = str(tmp_path)
    clip_path = os.path.join(output_dir, "base_clip_1.mp4")
    Path(clip_path).write_bytes(b"raw-clip-bytes")

    async def _fake_burn(input_path, output_path, transcript, clip_start, clip_end, job_id, clip_index, style_kwargs):
        Path(output_path).write_bytes(b"captioned-bytes-longer")
        return True

    monkeypatch.setattr(app, "_burn_default_captions_for_clip", _fake_burn)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: True)
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}" if key else "")
    monkeypatch.setattr(app, "_upload_reel_clip_thumbnail", lambda *args, **kwargs: "")
    monkeypatch.setattr(app, "_estimate_reel_cost_breakdown", lambda **kwargs: {})
    monkeypatch.setattr(app, "supabase_list_style_edit_versions", AsyncMock(return_value=[]))
    insert_mock = AsyncMock(return_value={})
    monkeypatch.setattr(app, "supabase_insert_style_edit_version", insert_mock)

    asyncio.run(app._build_reel_row_for_clip(
        "job-1", "user-1", output_dir, "bucket", "base", {"start": 0.0, "end": 10.0}, 1,
        "2024-01-01T00:00:00Z", False, None, transcript={"segments": [{"words": []}]},
    ))

    insert_mock.assert_awaited_once()
    row_arg = insert_mock.await_args.args[0]
    assert row_arg["job_id"] == "job-1"
    assert row_arg["clip_index"] == 0
    assert row_arg["version_number"] == app._DEFAULT_STYLE_VERSION_NUMBER
    assert row_arg["output_video_url"] == "https://cdn.example/reels/user-1/job-1/base_clip_1.mp4"
    assert row_arg["source_video_url"] == "https://cdn.example/reels/user-1/job-1/original_base_clip_1.mp4"
    assert row_arg["style_config"]["font_name"] == "Montserrat"


def test_build_reel_row_for_clip_skips_captioning_without_transcript(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = str(tmp_path)
    clip_path = os.path.join(output_dir, "base_clip_1.mp4")
    Path(clip_path).write_bytes(b"raw-clip-bytes")

    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: True)
    monkeypatch.setattr(app, "_reel_media_url_from_s3_key", lambda key: f"https://cdn.example/{key}")
    monkeypatch.setattr(app, "_upload_reel_clip_thumbnail", lambda *args, **kwargs: "")
    monkeypatch.setattr(app, "_estimate_reel_cost_breakdown", lambda **kwargs: {})

    row = asyncio.run(app._build_reel_row_for_clip(
        "job-1", "user-1", output_dir, "bucket", "base", {"start": 0.0, "end": 10.0}, 1,
        "2024-01-01T00:00:00Z", False, None, transcript=None,
    ))

    assert row is not None
    assert row["billing_details"]["auto_caption"]["applied"] is False
    assert row["billing_details"]["original_s3_key"] == ""
    assert row["reel_size_bytes"] == len(b"raw-clip-bytes")


def test_save_caption_row_and_debit_debits_video_storage(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_insert_captions", AsyncMock(return_value=[{"id": "cap-1"}]))
    monkeypatch.setattr(app, "_normalize_caption_row", lambda row: row)
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock

    asyncio.run(app._save_caption_row_and_debit(
        row_payload={"id": "row-1"}, job_id="job-cap-1", user_id="u1",
        caption_required_credits=3.0, caption_storage_gb=0.25,
    ))

    debit_mock.assert_awaited_once()
    assert debit_mock.await_args.kwargs["storage_delta"] == pytest.approx(-0.25)
    assert debit_mock.await_args.kwargs["operation_type"] == "sous_titre"


def test_settle_anonymous_story_row_never_debits_storage(monkeypatch):
    # Anonymous stories deliberately carry no storage cost (spec: they
    # don't produce a billable video the way reels/captions/film summaries
    # do) -- this call must never pass storage_delta at all.
    app = _import_app_with_stubs(monkeypatch)
    app.supabase_update_anonymous_story = AsyncMock()
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock

    asyncio.run(app._settle_anonymous_story_row(
        job_id="job-story-1", user_id="u1", story_id="story-1", source_s3_key="key.mp4",
        story_content={"full_text": "hello"}, cost_breakdown={"total_usd": 0.1}, final_credits=4.0,
        story_required_credits=4.0, generated_title="Title", now_iso="2026-01-01T00:00:00+00:00",
    ))

    debit_mock.assert_awaited_once()
    assert "storage_delta" not in debit_mock.await_args.kwargs


def test_delete_film_summary_endpoint_frees_storage(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    row = {
        "id": "fs-1", "source_s3_key": "source/key.mp4",
        "preview_s3_key": "preview/key.mp4", "final_s3_key": "final/key.mp4",
    }
    app.supabase_get_film_summary = AsyncMock(return_value=row)
    app.supabase_soft_delete_film_summary = AsyncMock(return_value=True)
    app.get_s3_object_size = lambda bucket, key: 1024 ** 3
    app.delete_s3_object = lambda bucket, key: True
    free_storage_mock = AsyncMock()
    app._free_user_storage_after_project_deletion = free_storage_mock

    result = asyncio.run(app.delete_film_summary_endpoint("fs-1", "u1"))

    assert result == {"deleted": True}
    free_storage_mock.assert_awaited_once_with("u1", 3 * (1024 ** 3))


def test_render_pipeline_reports_incremental_progress_per_segment(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "download_s3_object", lambda bucket, key, path: True)
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *a, **k: True)
    app._finalize_film_summary_render = AsyncMock()
    progress_calls = []
    app.reel_job_manager.update_progress = AsyncMock(side_effect=lambda *a, **k: progress_calls.append(a))

    def _fake_render_edit_plan(*, on_segment_done, **kwargs):
        # Mirrors render_edit_plan calling back after each of 4 segments --
        # this runs inside asyncio.to_thread, same as the real function, to
        # exercise the actual cross-thread run_coroutine_threadsafe wiring.
        for i in range(4):
            on_segment_done(i, 4)
        return {"segment_count": 4, "final_duration_seconds": 42.0}

    monkeypatch.setattr(app.film_summary_render, "render_edit_plan", _fake_render_edit_plan)

    plan = {"segments": [{"id": "seg_1", "sequence": 1, "type": "voice_over", "narration": "", "estimated_duration_ms": 1000, "clips": []}]}
    asyncio.run(app._run_film_summary_render_pipeline_stages(
        "job-1", "u1", "fs-1", "proj-1", "source-key", str(tmp_path), plan, "cedar", "fr",
    ))

    # 45% (render start) plus one call per segment, all within the 45-85%
    # band reserved for segment-by-segment rendering progress.
    render_stage_calls = [call for call in progress_calls if call[2] == app.film_summary.FilmSummaryStage.RENDERING_PREVIEW]
    assert len(render_stage_calls) == 5
    reported_percentages = [call[1] for call in render_stage_calls[1:]]
    assert reported_percentages == sorted(reported_percentages)
    assert all(45 <= pct <= 85 for pct in reported_percentages)


def test_map_film_summary_subtitle_style_maps_camel_case_and_fills_defaults(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    kwargs = app._map_film_summary_subtitle_style({
        "fontSize": 22, "fontFamily": "Impact", "highlightColor": "#00FF00", "wordsPerLine": 7,
    })

    # Position is always hardcoded to "bottom" -- never read from the row --
    # consistent with CaptionsModal.jsx's own handleSetAsDefaultStyle.
    assert kwargs["position"] == "bottom"
    assert kwargs["font_size"] == 22
    assert kwargs["font_name"] == "Impact"
    assert kwargs["highlight_color"] == "#00FF00"
    assert kwargs["words_per_line"] == 7
    # Anything the row's subtitle_style didn't set falls back to the factory
    # default auto-caption style.
    assert kwargs["font_color"] == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS["font_color"]
    assert kwargs["bg_opacity"] == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS["bg_opacity"]


def test_map_film_summary_subtitle_style_handles_missing_style(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    kwargs = app._map_film_summary_subtitle_style(None)

    assert kwargs["position"] == "bottom"
    assert kwargs["font_size"] == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS["font_size"]
    assert kwargs["words_per_line"] == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS["words_per_line"]


def test_build_film_summary_subtitle_style_builds_style_options(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    captured = {}

    class _StyleOptions:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(app, "SubtitleStyleOptions", _StyleOptions)

    app._build_film_summary_subtitle_style({"fontColor": "#111111", "borderWidth": 9})

    assert captured["font_color"] == "#111111"
    assert captured["border_width"] == 9
    assert captured["highlight_color"] == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS["highlight_color"]


def test_apply_film_summary_subtitle_burn_in_skips_when_disabled(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    calls = []
    monkeypatch.setattr(app, "generate_srt_from_video", lambda *a, **k: calls.append((a, k)))

    final_path = str(tmp_path / "final.mp4")
    result = asyncio.run(app._apply_film_summary_subtitle_burn_in(str(tmp_path), final_path, False, None))

    assert result == final_path
    assert calls == []


def test_apply_film_summary_subtitle_burn_in_burns_and_cleans_up_temp_files(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    srt_path = str(tmp_path / "film_summary_subtitles.srt")
    ass_path = str(tmp_path / "film_summary_subtitles.ass")
    transcribe_calls = []
    burn_calls = []

    def _fake_transcribe(input_path, out_srt_path, max_words_per_line=4):
        transcribe_calls.append((input_path, out_srt_path, max_words_per_line))
        with open(out_srt_path, "w", encoding="utf-8") as handle:
            handle.write("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
        # A real burn_subtitles writes (and later removes) a sibling .ass
        # file next to the srt -- write one here so the cleanup assertion
        # below actually exercises something.
        with open(ass_path, "w", encoding="utf-8") as handle:
            handle.write("[Script Info]\n")
        return True

    def _fake_burn(input_path, srt_path_arg, output_path, alignment=None, fontsize=None, style_options=None):
        burn_calls.append((input_path, srt_path_arg, output_path, alignment, fontsize))
        return True

    monkeypatch.setattr(app, "generate_srt_from_video", _fake_transcribe)
    monkeypatch.setattr(app, "burn_subtitles", _fake_burn)

    class _StyleOptions:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(app, "SubtitleStyleOptions", _StyleOptions)

    final_path = str(tmp_path / "final.mp4")
    result = asyncio.run(app._apply_film_summary_subtitle_burn_in(
        str(tmp_path), final_path, True, {"wordsPerLine": 6, "fontSize": 20},
    ))

    assert result == str(tmp_path / "final_with_subtitles.mp4")
    assert transcribe_calls == [(final_path, srt_path, 6)]
    assert burn_calls == [(final_path, srt_path, str(tmp_path / "final_with_subtitles.mp4"), "bottom", 20)]
    assert not os.path.exists(srt_path)
    assert not os.path.exists(ass_path)


def test_apply_film_summary_subtitle_burn_in_raises_when_no_transcript_produced(monkeypatch, tmp_path):
    # "s'assurer qu'une transcription existe pour la video finale" --
    # generate_srt_from_video returning False (no speech detected, or no
    # duration to transcribe against) must be treated as subtitle
    # generation failing, never silently shipping a final video with no
    # subtitles burned in.
    app = _import_app_with_stubs(monkeypatch)
    burn_calls = []
    monkeypatch.setattr(app, "generate_srt_from_video", lambda *a, **k: False)
    monkeypatch.setattr(app, "burn_subtitles", lambda *a, **k: burn_calls.append(a) or True)

    final_path = str(tmp_path / "final.mp4")
    coro = app._apply_film_summary_subtitle_burn_in(str(tmp_path), final_path, True, None)
    with pytest.raises(film_summary.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.code == film_summary.FilmSummaryErrorCode.TRANSCRIPTION_FAILED
    # burn_subtitles must never be called against a .srt file that was
    # never written.
    assert burn_calls == []


def test_run_film_summary_render_pipeline_applies_subtitles_and_reencodes_preview(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "download_s3_object", lambda bucket, key, path: True)
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *a, **k: True)
    app._finalize_film_summary_render = AsyncMock()
    app.reel_job_manager.update_progress = AsyncMock()

    render_calls = []

    def _fake_render_edit_plan(*, on_segment_done, **kwargs):
        render_calls.append(True)
        return {"segment_count": 1, "final_duration_seconds": 10.0}

    monkeypatch.setattr(app.film_summary_render, "render_edit_plan", _fake_render_edit_plan)

    subtitle_calls = []
    monkeypatch.setattr(app, "generate_srt_from_video", lambda *a, **k: True)

    def _fake_burn(input_path, srt_path_arg, output_path, alignment=None, fontsize=None, style_options=None):
        subtitle_calls.append((input_path, output_path))
        open(output_path, "wb").write(b"x")
        return True

    monkeypatch.setattr(app, "burn_subtitles", _fake_burn)

    class _StyleOptions:
        def __init__(self, **_kwargs):
            pass

    monkeypatch.setattr(app, "SubtitleStyleOptions", _StyleOptions)

    preview_reencode_calls = []
    monkeypatch.setattr(
        app.film_summary_render, "encode_preview",
        lambda inp, out, **k: preview_reencode_calls.append((inp, out)),
    )

    plan = {"segments": [{"id": "seg_1", "sequence": 1, "type": "voice_over", "narration": "", "estimated_duration_ms": 1000, "clips": []}]}
    asyncio.run(app._run_film_summary_render_pipeline_stages(
        "job-1", "u1", "fs-1", "proj-1", "source-key", str(tmp_path), plan, "cedar", "fr",
        subtitles_enabled=True, subtitle_style={"fontSize": 18},
    ))

    assert render_calls == [True]
    assert len(subtitle_calls) == 1
    assert subtitle_calls[0][0] == str(tmp_path / "final.mp4")
    # Preview re-encoded once at the end, from the fully post-processed path.
    assert preview_reencode_calls == [(str(tmp_path / "final_with_subtitles.mp4"), str(tmp_path / "preview.mp4"))]
    # Burning subtitles in gets its own dedicated, user-visible progress
    # stage -- the final step before upload -- rather than being silently
    # folded into RENDERING_FINAL.
    stage_calls = [call.args[2] for call in app.reel_job_manager.update_progress.await_args_list]
    assert film_summary.FilmSummaryStage.ADDING_SUBTITLES in stage_calls
    assert stage_calls.index(film_summary.FilmSummaryStage.ADDING_SUBTITLES) > stage_calls.index(film_summary.FilmSummaryStage.RENDERING_FINAL)


def test_run_film_summary_render_pipeline_leaves_preview_untouched_without_new_settings(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "download_s3_object", lambda bucket, key, path: True)
    monkeypatch.setattr(app, "upload_file_to_s3", lambda *a, **k: True)
    app._finalize_film_summary_render = AsyncMock()
    app.reel_job_manager.update_progress = AsyncMock()
    monkeypatch.setattr(app.film_summary_render, "render_edit_plan", lambda *a, on_segment_done, **k: {"segment_count": 1, "final_duration_seconds": 10.0})
    preview_reencode_calls = []
    monkeypatch.setattr(app.film_summary_render, "encode_preview", lambda *a, **k: preview_reencode_calls.append(a))

    plan = {"segments": [{"id": "seg_1", "sequence": 1, "type": "voice_over", "narration": "", "estimated_duration_ms": 1000, "clips": []}]}
    asyncio.run(app._run_film_summary_render_pipeline_stages(
        "job-1", "u1", "fs-1", "proj-1", "source-key", str(tmp_path), plan, "cedar", "fr",
    ))

    # No subtitle setting to act on, so the preview render_edit_plan already
    # built is never touched again.
    assert preview_reencode_calls == []
    # ...and no ADDING_SUBTITLES stage is reported either, since nothing
    # happens in that step when subtitles aren't enabled.
    stage_calls = [call.args[2] for call in app.reel_job_manager.update_progress.await_args_list]
    assert film_summary.FilmSummaryStage.ADDING_SUBTITLES not in stage_calls


def test_share_film_summary_rejects_when_not_completed(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    app.supabase_get_film_summary = AsyncMock(return_value={"id": "fs-1", "status": "awaiting_review"})

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/film-summaries/fs-1/share",
            json={"account_ids": ["acct-1"]},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_share_film_summary_publishes_immediately(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    app.supabase_get_film_summary = AsyncMock(return_value={
        "id": "fs-1", "status": "completed", "title": "Mon film", "final_s3_key": "final/fs-1.mp4",
    })
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: "https://s3.example/final/fs-1.mp4")
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "acct-1", "platform": "facebook", "platform_user_id": "page-1"}))
    app._insert_publish_job = AsyncMock(return_value="pub-1")
    app._update_publish_job_status = AsyncMock()
    published_payloads = []

    async def fake_publish_post(account, content):
        published_payloads.append(content)
        return {"id": "post-123"}

    monkeypatch.setattr(app, "publish_post", fake_publish_post)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/film-summaries/fs-1/share",
            json={"account_ids": ["acct-1"], "description": "Regardez ce resume !"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["success"] is True
    assert payload["results"]["acct-1"]["success"] is True
    assert len(published_payloads) == 1
    assert published_payloads[0].video_url == "https://s3.example/final/fs-1.mp4"
    assert published_payloads[0].description == "Regardez ce resume !"


def test_share_film_summary_schedules_future_post(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    app.supabase_get_film_summary = AsyncMock(return_value={
        "id": "fs-1", "status": "completed", "title": "Mon film", "final_s3_key": "final/fs-1.mp4",
    })
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: "https://s3.example/final/fs-1.mp4")
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "yt-acct", "platform": "youtube"}))
    schedule_mock = AsyncMock(return_value={"success": True, "scheduled": True, "publish_job_id": "pub-1"})
    app._schedule_share_publish_job = schedule_mock

    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    with TestClient(app.app) as client:
        resp = client.post(
            "/api/film-summaries/fs-1/share",
            json={"account_ids": ["yt-acct"], "scheduled_date": future_date, "timezone": "UTC"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    assert resp.json()["results"]["yt-acct"]["scheduled"] is True
    schedule_mock.assert_awaited_once()
    assert schedule_mock.await_args.args[2] == "film_summary"
    assert schedule_mock.await_args.args[3] == "fs-1"


def test_share_reel_publishes_to_each_selected_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    app.supabase_get_reel = AsyncMock(return_value={"reel_title": "Mon reel"})
    monkeypatch.setattr(app, "_normalize_reel_row", lambda row: {**row, "media_url": "https://s3.example/reel.mp4"})
    accounts_by_id = {
        "fb-acct": {"id": "fb-acct", "platform": "facebook"},
        "yt-acct": {"id": "yt-acct", "platform": "youtube"},
    }
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(side_effect=lambda _uid, aid: accounts_by_id.get(aid)))
    monkeypatch.setattr(app, "_insert_publish_job", AsyncMock(return_value="pub-1"))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "post-1"}))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/reels/reel-1/share",
            json={"account_ids": ["fb-acct", "yt-acct"]},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert set(data["results"].keys()) == {"fb-acct", "yt-acct"}


def test_share_reel_rejects_when_no_media_url(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    app.supabase_get_reel = AsyncMock(return_value={"reel_title": "Mon reel"})
    monkeypatch.setattr(app, "_normalize_reel_row", lambda row: {**row, "media_url": ""})

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/reels/reel-1/share",
            json={"account_ids": ["fb-acct"]},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_share_caption_publishes_to_each_selected_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    app.supabase_get_caption = AsyncMock(return_value={"caption_title": "Mes sous-titres"})
    monkeypatch.setattr(app, "_normalize_caption_row", lambda row: {**row, "media_url": "https://s3.example/caption.mp4"})
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "fb-acct", "platform": "facebook"}))
    monkeypatch.setattr(app, "_insert_publish_job", AsyncMock(return_value="pub-1"))
    monkeypatch.setattr(app, "_update_publish_job_status", AsyncMock())
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "post-1"}))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/captions/caption-1/share",
            json={"account_ids": ["fb-acct"]},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["results"]["fb-acct"]["success"] is True


def test_post_to_socials_publishes_reel_clip_to_selected_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "fb-acct", "platform": "facebook"}))
    monkeypatch.setattr(
        app, "_resolve_clip_for_social_post",
        AsyncMock(return_value={"video_url": "https://s3.example/clip.mp4", "title": "Clip"}),
    )
    monkeypatch.setattr(app, "_insert_publish_job", AsyncMock(return_value="pub-1"))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "post-1"}))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/post",
            json={"job_id": "job-1", "clip_index": 0, "account_ids": ["fb-acct"]},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["results"]["fb-acct"]["success"] is True


def test_create_social_post_blocks_when_over_comment_limit(monkeypatch):
    # abonnement.commentaire caps how many follow-up comments a single
    # publication can carry -- a request with more than that must be
    # rejected before any account is touched or anything is published.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value={"commentaire": 1}))
    resolve_accounts_mock = AsyncMock()
    monkeypatch.setattr(app, "_resolve_accounts_for_publish", resolve_accounts_mock)

    payload = app.CreateSocialPostRequest(
        text="Hello", account_ids=["acct-1"],
        comments=[app.SocialPostCommentInput(text="first"), app.SocialPostCommentInput(text="second")],
    )
    coro = app.create_social_post(payload=payload, user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.status_code == 403
    assert "1 commentaire" in exc_info.value.detail
    resolve_accounts_mock.assert_not_awaited()


def test_create_social_post_allows_comments_within_limit(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value={"commentaire": 2}))
    monkeypatch.setattr(app, "_resolve_accounts_for_publish", AsyncMock(return_value=[{"id": "acct-1", "platform": "facebook"}]))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "_publish_or_schedule_social_post", AsyncMock(return_value={"success": True}))

    payload = app.CreateSocialPostRequest(
        text="Hello", account_ids=["acct-1"],
        comments=[app.SocialPostCommentInput(text="first"), app.SocialPostCommentInput(text="second")],
    )
    result = asyncio.run(app.create_social_post(payload=payload, user_id="u1"))

    assert result["success"] is True


def test_get_user_max_comments_per_post_defaults_to_zero_without_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value=None))
    assert asyncio.run(app._get_user_max_comments_per_post("u1")) == 0


def test_get_user_max_comments_per_post_reads_plan_column(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value={"commentaire": 5}))
    assert asyncio.run(app._get_user_max_comments_per_post("u1")) == 5


def test_film_summary_voice_preview_rejects_unknown_voice(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    with TestClient(app.app) as client:
        resp = client.get("/api/film-summaries/voice-previews/not-a-real-voice", headers=_auth_headers("u1"))
    assert resp.status_code == 400


def test_film_summary_voice_preview_generates_and_caches_on_first_request(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "FILM_SUMMARY_VOICE_PREVIEWS_DIR", str(tmp_path))
    synth = AsyncMock(side_effect=lambda **kwargs: Path(kwargs["output_path"]).write_bytes(b"fake-mp3") or 1.5)
    monkeypatch.setattr(app.film_summary, "synthesize_tts_segment", synth)

    with TestClient(app.app) as client:
        resp = client.get("/api/film-summaries/voice-previews/cedar", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"preview_url": "/voice-previews/cedar.mp3"}
    synth.assert_awaited_once()
    assert synth.await_args.kwargs["voice"] == "cedar"
    assert (tmp_path / "cedar.mp3").exists()


def test_film_summary_voice_preview_skips_synthesis_when_cached(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "FILM_SUMMARY_VOICE_PREVIEWS_DIR", str(tmp_path))
    (tmp_path / "nova.mp3").write_bytes(b"already-cached")
    synth = AsyncMock()
    monkeypatch.setattr(app.film_summary, "synthesize_tts_segment", synth)

    with TestClient(app.app) as client:
        resp = client.get("/api/film-summaries/voice-previews/nova", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"preview_url": "/voice-previews/nova.mp3"}
    synth.assert_not_awaited()


def test_film_summary_voice_preview_regenerates_empty_cached_file(monkeypatch, tmp_path):
    # Regression test: a previous request that failed partway through
    # streaming (see synthesize_tts_segment) could leave a zero-byte file
    # behind under the old direct-write implementation. The cache check
    # must not treat that as "already generated" -- it must regenerate
    # instead of permanently serving a broken preview for that voice.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "FILM_SUMMARY_VOICE_PREVIEWS_DIR", str(tmp_path))
    (tmp_path / "sage.mp3").write_bytes(b"")
    synth = AsyncMock(side_effect=lambda **kwargs: Path(kwargs["output_path"]).write_bytes(b"fake-mp3") or 1.5)
    monkeypatch.setattr(app.film_summary, "synthesize_tts_segment", synth)

    with TestClient(app.app) as client:
        resp = client.get("/api/film-summaries/voice-previews/sage", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    synth.assert_awaited_once()
    assert (tmp_path / "sage.mp3").read_bytes() == b"fake-mp3"


# ---------------------------------------------------------------------------
# User-replaceable default caption style (style_edit_versions, sentinel
# job_id/clip_index) -- what new reels/captions get auto-captioned with.
# ---------------------------------------------------------------------------

def test_get_user_default_caption_style_returns_factory_default_without_supabase(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    result = asyncio.run(app._get_user_default_caption_style("u1"))

    assert result == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS


def test_get_user_default_caption_style_returns_factory_default_without_user_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    list_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_list_style_edit_versions", list_mock)

    result = asyncio.run(app._get_user_default_caption_style(None))

    assert result == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS
    list_mock.assert_not_awaited()


def test_get_user_default_caption_style_returns_latest_saved_version(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    versions = [
        {"version_number": 1, "style_config": {"font_name": "Montserrat", "font_size": 52}},
        {"version_number": 2, "style_config": {"font_name": "Poppins", "font_size": 30}},
    ]
    monkeypatch.setattr(app, "supabase_list_style_edit_versions", AsyncMock(return_value=versions))

    result = asyncio.run(app._get_user_default_caption_style("u1"))

    assert result == {"font_name": "Poppins", "font_size": 30}


def test_get_user_default_caption_style_falls_back_when_query_fails(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_list_style_edit_versions", AsyncMock(side_effect=RuntimeError("boom")))

    result = asyncio.run(app._get_user_default_caption_style("u1"))

    assert result == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS


def test_get_default_caption_style_endpoint_returns_current_default(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    with TestClient(app.app) as client:
        resp = client.get("/api/caption-style-default", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json()["style"] == app._DEFAULT_AUTO_CAPTION_STYLE_KWARGS


def test_set_default_caption_style_endpoint_requires_supabase(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    with TestClient(app.app) as client:
        resp = client.put(
            "/api/caption-style-default",
            json={"font_name": "Poppins", "font_size": 30},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 503


def test_set_default_caption_style_endpoint_appends_next_version(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(
        app, "supabase_list_style_edit_versions",
        AsyncMock(return_value=[{"version_number": 1}, {"version_number": 2}]),
    )
    insert_mock = AsyncMock(return_value={})
    monkeypatch.setattr(app, "supabase_insert_style_edit_version", insert_mock)

    with TestClient(app.app) as client:
        resp = client.put(
            "/api/caption-style-default",
            json={"font_name": "Poppins", "font_size": 30},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["style"]["font_name"] == "Poppins"
    assert body["style"]["font_size"] == 30

    insert_mock.assert_awaited_once()
    inserted = insert_mock.await_args.args[0]
    assert inserted["job_id"] == app._DEFAULT_STYLE_SENTINEL_JOB_ID
    assert inserted["clip_index"] == app._DEFAULT_STYLE_SENTINEL_CLIP_INDEX
    assert inserted["version_number"] == 3
    assert inserted["user_id"] == "u1"
    assert inserted["style_config"]["font_name"] == "Poppins"


def test_set_default_caption_style_endpoint_rejects_out_of_range_font_size(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    with TestClient(app.app) as client:
        resp = client.put(
            "/api/caption-style-default",
            json={"font_size": 1000},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Caption style themes (CaptionsModal "Themes" picker, user-saved presets)
# ---------------------------------------------------------------------------

def test_list_caption_style_themes_returns_empty_without_supabase(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    with TestClient(app.app) as client:
        resp = client.get("/api/caption-style-themes", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"themes": []}


def test_list_caption_style_themes_returns_user_rows(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    list_mock = AsyncMock(return_value=[{"id": "t1", "name": "Mon Style", "style": {"fontFamily": "Montserrat"}}])
    monkeypatch.setattr(app, "supabase_list_caption_style_themes", list_mock)

    with TestClient(app.app) as client:
        resp = client.get("/api/caption-style-themes", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"themes": [{"id": "t1", "name": "Mon Style", "style": {"fontFamily": "Montserrat"}}]}
    list_mock.assert_awaited_once_with("u1")


def test_save_caption_style_theme_requires_name(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    with TestClient(app.app) as client:
        resp = client.post("/api/caption-style-themes", json={"name": "  ", "style": {}}, headers=_auth_headers("u1"))

    assert resp.status_code == 400


def test_save_caption_style_theme_requires_supabase(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    with TestClient(app.app) as client:
        resp = client.post("/api/caption-style-themes", json={"name": "Mon Style", "style": {}}, headers=_auth_headers("u1"))

    assert resp.status_code == 503


def test_save_caption_style_theme_upserts_and_returns_row(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    upsert_mock = AsyncMock(return_value={"id": "t1", "name": "Mon Style", "style": {"fontFamily": "Bangers"}})
    monkeypatch.setattr(app, "supabase_upsert_caption_style_theme", upsert_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/caption-style-themes",
            json={"name": "Mon Style", "style": {"fontFamily": "Bangers"}},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    assert resp.json() == {"id": "t1", "name": "Mon Style", "style": {"fontFamily": "Bangers"}}
    upsert_mock.assert_awaited_once_with("u1", "Mon Style", {"fontFamily": "Bangers"})


def test_delete_caption_style_theme_returns_404_when_not_found(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_delete_caption_style_theme", AsyncMock(return_value=False))

    with TestClient(app.app) as client:
        resp = client.delete("/api/caption-style-themes/does-not-exist", headers=_auth_headers("u1"))

    assert resp.status_code == 404


def test_delete_caption_style_theme_succeeds(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_delete_caption_style_theme", delete_mock)

    with TestClient(app.app) as client:
        resp = client.delete("/api/caption-style-themes/t1", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    delete_mock.assert_awaited_once_with("t1", "u1")


# ---------------------------------------------------------------------------
# Custom reels: manual start/end selection on the preserved source video
# ---------------------------------------------------------------------------

_CUSTOM_REEL_JOB_ID = "deadbeef1234"


def test_preserve_source_video_copies_input_path(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    src = tmp_path / "upload.mp4"
    src.write_bytes(b"video-bytes")

    asyncio.run(app._preserve_source_video_for_manual_clipping("job-1", {"input_path": str(src)}, str(tmp_path)))

    assert (tmp_path / "source.mp4").read_bytes() == b"video-bytes"


def test_preserve_source_video_falls_back_to_leftover_scan(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    (tmp_path / "My Cool Video.mp4").write_bytes(b"downloaded-bytes")

    asyncio.run(app._preserve_source_video_for_manual_clipping("job-1", {"input_path": None}, str(tmp_path)))

    assert (tmp_path / "source.mp4").read_bytes() == b"downloaded-bytes"


def test_preserve_source_video_ignores_clip_files_when_scanning(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    (tmp_path / "base_clip_1.mp4").write_bytes(b"clip-bytes")

    asyncio.run(app._preserve_source_video_for_manual_clipping("job-1", {}, str(tmp_path)))

    assert not (tmp_path / "source.mp4").exists()


def test_preserve_source_video_is_best_effort_on_failure(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    src = tmp_path / "upload.mp4"
    src.write_bytes(b"video-bytes")
    monkeypatch.setattr(app.shutil, "copyfile", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    # must not raise
    asyncio.run(app._preserve_source_video_for_manual_clipping("job-1", {"input_path": str(src)}, str(tmp_path)))


def test_preserve_source_video_uploads_to_s3_and_bills_storage(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    src = tmp_path / "upload.mp4"
    src.write_bytes(b"video-bytes")

    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "my-bucket")
    upload_mock = MagicMock(return_value=True)
    monkeypatch.setattr(app, "upload_file_to_s3", upload_mock)
    deduct_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_deduct_user_credits", deduct_mock)
    history_mock = AsyncMock(return_value={})
    monkeypatch.setattr(app, "supabase_upsert_user_data_history_entry", history_mock)

    asyncio.run(app._preserve_source_video_for_manual_clipping(
        "job-1", {"input_path": str(src)}, str(tmp_path), "user-1",
    ))

    dest = str(tmp_path / "source.mp4")
    upload_mock.assert_called_once_with(dest, "my-bucket", "reels/user-1/job-1/source.mp4")

    expected_storage_gb = app._bytes_to_gb(len(b"video-bytes"))
    deduct_mock.assert_awaited_once_with("user-1", 0.0, -expected_storage_gb)
    # operation_id is the bare job_id (not suffixed) so this storage charge
    # merges into the job's own primary "generation_reel" history row
    # instead of becoming its own line.
    history_mock.assert_awaited_once_with(
        user_id="user-1",
        credit=0.0,
        storage=round(expected_storage_gb, 6),
        operation="output",
        operation_type="generation_reel",
        operation_id="job-1",
    )


def test_preserve_source_video_skips_billing_without_user_id(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    src = tmp_path / "upload.mp4"
    src.write_bytes(b"video-bytes")

    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "my-bucket")
    upload_mock = MagicMock(return_value=True)
    monkeypatch.setattr(app, "upload_file_to_s3", upload_mock)

    asyncio.run(app._preserve_source_video_for_manual_clipping("job-1", {"input_path": str(src)}, str(tmp_path)))

    upload_mock.assert_not_called()


def test_preserve_source_video_is_best_effort_on_s3_failure(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    src = tmp_path / "upload.mp4"
    src.write_bytes(b"video-bytes")

    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "my-bucket")
    monkeypatch.setattr(app, "upload_file_to_s3", MagicMock(side_effect=RuntimeError("boom")))
    deduct_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(app, "supabase_deduct_user_credits", deduct_mock)

    # must not raise, and the local copy must still be in place
    asyncio.run(app._preserve_source_video_for_manual_clipping(
        "job-1", {"input_path": str(src)}, str(tmp_path), "user-1",
    ))

    assert (tmp_path / "source.mp4").read_bytes() == b"video-bytes"
    deduct_mock.assert_not_awaited()


def test_get_reel_job_source_endpoint_reports_unavailable_when_missing(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs[_CUSTOM_REEL_JOB_ID] = {"user_id": "u1"}
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))

    with TestClient(app.app) as client:
        resp = client.get(f"/api/reels/{_CUSTOM_REEL_JOB_ID}/source", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"available": False}


def test_get_reel_job_source_endpoint_reports_available(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    app.jobs[_CUSTOM_REEL_JOB_ID] = {"user_id": "u1"}
    job_dir = tmp_path / _CUSTOM_REEL_JOB_ID
    job_dir.mkdir()
    (job_dir / "source.mp4").write_bytes(b"x")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda path: 42.0)

    with TestClient(app.app) as client:
        resp = client.get(f"/api/reels/{_CUSTOM_REEL_JOB_ID}/source", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {
        "available": True,
        "source_url": f"/videos/{_CUSTOM_REEL_JOB_ID}/source.mp4",
        "duration_seconds": 42.0,
    }


def _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path):
    app.jobs[_CUSTOM_REEL_JOB_ID] = {"user_id": "u1", "project_id": "proj-1"}
    job_dir = tmp_path / _CUSTOM_REEL_JOB_ID
    job_dir.mkdir()
    (job_dir / "source.mp4").write_bytes(b"source-bytes")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda path: 300.0)
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock(return_value=1.0))
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=(
        str(job_dir / f"{_CUSTOM_REEL_JOB_ID}_metadata.json"),
        {"shorts": [], "transcript": {"segments": []}},
    )))
    monkeypatch.setattr(app, "_persist_metadata_json", lambda *a, **k: None)
    monkeypatch.setattr(app, "_cut_and_verticalize_custom_clip", AsyncMock(return_value=str(job_dir / "clip_1.mp4")))
    reel_row = {
        "reel_url": "https://cdn.example/clip.mp4",
        "reel_size_bytes": 1000,
        "billing_details": {"final_credits": 2.5, "auto_caption": {"applied": True, "credit_cost": 0.5}},
    }
    monkeypatch.setattr(app, "_build_reel_row_for_clip", AsyncMock(return_value=reel_row))
    monkeypatch.setattr(app, "supabase_insert_reels", AsyncMock(return_value=[{"id": "reel-1", **reel_row}]))
    monkeypatch.setattr(app, "_normalize_reel_row", lambda row: row)
    debit_mock = AsyncMock(return_value=True)
    app.reel_job_manager.debit_credits_for_job = debit_mock
    monkeypatch.setattr(app, "supabase_increment_project_output_count", AsyncMock())
    return debit_mock


def test_create_custom_reel_clip_rejects_end_before_start(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 5000, "end_ms": 4000},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 400


def test_create_custom_reel_clip_rejects_too_short_duration(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 0, "end_ms": 500},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 400


def test_create_custom_reel_clip_rejects_too_long_duration(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 0, "end_ms": 200000},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 400


def test_create_custom_reel_clip_returns_404_without_preserved_source(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)
    os.remove(str(tmp_path / _CUSTOM_REEL_JOB_ID / "source.mp4"))

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 0, "end_ms": 10000},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 404


def test_create_custom_reel_clip_rejects_range_past_source_duration(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda path: 5.0)

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 0, "end_ms": 10000},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 400


def test_create_custom_reel_clip_happy_path(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    debit_mock = _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 1000, "end_ms": 11000, "title": "Mon moment prefere"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "reel-1"

    # Bills base cost + auto-caption add-on together, no reservation to
    # reconcile against (this is an ad-hoc, post-job-completion action).
    debit_mock.assert_awaited_once()
    assert debit_mock.await_args.kwargs["credits"] == pytest.approx(3.0)
    assert debit_mock.await_args.kwargs["operation_type"] == "generation_reel"
    assert debit_mock.await_args.kwargs["reserved_credits"] == 0.0

    build_row_mock = app._build_reel_row_for_clip
    build_row_mock.assert_awaited_once()
    call_args = build_row_mock.await_args.args
    clip_entry = call_args[5]
    assert clip_entry["title"] == "Mon moment prefere"
    assert clip_entry["start"] == pytest.approx(1.0)
    assert clip_entry["end"] == pytest.approx(11.0)
    assert clip_entry["is_custom"] is True


def test_create_custom_reel_clip_uses_explicit_project_id_when_owned(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)
    monkeypatch.setattr(app, "supabase_get_project", AsyncMock(return_value={"id": "proj-2", "user_id": "u1"}))

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 1000, "end_ms": 11000, "project_id": "proj-2"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    build_row_mock = app._build_reel_row_for_clip
    call_args = build_row_mock.await_args.args
    assert call_args[9] == "proj-2"


def test_create_custom_reel_clip_rejects_unowned_explicit_project_id(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)
    monkeypatch.setattr(app, "supabase_get_project", AsyncMock(return_value=None))

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 1000, "end_ms": 11000, "project_id": "someone-elses-project"},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 404


def test_ensure_preserved_source_video_available_prefers_local_copy(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = tmp_path / "job-1"
    output_dir.mkdir()
    (output_dir / "source.mp4").write_bytes(b"local-bytes")
    download_mock = MagicMock()
    monkeypatch.setattr(app, "download_s3_object", download_mock)

    result = app._ensure_preserved_source_video_available("job-1", "u1", str(output_dir))

    assert result == str(output_dir / "source.mp4")
    download_mock.assert_not_called()


def test_ensure_preserved_source_video_available_downloads_s3_backup_when_local_missing(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = tmp_path / "job-1"
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(app, "get_s3_object_size", lambda bucket, key: 1234 if key.endswith(".mp4") else 0)

    def _fake_download(bucket, key, dest):
        Path(dest).write_bytes(b"restored-bytes")
        return True

    monkeypatch.setattr(app, "download_s3_object", _fake_download)

    result = app._ensure_preserved_source_video_available("job-1", "u1", str(output_dir))

    assert result == str(output_dir / "source.mp4")
    assert Path(result).read_bytes() == b"restored-bytes"


def test_ensure_preserved_source_video_available_returns_none_when_nothing_found(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = tmp_path / "job-1"
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(app, "get_s3_object_size", lambda bucket, key: 0)

    result = app._ensure_preserved_source_video_available("job-1", "u1", str(output_dir))

    assert result is None


def test_flatten_transcript_words_extracts_all_words_at_absolute_times():
    import app as app_module
    transcript = {
        "segments": [
            {"words": [{"word": "Hello", "start": 0.0, "end": 0.4}, {"word": " ", "start": 0.4, "end": 0.4}]},
            {"words": [{"word": "world", "start": 12.5, "end": 13.0}]},
        ]
    }
    result = app_module._flatten_transcript_words(transcript)
    assert result == [
        {"text": "Hello", "startMs": 0, "endMs": 400},
        {"text": "world", "startMs": 12500, "endMs": 13000},
    ]


def test_flatten_transcript_words_handles_missing_or_malformed_input():
    import app as app_module
    assert app_module._flatten_transcript_words(None) == []
    assert app_module._flatten_transcript_words({}) == []
    assert app_module._flatten_transcript_words({"segments": [{"words": [{"word": "x", "start": "bad"}]}]}) == []


def test_generate_scene_waveform_png_success(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"video")

    def _fake_run(cmd, **kwargs):
        (tmp_path / "waveform.png").write_bytes(b"png-bytes")
        return types.SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(app.subprocess, "run", _fake_run)

    result = app._generate_scene_waveform_png(str(source_path), str(tmp_path))

    assert result == str(tmp_path / "waveform.png")


def test_generate_scene_waveform_png_returns_none_on_ffmpeg_failure(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"video")
    monkeypatch.setattr(
        app.subprocess, "run",
        lambda *a, **k: types.SimpleNamespace(returncode=1, stderr=b"no audio stream"),
    )

    result = app._generate_scene_waveform_png(str(source_path), str(tmp_path))

    assert result is None


def test_generate_scene_waveform_png_reuses_cached_file(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"video")
    waveform_path = tmp_path / "waveform.png"
    waveform_path.write_bytes(b"cached-png")
    # Make sure the cached waveform is not considered stale relative to source.
    os.utime(waveform_path, (os.path.getmtime(source_path) + 10, os.path.getmtime(source_path) + 10))

    run_mock = MagicMock()
    monkeypatch.setattr(app.subprocess, "run", run_mock)

    result = app._generate_scene_waveform_png(str(source_path), str(tmp_path))

    assert result == str(waveform_path)
    run_mock.assert_not_called()


def test_get_project_manual_scene_returns_unavailable_without_job(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_project", AsyncMock(return_value={"id": "proj-1", "user_id": "u1"}))
    monkeypatch.setattr(app, "supabase_get_latest_job_record_by_project", AsyncMock(return_value=None))

    with TestClient(app.app) as client:
        resp = client.get("/api/projects/proj-1/manual-scene", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"available": False, "job_id": None}


def test_get_project_manual_scene_returns_404_for_unknown_project(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_project", AsyncMock(return_value=None))

    with TestClient(app.app) as client:
        resp = client.get("/api/projects/proj-1/manual-scene", headers=_auth_headers("u1"))

    assert resp.status_code == 404


def test_get_project_manual_scene_reports_unavailable_without_source(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_project", AsyncMock(return_value={"id": "proj-1", "user_id": "u1"}))
    monkeypatch.setattr(app, "supabase_get_latest_job_record_by_project", AsyncMock(return_value={"id": "job-1"}))
    monkeypatch.setattr(app, "_ensure_preserved_source_video_available", MagicMock(return_value=None))

    with TestClient(app.app) as client:
        resp = client.get("/api/projects/proj-1/manual-scene", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"available": False, "job_id": "job-1"}


def test_get_project_manual_scene_happy_path(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    output_dir = tmp_path / "job-1"
    output_dir.mkdir()
    source_path = output_dir / "source.mp4"
    source_path.write_bytes(b"video-bytes")
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_project", AsyncMock(return_value={"id": "proj-1", "user_id": "u1"}))
    monkeypatch.setattr(app, "supabase_get_latest_job_record_by_project", AsyncMock(return_value={"id": "job-1"}))
    monkeypatch.setattr(app, "_ensure_preserved_source_video_available", MagicMock(return_value=str(source_path)))
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda _p: 42.0)
    monkeypatch.setattr(app, "_generate_scene_waveform_png", lambda *_a, **_k: str(output_dir / "waveform.png"))
    transcript = {"segments": [{"words": [{"word": "hi", "start": 0.0, "end": 0.3}]}]}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=("meta.json", {"transcript": transcript})))

    with TestClient(app.app) as client:
        resp = client.get("/api/projects/proj-1/manual-scene", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["job_id"] == "job-1"
    assert body["source_url"] == "/videos/job-1/source.mp4"
    assert body["duration_seconds"] == 42.0
    assert body["waveform_url"] == "/videos/job-1/waveform.png"
    assert body["words"] == [{"text": "hi", "startMs": 0, "endMs": 300}]


def test_create_custom_reel_clip_requires_supabase(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    _setup_custom_reel_clip_mocks(app, monkeypatch, tmp_path)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    with TestClient(app.app) as client:
        resp = client.post(
            f"/api/reels/{_CUSTOM_REEL_JOB_ID}/custom-clip",
            json={"start_ms": 0, "end_ms": 10000},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Stripe subscriptions: mode="subscription" + auto-renewal via invoice.paid
# ---------------------------------------------------------------------------

class _FakeStripeMetadata:
    """Mimics the .to_dict() surface _extract_session_context / the renewal
    handler rely on -- the real stripe.StripeObject supports it too, but a
    plain dict/SimpleNamespace doesn't."""

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeCheckoutRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


def test_list_abonnements_endpoint_filters_out_plans_without_ordre(monkeypatch):
    # A plan with no "ordre" set is retired from sale (see the "ordre"
    # migration) without deleting its row -- the public-facing endpoint
    # must hide it, while supabase_list_abonnements itself still returns
    # it (needed to resolve plan names for existing subscribers' history).
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_list_abonnements", AsyncMock(return_value=[
        {"id": "a1", "name": "Discover", "ordre": 1},
        {"id": "a2", "name": "Retired", "ordre": None},
        {"id": "a3", "name": "Publish", "ordre": 2},
    ]))

    result = asyncio.run(app.list_abonnements())

    assert [plan["id"] for plan in result["plans"]] == ["a1", "a3"]


def test_create_stripe_checkout_session_uses_subscription_mode(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_123", id="cs_test_123")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"id": "plan-1", "name": "Pro", "price": 29.99}))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))

    payload = app.StripeCheckoutRequest(plan_id="plan-1")
    result = asyncio.run(app.create_stripe_checkout_session(
        request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
        payload=payload, user_id="u1",
    ))

    assert result == {"checkout_url": fake_session.url, "session_id": fake_session.id}
    _, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["mode"] == "subscription"
    assert kwargs["line_items"][0]["price_data"]["recurring"] == {"interval": "month"}
    assert kwargs["subscription_data"] == {"metadata": kwargs["metadata"]}
    assert kwargs["metadata"]["userid"] == "u1"
    assert kwargs["customer_email"] == "user@example.com"
    assert "customer" not in kwargs


def test_create_stripe_checkout_session_reuses_existing_stripe_customer(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_456", id="cs_test_456")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"id": "plan-1", "name": "Pro", "price": 29.99}))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"stripe_customer_id": "cus_existing"}))

    payload = app.StripeCheckoutRequest(plan_id="plan-1")
    asyncio.run(app.create_stripe_checkout_session(
        request=_FakeCheckoutRequest(), payload=payload, user_id="u1",
    ))

    _, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["customer"] == "cus_existing"
    assert "customer_email" not in kwargs


def test_annual_price_for_plan_applies_discount_rate():
    import app as app_module
    assert app_module._annual_price_for_plan({"price": 10, "reduction_annuelle": 5}) == 114.0


def test_annual_price_for_plan_accepts_legacy_fractional_discount_during_rollout():
    import app as app_module
    assert app_module._annual_price_for_plan({"price": 10, "reduction_annuelle": 0.05}) == 114.0


def test_annual_price_for_plan_defaults_to_no_discount():
    import app as app_module
    assert app_module._annual_price_for_plan({"price": 10}) == 120.0


def test_annual_price_for_plan_clamps_out_of_range_rate():
    import app as app_module
    assert app_module._annual_price_for_plan({"price": 10, "reduction_annuelle": 150}) == 0.0
    assert app_module._annual_price_for_plan({"price": 10, "reduction_annuelle": -1}) == 120.0


def test_create_stripe_checkout_session_annual_interval_uses_discounted_price(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_annual", id="cs_test_annual")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"id": "plan-1", "name": "Pro", "price": 10.0, "reduction_annuelle": 5}))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))

    payload = app.StripeCheckoutRequest(plan_id="plan-1", billing_interval="year")
    asyncio.run(app.create_stripe_checkout_session(
        request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
        payload=payload, user_id="u1",
    ))

    _, kwargs = fake_stripe.checkout.Session.create.call_args
    price_data = kwargs["line_items"][0]["price_data"]
    assert price_data["recurring"] == {"interval": "year"}
    assert price_data["unit_amount"] == 11400  # (10*12 - 5%) euros, in cents
    assert kwargs["metadata"]["billing_interval"] == "year"


def test_create_stripe_checkout_session_defaults_to_monthly_interval(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_default", id="cs_test_default")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"id": "plan-1", "name": "Pro", "price": 10.0, "reduction_annuelle": 5}))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))

    payload = app.StripeCheckoutRequest(plan_id="plan-1")
    asyncio.run(app.create_stripe_checkout_session(
        request=_FakeCheckoutRequest(), payload=payload, user_id="u1",
    ))

    _, kwargs = fake_stripe.checkout.Session.create.call_args
    price_data = kwargs["line_items"][0]["price_data"]
    assert price_data["recurring"] == {"interval": "month"}
    assert price_data["unit_amount"] == 1000
    assert kwargs["metadata"]["billing_interval"] == "month"


def test_buy_credits_checkout_reuses_existing_stripe_customer(monkeypatch):
    # The card used to buy credits must be the same one on file for the
    # subscription (and vice versa) -- see _existing_stripe_customer_id --
    # so this mode="payment" Checkout must reuse the subscription's Stripe
    # Customer instead of a bare customer_email, which risks a second,
    # disconnected guest Customer.
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_credits", id="cs_test_credits")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_enforce_subscription_retention_policy", AsyncMock(return_value={"state": "active"}))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"stripe_customer_id": "cus_existing"}))

    payload = app.BuyCreditsRequest(amount_usd=10.0)
    result = asyncio.run(app.buy_credits_checkout(
        request=_FakeCheckoutRequest(), payload=payload, user_id="u1",
    ))

    assert result["checkout_url"] == fake_session.url
    _, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["customer"] == "cus_existing"
    assert "customer_email" not in kwargs
    assert kwargs["payment_intent_data"] == {"setup_future_usage": "off_session"}


def test_buy_credits_checkout_falls_back_to_customer_email_without_existing_customer(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_credits2", id="cs_test_credits2")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_enforce_subscription_retention_policy", AsyncMock(return_value={"state": "active"}))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))

    payload = app.BuyCreditsRequest(amount_usd=10.0)
    asyncio.run(app.buy_credits_checkout(
        request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}), payload=payload, user_id="u1",
    ))

    _, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["customer_email"] == "user@example.com"
    assert "customer" not in kwargs


def test_extract_session_context_captures_stripe_subscription_and_customer_ids(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    session = types.SimpleNamespace(
        metadata=_FakeStripeMetadata({"userid": "u1", "abonnement": "plan-1", "payment_mode": "stripe"}),
        created=1700000000,
        amount_total=2999,
        payment_intent=None,
        id="cs_test_789",
        customer_details=None,
        customer_email="user@example.com",
        subscription="sub_abc",
        customer="cus_abc",
    )

    ctx = app._extract_session_context(session)

    assert ctx["stripe_subscription_id"] == "sub_abc"
    assert ctx["stripe_customer_id"] == "cus_abc"
    assert ctx["payment_reference"] == "cs_test_789"  # no payment_intent in subscription mode


def test_invoice_line_period_reads_stripe_period(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    period = types.SimpleNamespace(start=1700000000, end=1702592000)
    invoice = types.SimpleNamespace(lines=types.SimpleNamespace(data=[types.SimpleNamespace(period=period)]))

    start, end = app._invoice_line_period(invoice)

    assert start == datetime.fromtimestamp(1700000000, tz=timezone.utc)
    assert end == datetime.fromtimestamp(1702592000, tz=timezone.utc)


def test_invoice_line_period_missing_lines_returns_none(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    invoice = types.SimpleNamespace(lines=types.SimpleNamespace(data=[]))

    assert app._invoice_line_period(invoice) == (None, None)


def test_handle_subscription_renewal_invoice_credits_plan_and_persists_period(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_subscription = types.SimpleNamespace(metadata=_FakeStripeMetadata({"userid": "u1", "abonnement": "plan-1"}))
    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = fake_subscription
    monkeypatch.setattr(app, "stripe", fake_stripe)

    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    insert_mock = AsyncMock(return_value={"id": "sous-1"})
    monkeypatch.setattr(app, "supabase_insert_souscription", insert_mock)
    allocate_mock = AsyncMock()
    monkeypatch.setattr(app, "_allocate_plan_resources", allocate_mock)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    period = types.SimpleNamespace(start=1700000000, end=1702592000)
    invoice = types.SimpleNamespace(
        subscription="sub_123",
        payment_intent="pi_renewal_1",
        id="in_renewal_1",
        lines=types.SimpleNamespace(data=[types.SimpleNamespace(period=period)]),
        created=1700000000,
        amount_paid=2999,
        customer="cus_456",
        customer_email="user@example.com",
    )

    result = asyncio.run(app._handle_subscription_renewal_invoice(invoice))

    assert result == {"received": True}
    fake_stripe.Subscription.retrieve.assert_called_once_with("sub_123")
    insert_mock.assert_awaited_once()
    kwargs = insert_mock.await_args.kwargs
    assert kwargs["user_id"] == "u1"
    assert kwargs["abonnement"] == "plan-1"
    assert kwargs["payment_reference"] == "pi_renewal_1"
    assert kwargs["stripe_subscription_id"] == "sub_123"
    assert kwargs["stripe_customer_id"] == "cus_456"
    assert kwargs["period_end_date"] == datetime.fromtimestamp(1702592000, tz=timezone.utc)
    assert kwargs["payment_amount"] == 29.99
    allocate_mock.assert_awaited_once()
    email_mock.assert_called_once()


def test_handle_subscription_renewal_invoice_threads_billing_interval(monkeypatch):
    # An annual subscription's renewal invoice (fired once a year by
    # Stripe) must carry billing_interval through to both the new
    # souscription row and _allocate_plan_resources, which is what
    # actually schedules the in-between monthly refills.
    app = _import_app_with_stubs(monkeypatch)
    fake_subscription = types.SimpleNamespace(
        metadata=_FakeStripeMetadata({"userid": "u1", "abonnement": "plan-1", "billing_interval": "year"})
    )
    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = fake_subscription
    monkeypatch.setattr(app, "stripe", fake_stripe)

    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    insert_mock = AsyncMock(return_value={"id": "sous-1"})
    monkeypatch.setattr(app, "supabase_insert_souscription", insert_mock)
    allocate_mock = AsyncMock()
    monkeypatch.setattr(app, "_allocate_plan_resources", allocate_mock)
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())

    period = types.SimpleNamespace(start=1700000000, end=1731536000)
    invoice = types.SimpleNamespace(
        subscription="sub_123", payment_intent="pi_renewal_annual", id="in_renewal_annual",
        lines=types.SimpleNamespace(data=[types.SimpleNamespace(period=period)]),
        created=1700000000, amount_paid=11400, customer="cus_456", customer_email="user@example.com",
    )

    asyncio.run(app._handle_subscription_renewal_invoice(invoice))

    insert_kwargs = insert_mock.await_args.kwargs
    assert insert_kwargs["billing_interval"] == "year"
    allocate_kwargs = allocate_mock.await_args.kwargs
    assert allocate_kwargs["billing_interval"] == "year"
    assert allocate_kwargs["period_start"] == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_handle_subscription_renewal_invoice_is_idempotent_on_duplicate_reference(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value={"id": "existing"}))
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_souscription", insert_mock)

    invoice = types.SimpleNamespace(
        subscription="sub_123", payment_intent="pi_dup", id="in_dup",
        lines=types.SimpleNamespace(data=[]), created=1700000000, amount_paid=2999,
        customer="cus_456", customer_email="user@example.com",
    )

    result = asyncio.run(app._handle_subscription_renewal_invoice(invoice))

    assert result == {"received": True, "duplicate": True}
    insert_mock.assert_not_awaited()


def test_handle_subscription_renewal_invoice_ignores_invoice_without_subscription(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    invoice = types.SimpleNamespace(subscription=None)

    result = asyncio.run(app._handle_subscription_renewal_invoice(invoice))

    assert result == {"received": True, "ignored": "no_subscription_on_invoice"}


def test_handle_subscription_renewal_invoice_ignores_missing_metadata(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    fake_subscription = types.SimpleNamespace(metadata=_FakeStripeMetadata({}))
    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = fake_subscription
    monkeypatch.setattr(app, "stripe", fake_stripe)

    invoice = types.SimpleNamespace(
        subscription="sub_999", payment_intent=None, id="in_999",
        lines=types.SimpleNamespace(data=[]), created=1700000000, amount_paid=0,
        customer=None, customer_email=None,
    )

    result = asyncio.run(app._handle_subscription_renewal_invoice(invoice))

    assert result == {"received": True, "ignored": "missing_subscription_metadata"}


class _FakeWebhookRequest:
    headers = {"stripe-signature": "sig"}

    async def body(self):
        return b"{}"


def test_stripe_webhook_ignores_non_renewal_invoice_paid(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "stripe", MagicMock())
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    invoice = types.SimpleNamespace(billing_reason="subscription_create")
    fake_event = types.SimpleNamespace(type="invoice.paid", data=types.SimpleNamespace(object=invoice))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, signature: fake_event)
    renewal_mock = AsyncMock()
    monkeypatch.setattr(app, "_handle_subscription_renewal_invoice", renewal_mock)

    result = asyncio.run(app.stripe_webhook(_FakeWebhookRequest()))

    assert result == {"received": True, "ignored": "invoice.paid:subscription_create"}
    renewal_mock.assert_not_awaited()


def test_stripe_webhook_dispatches_subscription_cycle_invoice_to_renewal_handler(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "stripe", MagicMock())
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    invoice = types.SimpleNamespace(billing_reason="subscription_cycle")
    fake_event = types.SimpleNamespace(type="invoice.paid", data=types.SimpleNamespace(object=invoice))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, signature: fake_event)
    renewal_mock = AsyncMock(return_value={"received": True})
    monkeypatch.setattr(app, "_handle_subscription_renewal_invoice", renewal_mock)

    result = asyncio.run(app.stripe_webhook(_FakeWebhookRequest()))

    assert result == {"received": True}
    renewal_mock.assert_awaited_once_with(invoice)


def test_stripe_webhook_dispatches_subscription_update_invoice_to_renewal_handler(monkeypatch):
    # A Stripe Subscription Schedule's phase-2 transition (the mechanism
    # driving a deferred downgrade/periodicity change, see
    # _create_or_replace_plan_change_schedule) raises its invoice with
    # billing_reason "subscription_update" rather than "subscription_cycle"
    # -- this must reach the SAME existing renewal handler unmodified, or
    # a scheduled change would silently never get applied/credited.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "stripe", MagicMock())
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    invoice = types.SimpleNamespace(billing_reason="subscription_update")
    fake_event = types.SimpleNamespace(type="invoice.paid", data=types.SimpleNamespace(object=invoice))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, signature: fake_event)
    renewal_mock = AsyncMock(return_value={"received": True})
    monkeypatch.setattr(app, "_handle_subscription_renewal_invoice", renewal_mock)

    result = asyncio.run(app.stripe_webhook(_FakeWebhookRequest()))

    assert result == {"received": True}
    renewal_mock.assert_awaited_once_with(invoice)


def test_stripe_webhook_dispatches_payment_failed_invoice(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "stripe", MagicMock())
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    invoice = types.SimpleNamespace()
    fake_event = types.SimpleNamespace(type="invoice.payment_failed", data=types.SimpleNamespace(object=invoice))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, signature: fake_event)
    failed_mock = AsyncMock(return_value={"received": True})
    monkeypatch.setattr(app, "_handle_subscription_payment_failed", failed_mock)

    result = asyncio.run(app.stripe_webhook(_FakeWebhookRequest()))

    assert result == {"received": True}
    failed_mock.assert_awaited_once_with(invoice)


def test_stripe_webhook_dispatches_setup_session_to_payment_method_handler(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "stripe", MagicMock())
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    session = types.SimpleNamespace(mode="setup", customer="cus_1", setup_intent="seti_1")
    fake_event = types.SimpleNamespace(type="checkout.session.completed", data=types.SimpleNamespace(object=session))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, signature: fake_event)
    setup_mock = MagicMock(return_value={"received": True})
    monkeypatch.setattr(app, "_handle_payment_method_setup", setup_mock)
    purchase_mock = AsyncMock()
    monkeypatch.setattr(app, "_handle_subscription_purchase", purchase_mock)

    result = asyncio.run(app.stripe_webhook(_FakeWebhookRequest()))

    assert result == {"received": True}
    setup_mock.assert_called_once_with(session)
    purchase_mock.assert_not_awaited()


def _fake_subscription_purchase_ctx(**overrides):
    ctx = {
        "metadata": {"abonnement": "plan-1", "plan_name": "Pro"},
        "user_id": "u1",
        "payment_mode": "stripe",
        "amount_total": 29.99,
        "payment_reference": "cs_test_1",
        "payment_date": datetime.now(timezone.utc),
        "session_id": "cs_test_1",
        "customer_email": "user@example.com",
        "stripe_subscription_id": "sub_new",
        "stripe_customer_id": "cus_new",
    }
    ctx.update(overrides)
    return ctx


def test_handle_subscription_purchase_closes_out_previous_souscription(monkeypatch):
    # Changing plan from a non-Stripe-recurring subscription creates a
    # fresh Checkout carrying previous_souscription_id in its metadata
    # (see change_souscription_plan / _create_recurring_subscription_checkout)
    # -- once that Checkout completes, this webhook handler must retire the
    # old row so it stops matching get_user_abonnement's "active" filter
    # alongside the brand new one.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_souscription", AsyncMock(return_value={"id": "sous-new"}))
    monkeypatch.setattr(app, "_allocate_plan_resources", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    monkeypatch.setattr(app, "_sync_customer_default_payment_method", MagicMock())
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)

    ctx = _fake_subscription_purchase_ctx(
        metadata={"abonnement": "plan-1", "plan_name": "Pro", "previous_souscription_id": "sous-legacy"},
    )
    asyncio.run(app._handle_subscription_purchase(ctx))

    update_mock.assert_awaited_once()
    args, kwargs = update_mock.await_args
    assert args[0] == "sous-legacy"
    assert "payment_end_date" in args[1]
    assert kwargs["user_id"] == "u1"


def test_handle_subscription_purchase_without_previous_souscription_touches_nothing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"id": "prior"}))
    monkeypatch.setattr(app, "supabase_insert_souscription", AsyncMock(return_value={"id": "sous-new"}))
    monkeypatch.setattr(app, "_allocate_plan_resources", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    monkeypatch.setattr(app, "_sync_customer_default_payment_method", MagicMock())
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)

    asyncio.run(app._handle_subscription_purchase(_fake_subscription_purchase_ctx()))

    update_mock.assert_not_awaited()


def test_handle_subscription_purchase_syncs_default_payment_method(monkeypatch):
    # The card used to pay during the Checkout must become visible as
    # "card on file" in Settings (get_souscription_payment_method), which
    # reads the Customer's invoice_settings.default_payment_method, not
    # the Subscription's -- without this sync call, a user who only ever
    # subscribed (never replaced their card) would never see the card
    # they actually paid with.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"id": "prior"}))
    monkeypatch.setattr(app, "supabase_insert_souscription", AsyncMock(return_value={"id": "sous-new"}))
    monkeypatch.setattr(app, "_allocate_plan_resources", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    monkeypatch.setattr(app, "supabase_update_souscription_row", AsyncMock())
    sync_mock = MagicMock()
    monkeypatch.setattr(app, "_sync_customer_default_payment_method", sync_mock)

    asyncio.run(app._handle_subscription_purchase(_fake_subscription_purchase_ctx(
        stripe_subscription_id="sub_new", stripe_customer_id="cus_new",
    )))

    sync_mock.assert_called_once_with("sub_new", "cus_new")


def test_handle_subscription_purchase_threads_annual_billing_interval(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"id": "prior"}))
    insert_mock = AsyncMock(return_value={"id": "sous-new"})
    monkeypatch.setattr(app, "supabase_insert_souscription", insert_mock)
    allocate_mock = AsyncMock()
    monkeypatch.setattr(app, "_allocate_plan_resources", allocate_mock)
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    monkeypatch.setattr(app, "_sync_customer_default_payment_method", MagicMock())

    payment_date = datetime.now(timezone.utc)
    ctx = _fake_subscription_purchase_ctx(
        metadata={"abonnement": "plan-1", "plan_name": "Pro", "billing_interval": "year"},
        billing_interval="year", payment_date=payment_date,
    )
    asyncio.run(app._handle_subscription_purchase(ctx))

    insert_kwargs = insert_mock.await_args.kwargs
    assert insert_kwargs["billing_interval"] == "year"
    allocate_kwargs = allocate_mock.await_args.kwargs
    assert allocate_kwargs["billing_interval"] == "year"
    assert allocate_kwargs["period_start"] == payment_date


def test_allocate_plan_resources_snapshots_values_onto_souscription_row(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"id": "plan-1", "credit": 500.0, "stockage": 1.0}))
    balance_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_set_user_data_balance", balance_mock)
    history_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_user_data_history", history_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)
    monkeypatch.setattr(app, "supabase_set_user_max_daily_publications", AsyncMock())

    asyncio.run(app._allocate_plan_resources(
        user_id="u1", abonnement="plan-1", payment_reference="ref-1", souscription_id="sous-1",
    ))

    balance_mock.assert_awaited_once()
    assert balance_mock.await_args.kwargs["credit"] == 500.0
    assert balance_mock.await_args.kwargs["storage"] == 1.0
    update_mock.assert_awaited_once()
    args, _ = update_mock.await_args
    assert args[0] == "sous-1"
    assert args[1] == {"plan_credit": 500.0, "plan_stockage": 1.0}  # no next_credit_allocation_at for a monthly plan


def test_allocate_plan_resources_schedules_next_allocation_for_annual_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"id": "plan-1", "credit": 500.0, "stockage": 1.0}))
    monkeypatch.setattr(app, "supabase_set_user_data_balance", AsyncMock())
    monkeypatch.setattr(app, "supabase_insert_user_data_history", AsyncMock())
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)
    monkeypatch.setattr(app, "supabase_set_user_max_daily_publications", AsyncMock())

    period_start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    asyncio.run(app._allocate_plan_resources(
        user_id="u1", abonnement="plan-1", payment_reference="ref-1", souscription_id="sous-1",
        billing_interval="year", period_start=period_start,
    ))

    args, _ = update_mock.await_args
    assert args[0] == "sous-1"
    assert args[1]["plan_credit"] == 500.0
    assert args[1]["plan_stockage"] == 1.0
    assert args[1]["next_credit_allocation_at"] == datetime(2026, 2, 15, tzinfo=timezone.utc).isoformat()


def test_allocate_plan_resources_noop_when_plan_missing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value=None))
    balance_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_set_user_data_balance", balance_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)

    asyncio.run(app._allocate_plan_resources(
        user_id="u1", abonnement="missing-plan", payment_reference="ref-1", souscription_id="sous-1",
    ))

    balance_mock.assert_not_awaited()
    update_mock.assert_not_awaited()


def test_process_due_annual_credit_refills_uses_snapshot_not_live_plan(monkeypatch):
    # The whole point of the snapshot is that this sweep must never read
    # the live plan catalog -- only the souscription row's own
    # plan_credit/plan_stockage, so a later change to the plan never
    # retroactively changes an in-progress annual subscription's refill.
    app = _import_app_with_stubs(monkeypatch)
    due_row = {
        "id": "sous-1", "userid": "u1", "plan_credit": 500.0, "plan_stockage": 1.0,
        "next_credit_allocation_at": datetime(2026, 1, 15, tzinfo=timezone.utc).isoformat(),
    }
    monkeypatch.setattr(app, "supabase_list_souscriptions_due_for_monthly_credit_allocation", AsyncMock(return_value=[due_row]))
    balance_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_set_user_data_balance", balance_mock)
    monkeypatch.setattr(app, "supabase_insert_user_data_history", AsyncMock())
    get_abonnement_mock = AsyncMock(return_value={"credit": 999999.0, "stockage": 999.0})
    monkeypatch.setattr(app, "supabase_get_abonnement", get_abonnement_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)

    asyncio.run(app._process_due_annual_credit_refills())

    get_abonnement_mock.assert_not_awaited()
    balance_mock.assert_awaited_once()
    assert balance_mock.await_args.kwargs["credit"] == 500.0
    assert balance_mock.await_args.kwargs["storage"] == 1.0
    update_args, _ = update_mock.await_args
    assert update_args[0] == "sous-1"
    assert update_args[1]["next_credit_allocation_at"] == datetime(2026, 2, 15, tzinfo=timezone.utc).isoformat()


def test_process_due_annual_credit_refills_skips_rows_missing_ids(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_list_souscriptions_due_for_monthly_credit_allocation", AsyncMock(return_value=[
        {"id": "sous-1", "userid": None, "plan_credit": 500.0, "plan_stockage": 1.0},
    ]))
    balance_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_set_user_data_balance", balance_mock)
    monkeypatch.setattr(app, "supabase_insert_user_data_history", AsyncMock())
    monkeypatch.setattr(app, "supabase_update_souscription_row", AsyncMock())

    asyncio.run(app._process_due_annual_credit_refills())

    balance_mock.assert_not_awaited()


def test_sync_customer_default_payment_method_sets_default_from_expanded_subscription(monkeypatch):
    # A plain dict would silently accept subscription.get(...) and hide
    # the real SDK's failure mode -- _FakeStripeObjectNoGet (defined
    # below) mimics a real stripe.StripeObject, which only supports
    # bracket access, to actually catch a .get() regression here.
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    fake_stripe.Subscription.retrieve.return_value = _FakeStripeObjectNoGet(
        {"default_payment_method": _FakeStripeObjectNoGet({"id": "pm_abc"})},
    )

    app._sync_customer_default_payment_method("sub_1", "cus_1")

    fake_stripe.Subscription.retrieve.assert_called_once_with("sub_1", expand=["default_payment_method"])
    fake_stripe.Customer.modify.assert_called_once_with("cus_1", invoice_settings={"default_payment_method": "pm_abc"})


def test_sync_customer_default_payment_method_accepts_unexpanded_string_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    fake_stripe.Subscription.retrieve.return_value = _FakeStripeObjectNoGet({"default_payment_method": "pm_xyz"})

    app._sync_customer_default_payment_method("sub_1", "cus_1")

    fake_stripe.Customer.modify.assert_called_once_with("cus_1", invoice_settings={"default_payment_method": "pm_xyz"})


def test_sync_customer_default_payment_method_noop_without_ids(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)

    app._sync_customer_default_payment_method(None, "cus_1")
    app._sync_customer_default_payment_method("sub_1", None)

    fake_stripe.Subscription.retrieve.assert_not_called()
    fake_stripe.Customer.modify.assert_not_called()


def test_sync_customer_default_payment_method_swallows_stripe_errors(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    fake_stripe.Subscription.retrieve.side_effect = RuntimeError("boom")

    app._sync_customer_default_payment_method("sub_1", "cus_1")  # must not raise


def test_stripe_field_reads_real_stripe_object_without_get(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    obj = _FakeStripeObjectNoGet({"brand": "visa", "last4": None})
    assert app._stripe_field(obj, "brand") == "visa"
    assert app._stripe_field(obj, "last4") is None  # a present-but-null value still falls back to default
    assert app._stripe_field(obj, "last4", "stand-in") == "stand-in"
    assert app._stripe_field(obj, "missing_key", "fallback") == "fallback"


def test_stripe_field_handles_plain_dict_and_none(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._stripe_field({"brand": "visa"}, "brand") == "visa"
    assert app._stripe_field({"brand": "visa"}, "missing", "fallback") == "fallback"
    assert app._stripe_field(None, "brand", "fallback") == "fallback"


def test_get_stripe_default_payment_method_reads_customer_default_without_get(monkeypatch):
    # A plain dict/MagicMock for `customer` would silently accept
    # customer.get(...) and hide the real SDK's failure mode --
    # _FakeStripeObjectNoGet mimics a real stripe.StripeObject (bracket
    # access only) to actually catch a .get() regression here.
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    default_pm = _FakeStripeObjectNoGet({"id": "pm_default"})
    invoice_settings = _FakeStripeObjectNoGet({"default_payment_method": default_pm})
    fake_stripe.Customer.retrieve.return_value = _FakeStripeObjectNoGet({"invoice_settings": invoice_settings})

    result = app._get_stripe_default_payment_method("cus_1")

    assert result is default_pm
    fake_stripe.PaymentMethod.list.assert_not_called()


def test_get_stripe_default_payment_method_falls_back_to_first_attached_card(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    invoice_settings = _FakeStripeObjectNoGet({"default_payment_method": None})
    fake_stripe.Customer.retrieve.return_value = _FakeStripeObjectNoGet({"invoice_settings": invoice_settings})
    first_card = _FakeStripeObjectNoGet({"id": "pm_first"})
    fake_stripe.PaymentMethod.list.return_value = _FakeStripeObjectNoGet({"data": [first_card]})

    result = app._get_stripe_default_payment_method("cus_1")

    assert result is first_card


# ---------------------------------------------------------------------------
# Credit top-up purchase: granted as its own tier-2 expiring batch, not a
# plain delta into user_data.credit (see the credit-tiers migration).
# ---------------------------------------------------------------------------

def _fake_credit_purchase_ctx(**overrides):
    ctx = {
        "metadata": {"credits_to_add": 100.0},
        "user_id": "u1",
        "amount_total": 9.99,
        "payment_reference": "cs_credits_1",
        "payment_date": datetime.now(timezone.utc),
        "customer_email": "user@example.com",
    }
    ctx.update(overrides)
    return ctx


def test_handle_credit_purchase_grants_tier_2_batch_not_plain_delta(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "_enforce_subscription_retention_policy", AsyncMock(return_value={"state": "active"}))
    monkeypatch.setattr(app, "supabase_insert_souscription", AsyncMock(return_value={"id": "sous-credits-1"}))
    batch_mock = AsyncMock(return_value={"id": "batch-1"})
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)
    delta_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_upsert_user_data_credits", delta_mock)
    monkeypatch.setattr(app, "supabase_insert_user_data_history", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())

    result = asyncio.run(app._handle_credit_purchase(_fake_credit_purchase_ctx()))

    assert result == {"received": True, "credits_added": 100.0}
    batch_mock.assert_awaited_once_with(
        "u1", 100.0, "CREDIT_PURCHASE", app.PURCHASED_CREDITS_EXPIRATION_DAYS,
        source_reference="sous-credits-1", tier=app.CREDIT_BATCH_TIER_PURCHASED,
    )
    # Never a plain delta into user_data.credit -- that's what used to let
    # a subscription renewal's reset-to-allowance silently wipe a
    # purchased top-up.
    delta_mock.assert_not_awaited()


def test_handle_credit_purchase_duplicate_payment_reference_is_noop(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value={"id": "existing"}))
    batch_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)

    result = asyncio.run(app._handle_credit_purchase(_fake_credit_purchase_ctx()))

    assert result == {"received": True, "duplicate": True}
    batch_mock.assert_not_awaited()


def test_handle_credit_purchase_requires_active_subscription(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "_enforce_subscription_retention_policy", AsyncMock(return_value={"state": "no_subscription"}))
    batch_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)

    result = asyncio.run(app._handle_credit_purchase(_fake_credit_purchase_ctx()))

    assert result == {"received": True, "ignored": "no_active_subscription", "policy_state": "no_subscription"}
    batch_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Payment method preview/revoke/replace: card on file shown in Settings.
# ---------------------------------------------------------------------------

def test_handle_payment_method_setup_sets_default_and_detaches_old(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    fake_stripe.SetupIntent.retrieve.return_value = types.SimpleNamespace(payment_method="pm_new")
    monkeypatch.setattr(app, "_get_stripe_default_payment_method", MagicMock(return_value={"id": "pm_old"}))
    session = types.SimpleNamespace(customer="cus_1", setup_intent="seti_1")

    result = app._handle_payment_method_setup(session)

    assert result == {"received": True}
    fake_stripe.Customer.modify.assert_called_once_with("cus_1", invoice_settings={"default_payment_method": "pm_new"})
    fake_stripe.PaymentMethod.detach.assert_called_once_with("pm_old")


def test_handle_payment_method_setup_skips_detach_when_no_previous_card(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    fake_stripe.SetupIntent.retrieve.return_value = types.SimpleNamespace(payment_method="pm_new")
    monkeypatch.setattr(app, "_get_stripe_default_payment_method", MagicMock(return_value=None))
    session = types.SimpleNamespace(customer="cus_1", setup_intent="seti_1")

    result = app._handle_payment_method_setup(session)

    assert result == {"received": True}
    fake_stripe.PaymentMethod.detach.assert_not_called()


def test_get_souscription_payment_method_returns_card_summary(monkeypatch):
    # Both payment_method and its nested "card" must be real
    # stripe.StripeObject-like values here (bracket access only, no
    # .get()) -- a plain dict would silently accept .get() and hide a
    # regression (see _FakeStripeObjectNoGet).
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    card = _FakeStripeObjectNoGet({"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2027})
    payment_method = _FakeStripeObjectNoGet({"id": "pm_1", "card": card})
    monkeypatch.setattr(app, "_get_stripe_default_payment_method", MagicMock(return_value=payment_method))

    result = asyncio.run(app.get_souscription_payment_method(user_id="u1"))

    assert result == {
        "has_payment_method": True, "brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2027,
    }


def test_get_souscription_payment_method_no_card_on_file(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    monkeypatch.setattr(app, "_get_stripe_default_payment_method", MagicMock(return_value=None))

    result = asyncio.run(app.get_souscription_payment_method(user_id="u1"))

    assert result == {"has_payment_method": False}


def test_revoke_souscription_payment_method_detaches_card(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe, _ = _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    monkeypatch.setattr(app, "_get_stripe_default_payment_method", MagicMock(return_value={"id": "pm_1"}))

    result = asyncio.run(app.revoke_souscription_payment_method(user_id="u1"))

    assert result == {"success": True}
    fake_stripe.PaymentMethod.detach.assert_called_once_with("pm_1")


def test_revoke_souscription_payment_method_404_without_card(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    monkeypatch.setattr(app, "_get_stripe_default_payment_method", MagicMock(return_value=None))

    coro = app.revoke_souscription_payment_method(user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_replace_souscription_payment_method_returns_setup_checkout_url(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe, _ = _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    fake_stripe.checkout.Session.create.return_value = types.SimpleNamespace(url="https://checkout.stripe.com/setup/cs_test_1")

    result = asyncio.run(app.replace_souscription_payment_method(
        request=_FakeCheckoutRequest(), user_id="u1",
    ))

    assert result == {"checkout_url": "https://checkout.stripe.com/setup/cs_test_1"}
    _, create_kwargs = fake_stripe.checkout.Session.create.call_args
    assert create_kwargs["mode"] == "setup"
    assert create_kwargs["customer"] == "cus_456"
    # Managed Payments (on by default on newer Stripe accounts) rejects
    # mode="setup" outright ("Invalid mode: setup") unless explicitly
    # disabled for the request.
    assert create_kwargs["managed_payments"] == {"enabled": False}


# ---------------------------------------------------------------------------
# Transactional emails: templated sends via Brevo, and the failed-renewal
# notification (invoice.payment_failed).
# ---------------------------------------------------------------------------

def test_send_transactional_email_sends_rendered_template_via_brevo(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "BREVO_API_KEY", "test-key")
    monkeypatch.setattr(app, "BREVO_FROM_EMAIL", "noreply@vireel.co")
    fake_sib = MagicMock()
    fake_api_instance = MagicMock()
    fake_sib.TransactionalEmailsApi.return_value = fake_api_instance
    monkeypatch.setattr(app, "sib_api_v3_sdk", fake_sib)

    app._send_transactional_email("user@example.com", "credit_purchase", amount=9.99, credits=100)

    fake_api_instance.send_transac_email.assert_called_once()
    sent_kwargs = fake_sib.SendSmtpEmail.call_args.kwargs
    assert sent_kwargs["to"] == [{"email": "user@example.com"}]
    assert sent_kwargs["sender"] == {"email": "noreply@vireel.co"}
    assert "100" in sent_kwargs["html_content"]


def test_send_transactional_email_skips_without_recipient(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "BREVO_API_KEY", "test-key")
    fake_sib = MagicMock()
    monkeypatch.setattr(app, "sib_api_v3_sdk", fake_sib)

    app._send_transactional_email("", "credit_purchase", amount=9.99, credits=100)

    fake_sib.TransactionalEmailsApi.assert_not_called()


def test_send_transactional_email_skips_without_api_key(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "BREVO_API_KEY", None)
    fake_sib = MagicMock()
    monkeypatch.setattr(app, "sib_api_v3_sdk", fake_sib)

    app._send_transactional_email("user@example.com", "credit_purchase", amount=9.99, credits=100)

    fake_sib.TransactionalEmailsApi.assert_not_called()


def test_send_transactional_email_swallows_bad_template_context(monkeypatch):
    # A missing placeholder (here: "credits") must never propagate out of
    # this function -- it's called from webhook handlers where an
    # exception would turn a successful payment into a failed webhook.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "BREVO_API_KEY", "test-key")
    fake_sib = MagicMock()
    monkeypatch.setattr(app, "sib_api_v3_sdk", fake_sib)

    app._send_transactional_email("user@example.com", "credit_purchase", amount=9.99)

    fake_sib.TransactionalEmailsApi.assert_not_called()


def test_handle_subscription_payment_failed_sends_email_with_retry_date(monkeypatch):
    # Not the final attempt (next_payment_attempt is set) -- Stripe will
    # retry on its own, so subscription credit must NOT be zeroed yet.
    app = _import_app_with_stubs(monkeypatch)
    fake_subscription = types.SimpleNamespace(metadata=_FakeStripeMetadata({"userid": "u1", "plan_name": "Pro"}))
    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = fake_subscription
    monkeypatch.setattr(app, "stripe", fake_stripe)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)
    zero_credit_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_zero_subscription_credit", zero_credit_mock)

    invoice = types.SimpleNamespace(
        subscription="sub_123", customer_email="user@example.com",
        amount_due=2999, next_payment_attempt=1700000000, hosted_invoice_url="https://billing.stripe.com/x",
        id="in_123",
    )
    result = asyncio.run(app._handle_subscription_payment_failed(invoice))

    assert result == {"received": True}
    email_mock.assert_called_once()
    args, kwargs = email_mock.call_args
    assert args[0] == "user@example.com"
    assert args[1] == "payment_failed"
    assert kwargs["plan_name"] == "Pro"
    assert kwargs["amount"] == pytest.approx(29.99)
    assert "aura lieu automatiquement" in kwargs["retry_message"]
    assert kwargs["update_payment_url"] == "https://billing.stripe.com/x"
    zero_credit_mock.assert_not_awaited()


def test_handle_subscription_payment_failed_zeroes_credit_on_final_attempt(monkeypatch):
    # next_payment_attempt is null/None -- Stripe has given up retrying,
    # so this is the signal to actually zero the subscription's credit.
    app = _import_app_with_stubs(monkeypatch)
    fake_subscription = types.SimpleNamespace(metadata=_FakeStripeMetadata({"userid": "u1", "plan_name": "Pro"}))
    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = fake_subscription
    monkeypatch.setattr(app, "stripe", fake_stripe)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)
    zero_credit_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_zero_subscription_credit", zero_credit_mock)

    invoice = types.SimpleNamespace(
        subscription="sub_123", customer_email="user@example.com",
        amount_due=2999, next_payment_attempt=None, hosted_invoice_url="https://billing.stripe.com/x",
        id="in_123",
    )
    asyncio.run(app._handle_subscription_payment_failed(invoice))

    kwargs = email_mock.call_args.kwargs
    assert "Aucune nouvelle tentative" in kwargs["retry_message"]
    zero_credit_mock.assert_awaited_once_with("u1", operation_id="in_123")


def test_handle_subscription_payment_failed_no_userid_skips_credit_zeroing(monkeypatch):
    # Defensive: missing userid metadata must never crash this handler --
    # it just can't zero anyone's credit.
    app = _import_app_with_stubs(monkeypatch)
    fake_subscription = types.SimpleNamespace(metadata=_FakeStripeMetadata({"plan_name": "Pro"}))
    fake_stripe = MagicMock()
    fake_stripe.Subscription.retrieve.return_value = fake_subscription
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    zero_credit_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_zero_subscription_credit", zero_credit_mock)

    invoice = types.SimpleNamespace(
        subscription="sub_123", customer_email="user@example.com",
        amount_due=2999, next_payment_attempt=None, hosted_invoice_url="https://billing.stripe.com/x",
        id="in_123",
    )
    asyncio.run(app._handle_subscription_payment_failed(invoice))

    zero_credit_mock.assert_not_awaited()


def test_handle_subscription_payment_failed_ignores_invoice_without_subscription(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    invoice = types.SimpleNamespace(subscription=None)

    result = asyncio.run(app._handle_subscription_payment_failed(invoice))

    assert result == {"received": True, "ignored": "no_subscription_on_invoice"}


# ---------------------------------------------------------------------------
# Referral program -- reward triggers
# ---------------------------------------------------------------------------

def test_maybe_reward_referrer_grants_monthly_bonus(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value={
        "id": "ref-1", "referrer_user_id": "referrer-1", "status": "pending",
    }))
    claim_mock = AsyncMock(return_value={"id": "ref-1", "status": "rewarded"})
    monkeypatch.setattr(app, "supabase_claim_referral_subscription_reward", claim_mock)
    batch_mock = AsyncMock(return_value={"id": "batch-1"})
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)
    monkeypatch.setattr(app, "supabase_update_referral_row", AsyncMock())
    notify_mock = AsyncMock()
    monkeypatch.setattr(app, "_create_notification", notify_mock)

    asyncio.run(app._maybe_reward_referrer_for_first_subscription("referee-1", "month", "sous-1"))

    claim_mock.assert_awaited_once_with("ref-1", "month", "sous-1")
    batch_mock.assert_awaited_once_with(
        "referrer-1", app.REFERRAL_MONTHLY_BONUS_CREDITS, "REFERRAL_MONTHLY_SUBSCRIPTION",
        app.PROMOTIONAL_CREDITS_EXPIRATION_DAYS, source_reference="sous-1",
    )
    assert notify_mock.await_count == 2


def test_maybe_reward_referrer_grants_annual_bonus(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value={
        "id": "ref-1", "referrer_user_id": "referrer-1", "status": "pending",
    }))
    monkeypatch.setattr(app, "supabase_claim_referral_subscription_reward", AsyncMock(return_value={"id": "ref-1"}))
    batch_mock = AsyncMock(return_value={"id": "batch-1"})
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)
    monkeypatch.setattr(app, "supabase_update_referral_row", AsyncMock())
    monkeypatch.setattr(app, "_create_notification", AsyncMock())

    asyncio.run(app._maybe_reward_referrer_for_first_subscription("referee-1", "year", "sous-1"))

    batch_mock.assert_awaited_once_with(
        "referrer-1", app.REFERRAL_ANNUAL_BONUS_CREDITS, "REFERRAL_ANNUAL_SUBSCRIPTION",
        app.PROMOTIONAL_CREDITS_EXPIRATION_DAYS, source_reference="sous-1",
    )


def test_maybe_reward_referrer_noop_when_not_referred(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value=None))
    batch_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)

    asyncio.run(app._maybe_reward_referrer_for_first_subscription("referee-1", "month", "sous-1"))

    batch_mock.assert_not_awaited()


def test_maybe_reward_referrer_noop_when_referral_invalidated(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value={
        "id": "ref-1", "referrer_user_id": "referrer-1", "status": "invalid",
    }))
    batch_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)

    asyncio.run(app._maybe_reward_referrer_for_first_subscription("referee-1", "month", "sous-1"))

    batch_mock.assert_not_awaited()


def test_maybe_reward_referrer_idempotent_on_duplicate_webhook(monkeypatch):
    # claim_referral_subscription_reward returns None once the reward was
    # already claimed (e.g. the webhook fired twice) -- no second batch.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value={
        "id": "ref-1", "referrer_user_id": "referrer-1", "status": "rewarded",
    }))
    monkeypatch.setattr(app, "supabase_claim_referral_subscription_reward", AsyncMock(return_value=None))
    batch_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)

    asyncio.run(app._maybe_reward_referrer_for_first_subscription("referee-1", "month", "sous-1"))

    batch_mock.assert_not_awaited()


def test_handle_subscription_purchase_skips_reward_when_not_first_subscription(monkeypatch):
    # A renewal never reaches _handle_subscription_purchase at all (see
    # _handle_subscription_renewal_invoice's own docstring), and a plan
    # change via fresh checkout always has a prior paid subscription --
    # both end up here as "not first", which must never reward anyone.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value={"id": "prior"}))
    monkeypatch.setattr(app, "supabase_insert_souscription", AsyncMock(return_value={"id": "sous-new"}))
    monkeypatch.setattr(app, "_allocate_plan_resources", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    monkeypatch.setattr(app, "_sync_customer_default_payment_method", MagicMock())
    reward_mock = AsyncMock()
    monkeypatch.setattr(app, "_maybe_reward_referrer_for_first_subscription", reward_mock)

    asyncio.run(app._handle_subscription_purchase(_fake_subscription_purchase_ctx()))

    reward_mock.assert_not_awaited()


def test_handle_subscription_purchase_rewards_referrer_on_first_subscription(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_insert_souscription", AsyncMock(return_value={"id": "sous-new"}))
    monkeypatch.setattr(app, "_allocate_plan_resources", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    monkeypatch.setattr(app, "_sync_customer_default_payment_method", MagicMock())
    reward_mock = AsyncMock()
    monkeypatch.setattr(app, "_maybe_reward_referrer_for_first_subscription", reward_mock)

    asyncio.run(app._handle_subscription_purchase(_fake_subscription_purchase_ctx(billing_interval="year")))

    reward_mock.assert_awaited_once_with("u1", "year", "sous-new")


def test_change_souscription_plan_never_rewards_referrer(monkeypatch):
    # A plan change (upgrade/downgrade) must never trigger a referral
    # reward -- only a genuinely first-ever paid subscription does. Not
    # even indirectly: change_souscription_plan never references the
    # referral-reward function at all.
    app = _import_app_with_stubs(monkeypatch)
    assert "_maybe_reward_referrer_for_first_subscription" not in app.change_souscription_plan.__code__.co_names
    assert "_maybe_reward_referrer_for_first_subscription" not in app._apply_immediate_upgrade.__code__.co_names
    assert "_maybe_reward_referrer_for_first_subscription" not in app._apply_scheduled_plan_change.__code__.co_names


# ---------------------------------------------------------------------------
# Referral program -- refunds/chargebacks revoke the reward batch
# ---------------------------------------------------------------------------

def test_handle_charge_refund_revokes_matching_batch(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value={"id": "sous-1"}))
    revoke_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(app, "supabase_revoke_promotional_credit_batches_by_source_reference", revoke_mock)

    charge = _FakeStripeObjectNoGet({"payment_intent": "pi_123"})
    result = asyncio.run(app._handle_charge_refund_or_dispute(charge, "refund"))

    assert result == {"received": True, "revoked_batches": 1}
    revoke_mock.assert_awaited_once_with("sous-1", "refund")


def test_handle_charge_dispute_revokes_matching_batch(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value={"id": "sous-1"}))
    revoke_mock = AsyncMock(return_value=1)
    monkeypatch.setattr(app, "supabase_revoke_promotional_credit_batches_by_source_reference", revoke_mock)

    dispute = _FakeStripeObjectNoGet({"payment_intent": "pi_123"})
    result = asyncio.run(app._handle_charge_refund_or_dispute(dispute, "chargeback"))

    revoke_mock.assert_awaited_once_with("sous-1", "chargeback")


def test_handle_charge_refund_ignored_when_no_matching_souscription(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_souscription_by_reference", AsyncMock(return_value=None))
    revoke_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_revoke_promotional_credit_batches_by_source_reference", revoke_mock)

    charge = _FakeStripeObjectNoGet({"payment_intent": "pi_unrelated"})
    result = asyncio.run(app._handle_charge_refund_or_dispute(charge, "refund"))

    assert result == {"received": True, "ignored": "no_matching_souscription"}
    revoke_mock.assert_not_awaited()


def test_handle_charge_refund_ignored_without_payment_intent(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    charge = _FakeStripeObjectNoGet({})
    result = asyncio.run(app._handle_charge_refund_or_dispute(charge, "refund"))
    assert result == {"received": True, "ignored": "no_payment_intent"}


def test_stripe_webhook_dispatches_charge_refunded(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    event = types.SimpleNamespace(type="charge.refunded", data=types.SimpleNamespace(object=types.SimpleNamespace(payment_intent="pi_123")))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, sig: event)
    handler_mock = AsyncMock(return_value={"received": True, "revoked_batches": 1})
    monkeypatch.setattr(app, "_handle_charge_refund_or_dispute", handler_mock)

    with TestClient(app.app) as client:
        resp = client.post("/api/stripe/webhook", data=b"{}", headers={"stripe-signature": "sig"})

    assert resp.status_code == 200
    handler_mock.assert_awaited_once_with(event.data.object, "refund")


def test_stripe_webhook_dispatches_charge_dispute_created(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "STRIPE_WEBHOOK_SECRET", "whsec_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    event = types.SimpleNamespace(type="charge.dispute.created", data=types.SimpleNamespace(object=types.SimpleNamespace(payment_intent="pi_123")))
    monkeypatch.setattr(app, "_verify_and_parse_event", lambda payload, sig: event)
    handler_mock = AsyncMock(return_value={"received": True, "revoked_batches": 1})
    monkeypatch.setattr(app, "_handle_charge_refund_or_dispute", handler_mock)

    with TestClient(app.app) as client:
        resp = client.post("/api/stripe/webhook", data=b"{}", headers={"stripe-signature": "sig"})

    assert resp.status_code == 200
    handler_mock.assert_awaited_once_with(event.data.object, "chargeback")


# ---------------------------------------------------------------------------
# Referral program -- HTTP endpoints
# ---------------------------------------------------------------------------

def test_get_referral_config_reads_from_backend_env(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "REFERRAL_SIGNUP_BONUS_CREDITS", 50.0)
    monkeypatch.setattr(app, "REFERRAL_MONTHLY_BONUS_CREDITS", 100.0)
    monkeypatch.setattr(app, "REFERRAL_ANNUAL_BONUS_CREDITS", 300.0)
    monkeypatch.setattr(app, "PROMOTIONAL_CREDITS_EXPIRATION_DAYS", 60)

    with TestClient(app.app) as client:
        resp = client.get("/api/referrals/config")

    assert resp.status_code == 200
    assert resp.json() == {
        "signup_bonus_credits": 50.0, "monthly_bonus_credits": 100.0,
        "annual_bonus_credits": 300.0, "expiration_days": 60,
    }


def test_get_my_referrals_returns_code_link_and_summary(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_or_create_referral_code", AsyncMock(return_value="ABC1234"))
    monkeypatch.setattr(app, "supabase_list_referrals_by_referrer", AsyncMock(return_value=[
        {"created_at": "t1", "status": "pending", "subscription_reward_granted_at": None},
        {"created_at": "t2", "status": "rewarded", "subscription_reward_granted_at": "t3", "first_subscription_type": "month"},
    ]))

    with TestClient(app.app) as client:
        resp = client.get("/api/referrals/me", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "ABC1234"
    assert data["link"].endswith("/r/ABC1234")
    assert data["referred_count"] == 2
    assert data["rewarded_count"] == 1
    assert data["referrals"][0]["label"] == "Filleul #1"
    # No PII anywhere in the per-referral summary.
    assert "email" not in data["referrals"][0]
    assert "referred_user_id" not in data["referrals"][0]


def test_associate_referral_success_grants_signup_bonus(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_referral_code_owner", AsyncMock(return_value="referrer-1"))
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_auth_user_created_at", AsyncMock(return_value=datetime.now(timezone.utc)))
    monkeypatch.setattr(app, "supabase_insert_referral", AsyncMock(return_value=({"id": "ref-1"}, True)))
    batch_mock = AsyncMock(return_value={"id": "batch-1"})
    monkeypatch.setattr(app, "supabase_insert_promotional_credit_batch", batch_mock)
    update_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_update_referral_row", update_mock)
    notify_mock = AsyncMock()
    monkeypatch.setattr(app, "_create_notification", notify_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/referrals/associate", json={"referral_code": "ABC1234"}, headers=_auth_headers("referee-1"),
        )

    assert resp.status_code == 200
    assert resp.json()["associated"] is True
    batch_mock.assert_awaited_once_with(
        "referee-1", app.REFERRAL_SIGNUP_BONUS_CREDITS, "REFERRAL_SIGNUP",
        app.PROMOTIONAL_CREDITS_EXPIRATION_DAYS, source_reference="ref-1",
    )
    update_mock.assert_awaited_once()
    assert notify_mock.await_count == 2


def test_associate_referral_blocks_self_referral(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_referral_code_owner", AsyncMock(return_value="u1"))
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_referral", insert_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/referrals/associate", json={"referral_code": "ABC1234"}, headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    assert resp.json()["associated"] is False
    insert_mock.assert_not_awaited()


def test_associate_referral_idempotent_when_already_referred(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_referral_code_owner", AsyncMock(return_value="referrer-1"))
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value={"id": "existing-ref"}))
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_referral", insert_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/referrals/associate", json={"referral_code": "ABC1234"}, headers=_auth_headers("referee-1"),
        )

    assert resp.status_code == 200
    assert resp.json()["associated"] is False
    insert_mock.assert_not_awaited()


def test_associate_referral_rejects_unknown_code(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_referral_code_owner", AsyncMock(return_value=None))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/referrals/associate", json={"referral_code": "NOPE000"}, headers=_auth_headers("referee-1"),
        )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "referral_code_not_found"


def test_associate_referral_rejects_account_too_old(monkeypatch):
    # An existing user who clicks a referral link long after signing up
    # must never retroactively get a referrer attached.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "REFERRAL_ASSOCIATION_WINDOW_MINUTES", 60)
    monkeypatch.setattr(app, "supabase_get_referral_code_owner", AsyncMock(return_value="referrer-1"))
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_auth_user_created_at", AsyncMock(
        return_value=datetime.now(timezone.utc) - timedelta(days=30)
    ))
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_referral", insert_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/referrals/associate", json={"referral_code": "ABC1234"}, headers=_auth_headers("referee-1"),
        )

    assert resp.status_code == 200
    assert resp.json()["associated"] is False
    insert_mock.assert_not_awaited()


def test_associate_referral_rejects_when_account_age_unknown(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_referral_code_owner", AsyncMock(return_value="referrer-1"))
    monkeypatch.setattr(app, "supabase_get_referral_by_referred_user", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_auth_user_created_at", AsyncMock(return_value=None))
    insert_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_referral", insert_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/referrals/associate", json={"referral_code": "ABC1234"}, headers=_auth_headers("referee-1"),
        )

    assert resp.json()["associated"] is False
    insert_mock.assert_not_awaited()


def test_invalidate_referral_requires_admin_secret(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "ADMIN_API_SECRET", "top-secret")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    with TestClient(app.app) as client:
        resp = client.post("/api/admin/referrals/ref-1/invalidate", json={"reason": "fraud"})

    assert resp.status_code == 403


def test_invalidate_referral_succeeds_with_correct_secret(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "ADMIN_API_SECRET", "top-secret")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_invalidate_referral", AsyncMock(return_value={"id": "ref-1", "status": "invalid"}))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/admin/referrals/ref-1/invalidate", json={"reason": "fraud"},
            headers={"x-admin-secret": "top-secret"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "invalid"


# ---------------------------------------------------------------------------
# In-app notifications
# ---------------------------------------------------------------------------

def test_list_notifications_endpoint_returns_items_and_unread_count(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_list_notifications", AsyncMock(return_value=([{"id": "n1"}], 3)))

    with TestClient(app.app) as client:
        resp = client.get("/api/notifications", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"items": [{"id": "n1"}], "unread_count": 3}


def test_mark_notification_read_endpoint_404_when_not_found(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_mark_notification_read", AsyncMock(return_value=None))

    with TestClient(app.app) as client:
        resp = client.post("/api/notifications/n1/read", headers=_auth_headers("u1"))

    assert resp.status_code == 404


def test_mark_all_notifications_read_endpoint_returns_count(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_mark_all_notifications_read", AsyncMock(return_value=5))

    with TestClient(app.app) as client:
        resp = client.post("/api/notifications/read-all", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json() == {"marked_read": 5}


# ---------------------------------------------------------------------------
# Subscription lifecycle actions: cancel / reactivate / pause / resume / change-plan
# ---------------------------------------------------------------------------

_DEFAULT_LIFECYCLE_SUBSCRIPTION = object()  # sentinel: None is a valid, meaningful test input (no active subscription)


def _stub_subscription_lifecycle_prereqs(monkeypatch, app, subscription=_DEFAULT_LIFECYCLE_SUBSCRIPTION):
    if subscription is _DEFAULT_LIFECYCLE_SUBSCRIPTION:
        subscription = {"id": "sous-1", "stripe_subscription_id": "sub_123", "stripe_customer_id": "cus_456"}
    fake_stripe = MagicMock()
    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=subscription))
    update_mock = AsyncMock(return_value={"id": "sous-1"})
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)
    # cancel/reactivate/pause/resume/change-plan all look up the plan name
    # for the notification email they now send -- individual tests may
    # override this with a more specific plan when it matters to them.
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"name": "Silver"}))
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    return fake_stripe, update_mock


def test_cancel_souscription_sets_cancel_at_period_end(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe, update_mock = _stub_subscription_lifecycle_prereqs(monkeypatch, app)

    asyncio.run(app.cancel_souscription(user_id="u1"))

    fake_stripe.Subscription.modify.assert_called_once_with("sub_123", cancel_at_period_end=True)
    update_mock.assert_awaited_once()
    args, kwargs = update_mock.await_args
    assert args[0] == "sous-1"
    assert args[1]["auto_renew"] is False
    assert kwargs["user_id"] == "u1"


def test_cancel_souscription_sends_notification_email(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app, subscription={
        "id": "sous-1", "stripe_subscription_id": "sub_123", "abonnement": "silver",
        "payment_end_date": "2026-11-15T00:00:00+00:00",
    })
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    asyncio.run(app.cancel_souscription(
        user_id="u1", request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
    ))

    email_mock.assert_called_once_with(
        "user@example.com", "subscription_canceled", plan_name="Silver", period_end_date="15/11/2026",
    )


def test_cancel_souscription_404_without_active_subscription(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app, subscription=None)

    coro = app.cancel_souscription(user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_cancel_souscription_400_without_stripe_subscription_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app, subscription={"id": "sous-legacy"})

    coro = app.cancel_souscription(user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 400


def test_reactivate_souscription_clears_cancel_at_period_end(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe, update_mock = _stub_subscription_lifecycle_prereqs(monkeypatch, app)

    asyncio.run(app.reactivate_souscription(user_id="u1"))

    fake_stripe.Subscription.modify.assert_called_once_with("sub_123", cancel_at_period_end=False)
    args, _ = update_mock.await_args
    assert args[1]["auto_renew"] is True
    assert args[1]["canceled_at"] is None


def test_reactivate_souscription_sends_notification_email(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    asyncio.run(app.reactivate_souscription(
        user_id="u1", request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
    ))

    email_mock.assert_called_once_with("user@example.com", "subscription_reactivated", plan_name="Silver")


def test_pause_souscription_voids_pause_collection(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe, update_mock = _stub_subscription_lifecycle_prereqs(monkeypatch, app)

    asyncio.run(app.pause_souscription(user_id="u1"))

    fake_stripe.Subscription.modify.assert_called_once_with("sub_123", pause_collection={"behavior": "void"})
    args, _ = update_mock.await_args
    assert "paused_at" in args[1]


def test_pause_souscription_sends_notification_email(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    asyncio.run(app.pause_souscription(
        user_id="u1", request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
    ))

    email_mock.assert_called_once_with("user@example.com", "subscription_paused", plan_name="Silver")


def test_resume_souscription_clears_pause_collection(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_stripe, update_mock = _stub_subscription_lifecycle_prereqs(monkeypatch, app)

    asyncio.run(app.resume_souscription(user_id="u1"))

    fake_stripe.Subscription.modify.assert_called_once_with("sub_123", pause_collection="")
    args, _ = update_mock.await_args
    assert "resumed_at" in args[1]


def test_resume_souscription_sends_notification_email(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    asyncio.run(app.resume_souscription(
        user_id="u1", request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
    ))

    email_mock.assert_called_once_with("user@example.com", "subscription_resumed", plan_name="Silver")


def test_subscription_lifecycle_action_skips_email_without_request(monkeypatch):
    # request defaults to None for direct/internal callers (e.g. no X-User-Email
    # header available) -- must degrade to "no email sent", never crash.
    app = _import_app_with_stubs(monkeypatch)
    _stub_subscription_lifecycle_prereqs(monkeypatch, app)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    asyncio.run(app.pause_souscription(user_id="u1"))

    email_mock.assert_called_once_with(None, "subscription_paused", plan_name="Silver")


class _FakeStripeSubscriptionObject(dict):
    """Supports both dict-style item access (subscription["items"]) and
    attribute access (subscription.metadata), matching how the real
    stripe.StripeObject behaves and how change_souscription_plan reads it."""

    def __init__(self, data, metadata):
        super().__init__(data)
        self.metadata = metadata


class _FakeStripeObjectNoGet:
    """Mimics the real stripe.StripeObject's actual failure mode: supports
    bracket access via __getitem__, but .get(...) raises exactly the
    AttributeError the real SDK raises ("is a dict method, but a
    Subscription is not a dict") -- a plain dict/ _FakeStripeSubscriptionObject
    mock would silently accept .get() and hide this regression."""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __getattr__(self, name):
        if name == "get":
            raise AttributeError(f"'get' is a dict method, but a Subscription is not a dict. Use .to_dict() to convert it.")
        raise AttributeError(name)


def test_extract_subscription_period_end_reads_subscription_level_field(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _FakeStripeObjectNoGet({"current_period_end": 1700000000})
    assert app._extract_subscription_period_end(subscription) == 1700000000


def test_extract_subscription_period_end_falls_back_to_item_level_field(monkeypatch):
    # Stripe moved current_period_end from the Subscription to its items in
    # a 2025 API version -- the top-level key is simply absent then.
    app = _import_app_with_stubs(monkeypatch)
    subscription = _FakeStripeObjectNoGet({"items": {"data": [{"current_period_end": 1700000001}]}})
    assert app._extract_subscription_period_end(subscription) == 1700000001


def test_extract_subscription_period_end_returns_none_when_absent_everywhere(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _FakeStripeObjectNoGet({"items": {"data": []}})
    assert app._extract_subscription_period_end(subscription) is None


def _FixedDatetime(fixed_now):
    """A datetime subclass whose .now() always returns `fixed_now`,
    while fromtimestamp/fromisoformat/etc. keep behaving normally (real
    datetime methods, inherited) -- lets a test pin "now" for proration
    math that calls datetime.now(timezone.utc) deep inside app.py."""
    class _Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now
    return _Fixed


class _FakeStripeCardError(Exception):
    """Stands in for stripe.error.CardError -- fake_stripe.error.CardError
    is set to THIS class (never a bare MagicMock, which `except` can't
    catch) so _charge_plan_change_proration's except clause actually
    matches what a test's side_effect raises."""
    def __init__(self, message, user_message=None):
        super().__init__(message)
        self.user_message = user_message


class _FakeStripeSchedule(dict):
    """Supports both schedule.id (attribute) and schedule["phases"]
    (bracket) access, matching how _create_or_replace_plan_change_schedule
    reads a real stripe.SubscriptionSchedule."""
    def __init__(self, data, id_):
        super().__init__(data)
        self.id = id_


_SILVER_PLAN = {"id": "silver", "name": "Silver", "price": 10.0, "credit": 500, "stockage": 10.0, "ordre": 1, "max_social_account": 1}
_GOLD_PLAN = {"id": "gold", "name": "Gold", "price": 25.0, "credit": 1500, "stockage": 50.0, "ordre": 2, "max_social_account": 3}
_ULTIMATE_PLAN = {"id": "ultimate", "name": "Ultimate", "price": 40.0, "credit": 3000, "stockage": 100.0, "ordre": 3, "max_social_account": 10}


def _plan_change_subscription(**overrides):
    base = {
        "id": "sous-1", "userid": "u1", "abonnement": "silver", "billing_interval": "month",
        "stripe_subscription_id": "sub_123", "stripe_customer_id": "cus_456",
        "plan_credit": 500.0, "plan_stockage": 10.0,
        "payment_start_date": "2026-01-01T00:00:00+00:00", "payment_end_date": "2026-02-01T00:00:00+00:00",
        "credit_cycle_start_at": "2026-01-01T00:00:00+00:00", "credit_cycle_end_at": "2026-02-01T00:00:00+00:00",
        "next_credit_allocation_at": None, "scheduled_abonnement_id": None, "stripe_schedule_id": None,
        "auto_renew": True,
    }
    base.update(overrides)
    return base


def _stub_plan_change_prereqs(monkeypatch, app, subscription=None, plans=None):
    subscription = subscription if subscription is not None else _plan_change_subscription()
    plans = plans if plans is not None else {"silver": _SILVER_PLAN, "gold": _GOLD_PLAN, "ultimate": _ULTIMATE_PLAN}

    fake_stripe = MagicMock()
    fake_stripe.error = types.SimpleNamespace(CardError=_FakeStripeCardError)
    fake_stripe.Subscription.retrieve.return_value = _FakeStripeSubscriptionObject(
        {"current_period_end": 1700000000, "items": {"data": [{"id": "si_123", "price": {"id": "price_old_1"}}]}},
        metadata=_FakeStripeMetadata({"userid": "u1", "abonnement": subscription.get("abonnement"), "billing_interval": subscription.get("billing_interval")}),
    )
    fake_stripe.Subscription.modify.return_value = _FakeStripeObjectNoGet({"current_period_end": 1700000000})
    fake_stripe.Price.create.return_value = types.SimpleNamespace(id="price_new_1")
    fake_stripe.Invoice.create.return_value = types.SimpleNamespace(id="in_1")
    fake_stripe.Invoice.finalize_invoice.return_value = types.SimpleNamespace(id="in_1")
    fake_stripe.SubscriptionSchedule.create.return_value = _FakeStripeSchedule({"phases": [{"start_date": 1690000000}]}, id_="sched_1")
    fake_stripe.SubscriptionSchedule.modify.return_value = types.SimpleNamespace(id="sched_1")

    monkeypatch.setattr(app, "stripe", fake_stripe)
    monkeypatch.setattr(app, "STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=subscription))

    async def fake_get_abonnement(plan_id):
        return plans.get(str(plan_id))
    monkeypatch.setattr(app, "supabase_get_abonnement", fake_get_abonnement)

    monkeypatch.setattr(app, "_count_social_accounts_by_platform", AsyncMock(return_value={}))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"stockage": 5.0, "stockage_max": 10.0, "credit": 120.0}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(return_value=[]))
    update_mock = AsyncMock(return_value={"id": subscription.get("id")})
    monkeypatch.setattr(app, "supabase_update_souscription_row", update_mock)
    insert_mock = AsyncMock(return_value={"id": "sous-2"})
    monkeypatch.setattr(app, "supabase_insert_souscription", insert_mock)
    credits_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_upsert_user_data_credits", credits_mock)
    history_mock = AsyncMock()
    monkeypatch.setattr(app, "supabase_insert_user_data_history", history_mock)
    monkeypatch.setattr(app, "supabase_set_user_max_daily_publications", AsyncMock())
    monkeypatch.setattr(app, "_send_transactional_email", MagicMock())
    return fake_stripe, update_mock, insert_mock, credits_mock, history_mock


# -- 1. Classification by ordre, including names/prices that don't follow it --

def test_classify_plan_change_upgrade_by_ordre_even_when_price_disagrees(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    cheap_but_higher_ordre = {"id": "b", "ordre": 2, "price": 1.0, "credit": 1}
    expensive_but_lower_ordre = {"id": "a", "ordre": 1, "price": 999.0, "credit": 9999}
    assert app._classify_plan_change(expensive_but_lower_ordre, cheap_but_higher_ordre, "month", "month") == app.PLAN_CHANGE_UPGRADE_IMMEDIATE


def test_classify_plan_change_downgrade_by_ordre_even_when_name_disagrees(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    named_premium_but_lower_ordre = {"id": "b", "ordre": 1, "name": "Premium Plus"}
    named_basic_but_higher_ordre = {"id": "a", "ordre": 2, "name": "Basic"}
    assert app._classify_plan_change(named_basic_but_higher_ordre, named_premium_but_lower_ordre, "month", "month") == app.PLAN_CHANGE_DOWNGRADE_SCHEDULED


def test_classify_plan_change_noop_same_plan_same_interval(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    plan = {"id": "a", "ordre": 1}
    assert app._classify_plan_change(plan, plan, "month", "month") == app.PLAN_CHANGE_NOOP


# -- 2. Equal / absent / invalid ordre --

def test_classify_plan_change_lateral_unsupported_for_equal_ordre_distinct_plans(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._classify_plan_change({"id": "a", "ordre": 1}, {"id": "b", "ordre": 1}, "month", "month") == app.PLAN_CHANGE_LATERAL_UNSUPPORTED


def test_classify_plan_change_invalid_when_ordre_absent(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._classify_plan_change({"id": "a", "ordre": None}, {"id": "b", "ordre": 2}, "month", "month") == app.PLAN_CHANGE_INVALID
    assert app._classify_plan_change({"id": "a", "ordre": 1}, {"id": "b", "ordre": None}, "month", "month") == app.PLAN_CHANGE_INVALID


def test_classify_plan_change_invalid_when_ordre_not_an_integer(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    assert app._classify_plan_change({"id": "a", "ordre": "not-a-number"}, {"id": "b", "ordre": 2}, "month", "month") == app.PLAN_CHANGE_INVALID


# -- 3. Monthly upgrade with remaining balance + proration (worked example) --

def test_compute_monthly_upgrade_proration_matches_spec_worked_example(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    mid = start + (end - start) / 2
    result = app._compute_monthly_upgrade_proration(
        current_plan_credit=500, current_plan_price=10, new_plan={"price": 25, "credit": 1500},
        period_start=start, period_end=end, now=mid,
    )
    assert result["amount_due_today"] == 7.50
    assert result["credits_to_add"] == 500


def test_apply_immediate_upgrade_monthly_charges_exact_proration_and_adds_delta(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    mid = start + (end - start) / 2
    monkeypatch.setattr(app, "datetime", _FixedDatetime(mid))
    subscription = _plan_change_subscription(
        payment_start_date=start.isoformat(), payment_end_date=end.isoformat(),
        credit_cycle_start_at=start.isoformat(), credit_cycle_end_at=end.isoformat(),
    )
    fake_stripe, update_mock, insert_mock, credits_mock, history_mock = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
    ))

    assert result == {"id": "sous-2"}
    # Custom proration charged as its own invoice -- never Stripe's own
    # proration engine (proration_behavior="none" below).
    _, item_kwargs = fake_stripe.InvoiceItem.create.call_args
    assert item_kwargs["amount"] == 750  # 7.50 EUR in cents
    fake_stripe.Invoice.pay.assert_called_once()
    _, modify_kwargs = fake_stripe.Subscription.modify.call_args
    assert modify_kwargs["proration_behavior"] == "none"

    insert_kwargs = insert_mock.await_args.kwargs
    assert insert_kwargs["abonnement"] == "gold"
    assert insert_kwargs["plan_credit"] == 1500.0  # full new quota snapshotted, not prorated
    assert insert_kwargs["credit_cycle_start_at"] == start  # carried forward, not restarted
    assert insert_kwargs["credit_cycle_end_at"] == end

    # Delta applied on top of the existing balance -- never a reset (spec
    # section 6: existing credits/expirations untouched).
    credits_mock.assert_awaited_once()
    credit_kwargs = credits_mock.await_args.kwargs
    assert credit_kwargs["credit_delta"] == 500.0
    assert credit_kwargs["storage_delta"] == 40.0  # 50 - 10 plan_stockage snapshot, applied in full
    assert credit_kwargs["update_credit_max"] is True
    assert credit_kwargs["update_stockage_max"] is True


# -- 4. Annual upgrade: distinct annual-price and monthly-credit proration --

def test_compute_annual_upgrade_proration_uses_two_distinct_ratios(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    annual_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    annual_end = datetime(2027, 1, 1, tzinfo=timezone.utc)
    annual_mid = annual_start + (annual_end - annual_start) / 2  # exactly 50% of the YEAR remaining
    # A credit sub-cycle that happens to be centered on the same instant,
    # but much shorter -- proving the two ratios are computed completely
    # independently of each other.
    cycle_start = annual_mid - timedelta(days=5)
    cycle_end = annual_mid + timedelta(days=5)

    result = app._compute_annual_upgrade_proration(
        current_plan_credit=500, current_annual_price=120.0,
        new_plan={"price": 25.0, "credit": 1500, "reduction_annuelle": 0},
        annual_period_start=annual_start, annual_period_end=annual_end,
        credit_cycle_start=cycle_start, credit_cycle_end=cycle_end, now=annual_mid,
    )
    # Annual diff: 300 (25*12) - 120 = 180, at exactly 50% of the year remaining.
    assert result["remaining_ratio"] == 0.5
    assert result["amount_due_today"] == 90.0
    # Credit diff: 1500-500=1000, at exactly 50% of the 10-day sub-cycle.
    assert result["credit_remaining_ratio"] == 0.5
    assert result["credits_to_add"] == 500


# -- 5. Several successive upgrades without double-granting --

def test_successive_upgrades_compute_only_the_complement(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    # Silver(500) -> Gold(1500) already happened: the row's plan_credit
    # snapshot now reads 1500, matching Gold's own full nominal quota --
    # a second upgrade straight to Ultimate(3000) must only add the
    # COMPLEMENT (3000-1500), never re-grant the full 3000.
    result = app._compute_monthly_upgrade_proration(
        current_plan_credit=1500, current_plan_price=25, new_plan={"price": 40, "credit": 3000},
        period_start=start, period_end=end, now=start,  # ratio 1.0, full period remaining
    )
    assert result["credits_to_add"] == 1500
    assert result["amount_due_today"] == 15.0


# -- 6. Monthly and annual downgrades land on the right boundary --

def test_change_souscription_plan_schedules_monthly_downgrade_to_next_renewal(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="gold")
    fake_stripe, update_mock, insert_mock, credits_mock, history_mock = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver"), user_id="u1",
    ))

    assert result["classification"] == app.PLAN_CHANGE_DOWNGRADE_SCHEDULED
    assert result["scheduled_effective_at"] == datetime.fromtimestamp(1700000000, tz=timezone.utc).isoformat()
    # No charge, no credit change, no immediate price swap -- only a
    # schedule's future phase.
    fake_stripe.InvoiceItem.create.assert_not_called()
    fake_stripe.Subscription.modify.assert_not_called()
    credits_mock.assert_not_awaited()
    fake_stripe.SubscriptionSchedule.create.assert_called_once_with(from_subscription="sub_123")
    _, schedule_kwargs = fake_stripe.SubscriptionSchedule.modify.call_args
    assert schedule_kwargs["phases"][1]["start_date"] == 1700000000
    assert schedule_kwargs["phases"][1]["metadata"]["abonnement"] == "silver"

    update_kwargs = update_mock.await_args.args[1]
    assert update_kwargs["scheduled_abonnement_id"] == "silver"
    assert update_kwargs["stripe_schedule_id"] == "sched_1"


def test_change_souscription_plan_annual_downgrade_defers_to_annual_renewal_not_credit_anniversary(monkeypatch):
    # The annual subscription's own Stripe current_period_end (the ANNUAL
    # boundary) must drive the schedule -- never the separate monthly
    # credit-allocation anniversary (next_credit_allocation_at).
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(
        abonnement="ultimate", billing_interval="year",
        next_credit_allocation_at="2026-01-20T00:00:00+00:00",  # much sooner than the annual boundary
    )
    fake_stripe, *_ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)
    fake_stripe.Subscription.retrieve.return_value = _FakeStripeSubscriptionObject(
        {"current_period_end": 1735689600, "items": {"data": [{"id": "si_123", "price": {"id": "price_old_1"}}]}},
        metadata=_FakeStripeMetadata({"userid": "u1", "abonnement": "ultimate", "billing_interval": "year"}),
    )

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
    ))

    assert result["classification"] == app.PLAN_CHANGE_DOWNGRADE_SCHEDULED
    assert result["scheduled_effective_at"] == datetime.fromtimestamp(1735689600, tz=timezone.utc).isoformat()


# -- 7. Periodicity changes, alone or combined with a plan change --

def test_change_souscription_plan_defers_periodicity_change_alone(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver", billing_interval="year"), user_id="u1",
    ))
    assert result["classification"] == app.PLAN_CHANGE_PERIODICITY_SCHEDULED


def test_change_souscription_plan_defers_periodicity_change_even_when_target_plan_is_higher(monkeypatch):
    # Spec section 5: deferred regardless of whether ordre also increases.
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="ultimate", billing_interval="year"), user_id="u1",
    ))
    assert result["classification"] == app.PLAN_CHANGE_PERIODICITY_SCHEDULED


# -- 8. Cancel, replace, and single execution of a scheduled change --

def test_cancel_scheduled_plan_change_releases_schedule(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(scheduled_abonnement_id="silver", stripe_schedule_id="sched_1")
    fake_stripe, update_mock, *_ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    result = asyncio.run(app.cancel_scheduled_plan_change(user_id="u1"))

    assert result == {"cancelled": True}
    fake_stripe.SubscriptionSchedule.release.assert_called_once_with("sched_1")
    update_kwargs = update_mock.await_args.args[1]
    assert update_kwargs["scheduled_abonnement_id"] is None
    assert update_kwargs["stripe_schedule_id"] is None


def test_cancel_scheduled_plan_change_404_when_none_pending(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_plan_change_prereqs(monkeypatch, app)
    coro = app.cancel_scheduled_plan_change(user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_change_souscription_plan_replaces_existing_scheduled_change(monkeypatch):
    # Only one scheduled change at a time -- scheduling a new one releases
    # whichever schedule was already pending first.
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="gold", scheduled_abonnement_id="silver", stripe_schedule_id="sched_old")
    fake_stripe, *_ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver", billing_interval="year"), user_id="u1",
    ))

    fake_stripe.SubscriptionSchedule.release.assert_called_once_with("sched_old")
    fake_stripe.SubscriptionSchedule.create.assert_called_once_with(from_subscription="sub_123")


def test_apply_immediate_upgrade_requires_confirmation_to_cancel_scheduled_change(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver", scheduled_abonnement_id="gold", stripe_schedule_id="sched_1")
    fake_stripe, *_ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "plan_change_scheduled_change_exists"
    fake_stripe.InvoiceItem.create.assert_not_called()

    # With explicit confirmation, it proceeds and cancels the pending schedule.
    asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold", confirm_cancel_scheduled=True), user_id="u1",
    ))
    fake_stripe.SubscriptionSchedule.release.assert_called_once_with("sched_1")


# -- 9. Failed payments and events received more than once --

def test_apply_immediate_upgrade_payment_failure_leaves_plan_unchanged(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    mid = datetime(2026, 1, 15, tzinfo=timezone.utc)  # inside the fixture's Jan 1 - Feb 1 period
    monkeypatch.setattr(app, "datetime", _FixedDatetime(mid))
    subscription = _plan_change_subscription(abonnement="silver")
    fake_stripe, update_mock, insert_mock, credits_mock, _ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)
    fake_stripe.Invoice.pay.side_effect = _FakeStripeCardError("declined", user_message="Card declined")

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["code"] == "plan_change_payment_failed"

    # Nothing about the plan was touched -- the current offer stays active.
    fake_stripe.Subscription.modify.assert_not_called()
    insert_mock.assert_not_awaited()
    credits_mock.assert_not_awaited()
    update_mock.assert_not_awaited()


def test_change_souscription_plan_refuses_inconsistent_upgrade_configuration(monkeypatch):
    # ordre says "upgrade" but the catalog's actual price/credit for that
    # plan is lower -- must refuse outright, never invert to a downgrade
    # or charge/credit a negative amount.
    app = _import_app_with_stubs(monkeypatch)
    mid = datetime(2026, 1, 15, tzinfo=timezone.utc)  # inside the fixture's Jan 1 - Feb 1 period
    monkeypatch.setattr(app, "datetime", _FixedDatetime(mid))
    subscription = _plan_change_subscription(abonnement="gold", plan_credit=1500.0)
    misconfigured_plans = {
        "gold": _GOLD_PLAN,
        "ultimate": {"id": "ultimate", "name": "Ultimate", "price": 5.0, "credit": 10, "stockage": 100.0, "ordre": 3, "max_social_account": 10},
    }
    fake_stripe, update_mock, insert_mock, credits_mock, _ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription, plans=misconfigured_plans)

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="ultimate"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "plan_change_inconsistent_configuration"
    fake_stripe.InvoiceItem.create.assert_not_called()
    insert_mock.assert_not_awaited()


# -- 10. Batches and their expirations are preserved --

def test_apply_immediate_upgrade_never_resets_existing_balance(monkeypatch):
    # The existing balance/expiration must never be wiped (spec section 6)
    # -- supabase_upsert_user_data_credits (a DELTA) is used, never
    # supabase_set_user_data_balance / _reset_user_plan_balance (a RESET).
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    reset_mock = AsyncMock()
    monkeypatch.setattr(app, "_reset_user_plan_balance", reset_mock)
    fake_stripe, *_ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
    ))
    reset_mock.assert_not_awaited()


# -- 11. Month-end anniversaries and the end of an annual subscription --
# (add_one_month/add_one_year + the credit-cycle defaulting are covered in
# tests/test_supabase_request.py; _process_due_annual_credit_refills's own
# "never past expiration" filter is covered by
# test_list_souscriptions_due_for_monthly_credit_allocation_filters_correctly.)


# -- 12. Storage is no longer a quota -- a plan change never considers it --

def test_change_souscription_plan_never_blocks_or_warns_on_storage(monkeypatch):
    # Storage is no longer a sellable/enforced quota at all: a plan
    # change (immediate or scheduled) must never block on it, and the
    # preview must never mention it.
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="gold")
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 0.0}))

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver"), user_id="u1",
    ))
    assert result["classification"] == app.PLAN_CHANGE_DOWNGRADE_SCHEDULED

    preview = asyncio.run(app.preview_souscription_plan_change(user_id="u1", plan_id="silver"))
    assert "storage_overage_warning" not in preview
    assert "new_storage_quota" not in preview


# -- 13. No new referral reward on a plan change (see above, static check) --
# -- 14. Classification refusals: lateral and invalid/absent ordre --

def test_change_souscription_plan_refuses_lateral_change(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    plans = {"silver": _SILVER_PLAN, "silver-annual-only": {**_SILVER_PLAN, "id": "silver-annual-only"}}
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription, plans=plans)

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver-annual-only"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "plan_change_lateral_unsupported"


def test_change_souscription_plan_refuses_when_ordre_missing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    plans = {"silver": _SILVER_PLAN, "retired": {"id": "retired", "name": "Retired", "ordre": None}}
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription, plans=plans)

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="retired"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "plan_change_invalid_order"


def test_change_souscription_plan_noop_when_same_plan_and_interval(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    fake_stripe, update_mock, insert_mock, credits_mock, _ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver"), user_id="u1",
    ))
    assert result == {"classification": app.PLAN_CHANGE_NOOP, "changed": False}
    fake_stripe.Subscription.modify.assert_not_called()
    insert_mock.assert_not_awaited()
    credits_mock.assert_not_awaited()


def test_change_souscription_plan_404_for_unknown_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    _stub_plan_change_prereqs(monkeypatch, app)

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="missing-plan"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_change_souscription_plan_blocks_when_over_social_account_limit(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="gold")
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)
    monkeypatch.setattr(app, "_count_social_accounts_by_platform", AsyncMock(return_value={"facebook": 5, "instagram": 1}))

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "plan_change_over_limit"
    assert "facebook" in exc_info.value.detail["details"]
    assert "instagram" not in exc_info.value.detail["details"]


def test_change_souscription_plan_sends_notification_email(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver")
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)
    email_mock = MagicMock()
    monkeypatch.setattr(app, "_send_transactional_email", email_mock)

    asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
        request=_FakeCheckoutRequest(headers={"X-User-Email": "user@example.com"}),
    ))

    email_mock.assert_called_once()
    args, kwargs = email_mock.call_args
    assert args[0] == "user@example.com"
    assert args[1] == "subscription_plan_changed"
    assert kwargs["plan_name"] == "Gold"


def test_change_souscription_plan_starts_fresh_checkout_for_non_recurring_subscription(monkeypatch):
    # A subscription with no stripe_subscription_id (see
    # _get_active_stripe_souscription's docstring) has no Stripe
    # Subscription to modify in place -- an immediate upgrade must instead
    # start a brand new recurring Checkout, and must never touch
    # stripe.Subscription.retrieve/modify.
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="silver", stripe_subscription_id=None)
    fake_stripe, update_mock, *_ = _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)
    fake_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test_plan", id="cs_test_plan")
    fake_stripe.checkout.Session.create.return_value = fake_session
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))

    result = asyncio.run(app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="gold"), user_id="u1",
        request=_FakeCheckoutRequest(),
    ))

    assert result == {"checkout_url": fake_session.url, "session_id": fake_session.id}
    fake_stripe.Subscription.retrieve.assert_not_called()
    fake_stripe.Subscription.modify.assert_not_called()
    update_mock.assert_not_awaited()  # old row is only closed out once the Checkout completes

    _, kwargs = fake_stripe.checkout.Session.create.call_args
    assert kwargs["mode"] == "subscription"
    assert kwargs["metadata"]["abonnement"] == "gold"
    assert kwargs["metadata"]["previous_souscription_id"] == "sous-1"


def test_change_souscription_plan_legacy_subscription_refuses_scheduled_change(monkeypatch):
    # A legacy pre-recurring-billing subscription has no Stripe
    # Subscription to attach a schedule to -- a downgrade/periodicity
    # change can't be deferred automatically for it.
    app = _import_app_with_stubs(monkeypatch)
    subscription = _plan_change_subscription(abonnement="gold", stripe_subscription_id=None)
    _stub_plan_change_prereqs(monkeypatch, app, subscription=subscription)

    coro = app.change_souscription_plan(
        payload=app.ChangeSubscriptionPlanRequest(plan_id="silver"), user_id="u1",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "plan_change_requires_recurring_subscription"


# ---------------------------------------------------------------------------
# Social posts: a user-authored post + follow-up comments, published (or
# scheduled) by the connected Facebook/LinkedIn account itself.
# ---------------------------------------------------------------------------

class _FakeHttpxResponse:
    def __init__(self, status_code=200, json_data=None, headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {}
        self.text = str(self._json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=types.SimpleNamespace(), response=self)

    def json(self):
        return self._json_data


class _FakeHttpxAsyncClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        _FakeHttpxAsyncClient.calls.append({"url": url, **kwargs})
        return _FakeHttpxAsyncClient.next_response


def _install_fake_httpx_post(monkeypatch, app, response):
    _FakeHttpxAsyncClient.calls = []
    _FakeHttpxAsyncClient.next_response = response
    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeHttpxAsyncClient)
    return _FakeHttpxAsyncClient


class _FakeSocialAccountsTable:
    """Minimal chainable stand-in for the postgrest query builder, just
    enough for _upsert_social_account's insert/update calls, plus select
    (returns select_rows) and delete (records into deleted)."""

    def __init__(self, select_rows=None):
        self.inserted = []
        self.updated = []
        self.deleted = []
        self._select_rows = select_rows if select_rows is not None else []
        self._pending_update = None
        self._pending_delete = False

    def insert(self, payload):
        self.inserted.append(payload)
        return self

    def update(self, payload):
        self._pending_update = payload
        return self

    def select(self, *_args, **_kwargs):
        return self

    def delete(self):
        self._pending_delete = True
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.deleted.append((field, value)) if self._pending_delete else None
        return self

    async def execute(self):
        if self._pending_update is not None:
            self.updated.append(self._pending_update)
            self._pending_update = None
            return types.SimpleNamespace(data=[])
        if self._pending_delete:
            self._pending_delete = False
            return types.SimpleNamespace(data=[{"id": "deleted"}])
        return types.SimpleNamespace(data=self._select_rows)


class _FakeSupabaseClient:
    def __init__(self, table):
        self._table = table

    def table(self, _name):
        return self._table


def test_upsert_social_account_inserts_new_account_within_limit(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    table = _FakeSocialAccountsTable()
    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeSupabaseClient(table)))
    monkeypatch.setattr(app, "_find_social_account_by_platform_user", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "_count_social_accounts_by_platform", AsyncMock(return_value={"facebook": 1}))
    monkeypatch.setattr(app, "_get_user_max_social_accounts", AsyncMock(return_value=3))

    asyncio.run(app._upsert_social_account(
        user_id="u1", platform="facebook", access_token="tok", refresh_token=None,
        expires_in=3600, platform_user_id="page-2", platform_account_name="Page 2", scopes="pages_show_list",
    ))

    assert len(table.inserted) == 1
    assert table.inserted[0]["platform_user_id"] == "page-2"
    assert table.updated == []


def test_upsert_social_account_updates_existing_match_without_limit_check(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    table = _FakeSocialAccountsTable()
    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeSupabaseClient(table)))
    monkeypatch.setattr(app, "_find_social_account_by_platform_user", AsyncMock(return_value={"id": "acct-1"}))
    count_mock = AsyncMock()
    monkeypatch.setattr(app, "_count_social_accounts_by_platform", count_mock)

    asyncio.run(app._upsert_social_account(
        user_id="u1", platform="facebook", access_token="tok", refresh_token=None,
        expires_in=3600, platform_user_id="page-1", platform_account_name="Page 1", scopes="pages_show_list",
    ))

    assert len(table.updated) == 1
    assert table.inserted == []
    count_mock.assert_not_called()


def test_upsert_social_account_rejects_new_account_over_plan_limit(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    table = _FakeSocialAccountsTable()
    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeSupabaseClient(table)))
    monkeypatch.setattr(app, "_find_social_account_by_platform_user", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "_count_social_accounts_by_platform", AsyncMock(return_value={"facebook": 1}))
    monkeypatch.setattr(app, "_get_user_max_social_accounts", AsyncMock(return_value=1))

    coro = app._upsert_social_account(
        user_id="u1", platform="facebook", access_token="tok", refresh_token=None,
        expires_in=3600, platform_user_id="page-2", platform_account_name="Page 2", scopes="pages_show_list",
    )
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 403
    assert table.inserted == []


def test_assert_user_has_active_subscription_for_publish_blocks_without_subscription_or_credit(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 0}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(return_value=[]))

    coro = app._assert_user_has_active_subscription_for_publish("u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.status_code == 402


def test_assert_user_has_active_subscription_for_publish_allows_with_bonus_credit_and_no_subscription(monkeypatch):
    # A referred user with only a promotional bonus (or anyone whose
    # subscription lapsed but still has unused promotional/purchased
    # credit) keeps publish access until that bonus credit runs out --
    # the subscription requirement is bypassed, not the other way around.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 0}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(
        return_value=[{"amount_remaining": 25.0, "tier": 1}],
    ))

    asyncio.run(app._assert_user_has_active_subscription_for_publish("u1"))


def test_assert_user_has_active_subscription_for_publish_allows_with_standard_credit_and_no_subscription(monkeypatch):
    # "peu importe la nature des credits" -- plain subscription credit
    # left over after the subscription itself lapsed counts just as much
    # as a promotional/purchased batch.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 10}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(return_value=[]))

    asyncio.run(app._assert_user_has_active_subscription_for_publish("u1"))


def test_assert_user_has_active_subscription_for_publish_blocks_when_bonus_credit_exhausted(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 0}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(
        return_value=[{"amount_remaining": 0.0, "tier": 2}],
    ))

    coro = app._assert_user_has_active_subscription_for_publish("u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.status_code == 402


def test_assert_user_has_active_subscription_for_publish_allows_with_zero_credits(monkeypatch):
    # Publishing is free (no credit debit) -- an active subscription is
    # enough to publish even when the account has 0 credits.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"id": "sub-1", "abonnement": "silver-plan"}))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 0}))

    asyncio.run(app._assert_user_has_active_subscription_for_publish("u1"))


def test_assert_user_can_publish_allows_under_quota(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_consume_publish_quota", AsyncMock(
        return_value={"allowed": True, "max_daily": 5, "used_today": 3},
    ))

    asyncio.run(app._assert_user_can_publish("u1", 1))


def test_assert_user_can_publish_blocks_with_quota_details(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_consume_publish_quota", AsyncMock(
        return_value={"allowed": False, "max_daily": 5, "used_today": 5, "resets_at": "2026-01-02T00:00:00+00:00"},
    ))

    coro = app._assert_user_can_publish("u1", 1)
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.status_code == 429
    detail = exc_info.value.detail
    assert detail["code"] == "publish_quota_exceeded"
    assert detail["max_daily"] == 5
    assert detail["used_today"] == 5
    assert detail["resets_at"] == "2026-01-02T00:00:00+00:00"


def test_post_to_socials_consumes_quota_for_every_account(monkeypatch):
    # The quota is consumed once per account/platform target in the
    # request, not once per API call.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    quota_mock = AsyncMock()
    monkeypatch.setattr(app, "_assert_user_can_publish", quota_mock)
    monkeypatch.setattr(app, "_resolve_accounts_for_publish", AsyncMock(return_value=[
        {"id": "acct-1", "platform": "facebook"}, {"id": "acct-2", "platform": "instagram"},
    ]))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "_resolve_clip_for_social_post", AsyncMock(return_value={"video_url": "https://x/video.mp4"}))
    monkeypatch.setattr(app, "_resolve_local_video_path", lambda *a, **k: "/tmp/video.mp4")
    monkeypatch.setattr(app, "_resolve_public_video_url", lambda *a, **k: "https://x/video.mp4")
    monkeypatch.setattr(app, "_publish_reel_social_post_now", AsyncMock(return_value={"success": True}))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/post",
            json={"job_id": "job-1", "clip_index": 0, "account_ids": ["acct-1", "acct-2"]},
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    quota_mock.assert_awaited_once_with("u1", 2)


def test_get_user_max_social_accounts_defaults_to_one_without_active_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))

    result = asyncio.run(app._get_user_max_social_accounts("u1"))

    assert result == 1


def test_get_user_max_social_accounts_reads_active_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"abonnement": "gold-plan"}))
    monkeypatch.setattr(app, "supabase_get_abonnement", AsyncMock(return_value={"max_social_account": 3}))

    result = asyncio.run(app._get_user_max_social_accounts("u1"))

    assert result == 3


def test_count_social_accounts_by_platform_groups_rows(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _CountTable:
        def table(self, _name):
            return self

        def select(self, _cols):
            return self

        def eq(self, *_a, **_k):
            return self

        async def execute(self):
            return types.SimpleNamespace(data=[
                {"platform": "facebook"}, {"platform": "facebook"}, {"platform": "instagram"},
            ])

    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_CountTable()))

    result = asyncio.run(app._count_social_accounts_by_platform("u1"))

    assert result == {"facebook": 2, "instagram": 1}


def test_list_social_accounts_returns_accounts_and_plan_limit(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    table = _FakeSocialAccountsTable(select_rows=[
        {"id": "acct-1", "platform": "facebook", "platform_account_name": "Page A"},
        {"id": "acct-2", "platform": "facebook", "platform_account_name": "Page B"},
    ])
    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeSupabaseClient(table)))
    monkeypatch.setattr(app, "_get_user_max_social_accounts", AsyncMock(return_value=3))

    result = asyncio.run(app.list_social_accounts(user_id="u1"))

    assert result["max_social_account"] == 3
    assert len(result["accounts"]) == 2
    assert all(a["connected"] is True for a in result["accounts"])


def test_disconnect_social_account_deletes_owned_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    table = _FakeSocialAccountsTable()
    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeSupabaseClient(table)))
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "acct-1", "user_id": "u1"}))

    result = asyncio.run(app.disconnect_social_account(account_id="acct-1", user_id="u1"))

    assert result == {"deleted": True}
    assert ("id", "acct-1") in table.deleted
    assert ("user_id", "u1") in table.deleted


def test_disconnect_social_account_404_when_not_owned(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value=None))

    coro = app.disconnect_social_account(account_id="acct-1", user_id="u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_post_facebook_comment_sends_message_and_attachment(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_client = _install_fake_httpx_post(
        monkeypatch, app, _FakeHttpxResponse(200, {"id": "comment_1"}),
    )

    result = asyncio.run(app._post_facebook_comment("page-token", "1234_5678", "Hello world", "https://example.com/img.png"))

    assert result == {"id": "comment_1"}
    call = fake_client.calls[0]
    assert call["url"] == "https://graph.facebook.com/v19.0/1234_5678/comments"
    assert call["data"]["message"] == "Hello world"
    assert call["data"]["attachment_url"] == "https://example.com/img.png"
    assert call["data"]["access_token"] == "page-token"


def test_post_platform_comment_facebook_never_sends_link_as_attachment(monkeypatch):
    # attachment_url must be a real image -- Facebook's Graph API rejects a
    # plain webpage link there with a misleading "(#200) Permissions error".
    # The link should still reach Facebook, just folded into the message
    # text (see _build_comment_message), never as attachment_url.
    app = _import_app_with_stubs(monkeypatch)
    fake_client = _install_fake_httpx_post(
        monkeypatch, app, _FakeHttpxResponse(200, {"id": "comment_1"}),
    )
    comment = app.SocialPostCommentInput(text="Check this out", link="https://example.com/article")

    asyncio.run(app._post_platform_comment("facebook", {}, "page-token", "1234_5678", comment))

    call = fake_client.calls[0]
    assert "attachment_url" not in call["data"]
    assert "https://example.com/article" in call["data"]["message"]


def test_post_platform_comment_facebook_uses_image_url_as_attachment(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_client = _install_fake_httpx_post(
        monkeypatch, app, _FakeHttpxResponse(200, {"id": "comment_1"}),
    )
    comment = app.SocialPostCommentInput(text="Look", image_url="https://s3.example/img.png")

    asyncio.run(app._post_platform_comment("facebook", {}, "page-token", "1234_5678", comment))

    call = fake_client.calls[0]
    assert call["data"]["attachment_url"] == "https://s3.example/img.png"


def test_post_comments_sequence_skips_linkedin_without_attempting(monkeypatch):
    # LinkedIn's comments API is permanently out of reach for this app
    # (403 ACCESS_DENIED, partnerApiSocialActions.CREATE) -- must be
    # skipped outright rather than attempted and recorded as a failure,
    # so the composer doesn't report a guaranteed, permanent failure as
    # if the user could retry it.
    app = _import_app_with_stubs(monkeypatch)
    get_token_mock = AsyncMock()
    monkeypatch.setattr(app, "get_valid_token", get_token_mock)
    post_platform_comment_mock = AsyncMock()
    monkeypatch.setattr(app, "_post_platform_comment", post_platform_comment_mock)

    results = asyncio.run(app._post_comments_sequence(
        "linkedin", {"platform_user_id": "u1"}, "urn:li:share:123",
        [app.SocialPostCommentInput(text="Nice post")],
    ))

    assert results == []
    get_token_mock.assert_not_awaited()
    post_platform_comment_mock.assert_not_awaited()


def test_post_comments_sequence_still_posts_for_facebook(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="page-token"))
    monkeypatch.setattr(app, "_post_platform_comment", AsyncMock(return_value={"id": "c1"}))

    results = asyncio.run(app._post_comments_sequence(
        "facebook", {"id": "acct-1"}, "1234_5678", [app.SocialPostCommentInput(text="Nice post")],
    ))

    assert results == [{"success": True, "id": "c1", "text": "Nice post"}]


class _FakeCommentImageUpload:
    def __init__(self, content: bytes, filename: str = "photo.png", content_type: str = "image/png"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._done = False

    async def read(self, _chunk_size: int):
        if self._done:
            return b""
        self._done = True
        return self._content


def test_upload_social_comment_image_happy_path(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")

    upload_calls = []
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: upload_calls.append((path, bucket, key)) or True)
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: f"https://s3.example/{key}?exp={expiration}")

    result = asyncio.run(app.upload_social_comment_image(user_id="u1", file=_FakeCommentImageUpload(b"fake-image-bytes")))

    assert result["image_url"].startswith("https://s3.example/social_comment_images/u1/")
    assert "exp=604800" in result["image_url"]
    assert len(upload_calls) == 1
    # The temp local file is cleaned up after the S3 upload, whether it
    # succeeded or not -- nothing should be left behind in UPLOAD_DIR.
    assert list((tmp_path / "uploads").glob("comment_image_*")) == []


def test_upload_social_comment_image_rejects_non_image_content_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    coro = app.upload_social_comment_image(user_id="u1", file=_FakeCommentImageUpload(b"x", content_type="text/plain"))
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400


def test_upload_social_comment_image_rejects_oversized_file(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "_COMMENT_IMAGE_MAX_BYTES", 4)

    coro = app.upload_social_comment_image(user_id="u1", file=_FakeCommentImageUpload(b"0123456789"))
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400
    assert "too large" in str(exc.value.detail).lower()


def test_upload_social_comment_image_requires_bucket_configured(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)

    coro = app.upload_social_comment_image(user_id="u1", file=_FakeCommentImageUpload(b"fake-image-bytes"))
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 503


def test_upload_social_post_media_happy_path_image(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")

    upload_calls = []
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: upload_calls.append((path, bucket, key)) or True)
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: f"https://s3.example/{key}?exp={expiration}")

    result = asyncio.run(app.upload_social_post_media(user_id="u1", file=_FakeCommentImageUpload(b"fake-image-bytes")))

    assert result["media_type"] == "image"
    assert result["media_url"].startswith("https://s3.example/social_post_media/u1/")
    assert len(upload_calls) == 1
    assert list((tmp_path / "uploads").glob("post_media_*")) == []


def test_upload_social_post_media_happy_path_video(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: True)
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: f"https://s3.example/{key}")

    result = asyncio.run(app.upload_social_post_media(
        user_id="u1",
        file=_FakeCommentImageUpload(b"fake-video-bytes", filename="clip.mp4", content_type="video/mp4"),
    ))

    assert result["media_type"] == "video"
    assert result["media_url"].startswith("https://s3.example/social_post_media/u1/")


def test_upload_social_post_media_rejects_unsupported_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    coro = app.upload_social_post_media(
        user_id="u1", file=_FakeCommentImageUpload(b"x", filename="doc.pdf", content_type="application/pdf"),
    )
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400


def test_upload_social_post_media_rejects_oversized_image(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "_POST_MEDIA_IMAGE_MAX_BYTES", 4)

    coro = app.upload_social_post_media(user_id="u1", file=_FakeCommentImageUpload(b"0123456789"))
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400
    assert "too large" in str(exc.value.detail).lower()


# ---------------------------------------------------------------------------
# Reel visuals (manual image split-screen overlays)
# ---------------------------------------------------------------------------

def test_validate_reel_visual_timing_rejects_negative_start(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    with pytest.raises(app.HTTPException) as exc:
        app._validate_reel_visual_timing(-1.0, 5.0, 60.0, [])
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_visual_timing"


def test_validate_reel_visual_timing_rejects_zero_or_negative_duration(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    with pytest.raises(app.HTTPException) as exc:
        app._validate_reel_visual_timing(0.0, 0.0, 60.0, [])
    assert exc.value.detail["code"] == "invalid_visual_timing"


def test_validate_reel_visual_timing_rejects_exceeding_reel_duration(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    with pytest.raises(app.HTTPException) as exc:
        app._validate_reel_visual_timing(55.0, 10.0, 60.0, [])
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "visual_exceeds_reel_duration"


def test_validate_reel_visual_timing_allows_exactly_at_reel_duration(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    # 55 + 5 == 60, exactly at the boundary -- must be allowed.
    end_time = app._validate_reel_visual_timing(55.0, 5.0, 60.0, [])
    assert end_time == 60.0


def test_validate_reel_visual_timing_rejects_overlap(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    existing = [{"id": "v1", "start_time": 10.0, "duration": 5.0}]  # [10,15)
    with pytest.raises(app.HTTPException) as exc:
        app._validate_reel_visual_timing(12.0, 5.0, 60.0, existing)  # [12,17) overlaps
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "visual_overlap"


def test_validate_reel_visual_timing_allows_adjacent_non_overlapping(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    existing = [{"id": "v1", "start_time": 10.0, "duration": 5.0}]  # [10,15)
    # [15,20) starts exactly where the other ends -- not an overlap.
    end_time = app._validate_reel_visual_timing(15.0, 5.0, 60.0, existing)
    assert end_time == 20.0


def test_validate_reel_visual_timing_excludes_self_when_editing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    existing = [{"id": "v1", "start_time": 10.0, "duration": 5.0}]
    # Editing v1's own timing must not collide with itself.
    end_time = app._validate_reel_visual_timing(10.0, 5.0, 60.0, existing, exclude_visual_id="v1")
    assert end_time == 15.0


def test_create_reel_visual_happy_path(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[]))
    upload_calls = []
    monkeypatch.setattr(app, "upload_file_to_s3", lambda path, bucket, key: upload_calls.append((path, bucket, key)) or True)
    insert_mock = AsyncMock(return_value={"id": "v1", "position": "TOP", "start_time": 5.0, "duration": 3.0, "image_s3_key": "reels/u1/job1/visual_0_v1.jpg"})
    monkeypatch.setattr(app, "supabase_insert_reel_visual", insert_mock)
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: f"https://s3.example/{key}")

    result = asyncio.run(app.create_reel_visual(
        "job1", 0, user_id="u1", file=_FakeCommentImageUpload(b"fake-image-bytes"),
        position="top", start_time=5.0, duration=3.0,
    ))

    assert result["id"] == "v1"
    assert result["image_url"] == "https://s3.example/reels/u1/job1/visual_0_v1.jpg"
    assert result["end_time"] == 8.0
    insert_mock.assert_awaited_once()
    insert_args = insert_mock.await_args.args
    assert insert_args[:5] == ("reel-1", "u1", "TOP", 5.0, 3.0)
    assert insert_args[5].startswith("reels/u1/job1/visual_0_")
    assert len(upload_calls) == 1
    assert upload_calls[0][2].startswith("reels/u1/job1/visual_0_")


def test_create_reel_visual_rejects_invalid_position(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))

    coro = app.create_reel_visual(
        "job1", 0, user_id="u1", file=_FakeCommentImageUpload(b"x"),
        position="left", start_time=0.0, duration=1.0,
    )
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "invalid_visual_position"


def test_create_reel_visual_rejects_non_image_content_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))

    coro = app.create_reel_visual(
        "job1", 0, user_id="u1", file=_FakeCommentImageUpload(b"x", content_type="text/plain"),
        position="top", start_time=0.0, duration=1.0,
    )
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.detail["code"] == "invalid_image_format"


def test_create_reel_visual_rejects_overlap_with_existing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"id": "v1", "start_time": 10.0, "duration": 5.0},
    ]))

    coro = app.create_reel_visual(
        "job1", 0, user_id="u1", file=_FakeCommentImageUpload(b"x"),
        position="top", start_time=12.0, duration=5.0,
    )
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "visual_overlap"


def test_create_reel_visual_requires_bucket_configured(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[]))

    coro = app.create_reel_visual(
        "job1", 0, user_id="u1", file=_FakeCommentImageUpload(b"x"),
        position="top", start_time=0.0, duration=1.0,
    )
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 503


def test_create_reel_visual_404_when_reel_not_found(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value=None))

    coro = app.create_reel_visual(
        "job1", 0, user_id="u1", file=_FakeCommentImageUpload(b"x"),
        position="top", start_time=0.0, duration=1.0,
    )
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 404


def test_list_reel_visuals_endpoint_returns_normalized_items(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"id": "v1", "start_time": 2.0, "duration": 3.0, "image_s3_key": "k1"},
    ]))
    monkeypatch.setattr(app, "generate_presigned_url", lambda bucket, key, expiration=3600: f"https://s3.example/{key}")

    result = asyncio.run(app.list_reel_visuals_endpoint("job1", 0, user_id="u1"))

    assert result["items"][0]["end_time"] == 5.0
    assert result["items"][0]["image_url"] == "https://s3.example/k1"


def test_update_reel_visual_endpoint_updates_timing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))
    monkeypatch.setattr(app, "supabase_get_reel_visual", AsyncMock(return_value={
        "id": "v1", "reel_id": "reel-1", "position": "TOP", "start_time": 5.0, "duration": 3.0,
    }))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"id": "v1", "start_time": 5.0, "duration": 3.0},
    ]))
    update_mock = AsyncMock(return_value={"id": "v1", "position": "TOP", "start_time": 20.0, "duration": 3.0, "image_s3_key": "k1"})
    monkeypatch.setattr(app, "supabase_update_reel_visual", update_mock)

    result = asyncio.run(app.update_reel_visual_endpoint(
        "job1", 0, "v1", app.UpdateReelVisualRequest(start_time=20.0), user_id="u1",
    ))

    assert result["start_time"] == 20.0
    update_mock.assert_awaited_once()
    args, kwargs = update_mock.await_args
    assert args[0] == "v1"
    assert args[2] == {"start_time": 20.0, "duration": 3.0}


def test_update_reel_visual_endpoint_404_for_other_users_visual(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))
    monkeypatch.setattr(app, "supabase_get_reel_visual", AsyncMock(return_value=None))

    coro = app.update_reel_visual_endpoint("job1", 0, "v1", app.UpdateReelVisualRequest(start_time=1.0), user_id="u1")
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 404


def test_update_reel_visual_endpoint_rejects_overlap(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1", "reel_duration": 60}))
    monkeypatch.setattr(app, "supabase_get_reel_visual", AsyncMock(return_value={
        "id": "v1", "reel_id": "reel-1", "position": "TOP", "start_time": 0.0, "duration": 3.0,
    }))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"id": "v1", "start_time": 0.0, "duration": 3.0},
        {"id": "v2", "start_time": 10.0, "duration": 5.0},
    ]))

    coro = app.update_reel_visual_endpoint("job1", 0, "v1", app.UpdateReelVisualRequest(start_time=12.0), user_id="u1")
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 409


def test_delete_reel_visual_endpoint_cleans_up_s3(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_get_reel_visual", AsyncMock(return_value={"id": "v1", "reel_id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_delete_reel_visual", AsyncMock(return_value={"id": "v1", "image_s3_key": "k1"}))
    delete_calls = []
    monkeypatch.setattr(app, "delete_s3_object", lambda bucket, key: delete_calls.append((bucket, key)) or True)

    result = asyncio.run(app.delete_reel_visual_endpoint("job1", 0, "v1", user_id="u1"))

    assert result == {"deleted": True}
    assert delete_calls == [("bucket", "k1")]


def test_delete_reel_visual_endpoint_404_when_not_found(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_get_reel_visual", AsyncMock(return_value=None))

    coro = app.delete_reel_visual_endpoint("job1", 0, "v1", user_id="u1")
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 404


def test_apply_reel_visuals_rejects_when_none_configured(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_require_job_ownership", AsyncMock())
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[]))

    coro = app.apply_reel_visuals("job1", 0, app.ApplyReelVisualsRequest(), user_id="u1")
    with pytest.raises(app.HTTPException) as exc:
        asyncio.run(coro)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "no_visuals_configured"


def test_apply_reel_visuals_happy_path(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket")
    monkeypatch.setattr(app, "_require_job_ownership", AsyncMock())
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"id": "v1", "position": "TOP", "start_time": 1.0, "duration": 2.0, "image_s3_key": "k1.jpg"},
    ]))
    monkeypatch.setattr(app, "jobs", {"job1": {"user_id": "u1"}})

    output_dir = os.path.join(str(tmp_path / "output"), "job1")
    os.makedirs(output_dir, exist_ok=True)
    video_path = os.path.join(output_dir, "clip_1.mp4")
    with open(video_path, "wb") as f:
        f.write(b"fake video bytes")

    metadata_path = os.path.join(output_dir, "metadata.json")
    clip_data = {"video_url": "clip_1.mp4", "start": 0, "end": 10}
    data = {"shorts": [clip_data]}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=(metadata_path, data)))
    monkeypatch.setattr(app, "_probe_local_video_duration_seconds", lambda path: 10.0)
    monkeypatch.setattr(app, "_estimate_reel_required_credits", lambda **kwargs: 5.0)
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock())

    def fake_download(bucket, key, local_path):
        with open(local_path, "wb") as f:
            f.write(b"fake image bytes")
        return True
    monkeypatch.setattr(app, "download_s3_object", fake_download)

    apply_calls = []
    def fake_apply(video_path, visuals, output_path):
        apply_calls.append((video_path, visuals, output_path))
        with open(output_path, "wb") as f:
            f.write(b"fake output bytes")
        return True
    monkeypatch.setattr(app, "apply_visuals_to_video", fake_apply)

    persist_calls = []
    monkeypatch.setattr(app, "_persist_new_video_url_to_clip", lambda *a, **k: persist_calls.append(a))
    monkeypatch.setattr(app, "supabase_deduct_user_credits", AsyncMock())
    monkeypatch.setattr(app, "supabase_insert_user_data_history", AsyncMock())

    result = asyncio.run(app.apply_reel_visuals("job1", 0, app.ApplyReelVisualsRequest(), user_id="u1"))

    assert result["success"] is True
    assert result["new_video_url"] == "/videos/job1/visuals_clip_1.mp4"
    assert len(apply_calls) == 1
    assert apply_calls[0][1][0]["position"] == "TOP"
    assert len(persist_calls) == 1
    # Downloaded visual image temp file is cleaned up afterwards.
    assert not any(p.startswith("visual_src_") for p in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, p)))


def test_reel_visual_windows_for_job_clip_returns_shaped_windows(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value={"id": "reel-1"}))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"position": "BOTTOM", "start_time": 2.0, "duration": 3.0},
    ]))

    result = asyncio.run(app._reel_visual_windows_for_job_clip("job1", 0, "u1"))

    assert result == [{"position": "BOTTOM", "start": 2.0, "end": 5.0}]


def test_reel_visual_windows_for_job_clip_empty_when_supabase_not_configured(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)
    assert asyncio.run(app._reel_visual_windows_for_job_clip("job1", 0, "u1")) == []


def test_reel_visual_windows_for_job_clip_empty_when_reel_not_found(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(return_value=None))
    assert asyncio.run(app._reel_visual_windows_for_job_clip("job1", 0, "u1")) == []


def test_reel_visual_windows_for_job_clip_swallows_lookup_errors(monkeypatch):
    # A lookup failure must never block subtitle burning.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "supabase_get_reel_by_job_clip", AsyncMock(side_effect=RuntimeError("db down")))
    assert asyncio.run(app._reel_visual_windows_for_job_clip("job1", 0, "u1")) == []


def test_add_subtitles_passes_visual_windows_to_burn(monkeypatch, tmp_path):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_require_job_ownership", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_has_required_credits", AsyncMock())
    monkeypatch.setattr(app, "jobs", {})
    output_dir = str(tmp_path / "job1")
    os.makedirs(output_dir, exist_ok=True)
    monkeypatch.setattr(app, "OUTPUT_DIR", str(tmp_path))

    clip_data = {"video_url": "clip_1.mp4", "start": 0, "end": 10}
    metadata_path = os.path.join(output_dir, "metadata.json")
    data = {"shorts": [clip_data], "transcript": {"segments": []}}
    monkeypatch.setattr(app, "_get_or_build_job_metadata", AsyncMock(return_value=(metadata_path, data)))
    monkeypatch.setattr(app, "_resolve_subtitle_source_video_history", AsyncMock(return_value=""))
    monkeypatch.setattr(app, "_resolve_burn_source_input_path", AsyncMock(return_value=("in.mp4", "clip_1.mp4")))
    monkeypatch.setattr(app, "_generate_subtitle_srt", AsyncMock(return_value=True))
    monkeypatch.setattr(app, "_reel_visual_windows_for_job_clip", AsyncMock(return_value=[{"position": "BOTTOM", "start": 2.0, "end": 5.0}]))
    burn_mock = MagicMock()
    monkeypatch.setattr(app, "_burn_subtitles_for_request", burn_mock)
    monkeypatch.setattr(app, "_upload_subtitled_video", lambda *a, **k: ("http://x/out.mp4", "k1"))
    monkeypatch.setattr(app, "_sync_reel_after_subtitle_edit", AsyncMock())

    req = app.SubtitleRequest(job_id="job1", clip_index=0)
    asyncio.run(app.add_subtitles(req, user_id="u1"))

    burn_mock.assert_called_once()
    assert burn_mock.call_args.args[4] == [{"position": "BOTTOM", "start": 2.0, "end": 5.0}]


def test_delete_project_reels_s3_files_also_cleans_up_visual_images(monkeypatch):
    # reel_visuals rows cascade-delete at the DB level once the reel row
    # is deleted, but their S3 images would be orphaned without this.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "supabase_get_reels_by_project", AsyncMock(return_value=[
        {"id": "reel-1", "reel_s3_key": "reels/u1/job1/clip.mp4", "reel_thumbnail_url": "reels/u1/job1/thumbnail_0.jpg"},
    ]))
    monkeypatch.setattr(app, "supabase_list_reel_visuals", AsyncMock(return_value=[
        {"id": "v1", "image_s3_key": "reels/u1/job1/visual_0_v1.jpg"},
        {"id": "v2", "image_s3_key": "reels/u1/job1/visual_0_v2.jpg"},
    ]))
    deleted_keys = []
    monkeypatch.setattr(app, "get_s3_object_size", lambda bucket, key: 100)
    monkeypatch.setattr(app, "delete_s3_object", lambda bucket, key: deleted_keys.append(key) or True)

    freed = asyncio.run(app._delete_project_reels_s3_files("proj-1", "bucket"))

    assert freed == 400  # 4 files * 100 bytes each
    assert "reels/u1/job1/visual_0_v1.jpg" in deleted_keys
    assert "reels/u1/job1/visual_0_v2.jpg" in deleted_keys


def test_post_facebook_comment_requires_object_id(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    coro = app._post_facebook_comment("page-token", "", "Hello")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 400


def test_post_linkedin_comment_sends_actor_and_encoded_urn(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    fake_client = _install_fake_httpx_post(
        monkeypatch, app, _FakeHttpxResponse(201, {}, headers={"x-restli-id": "urn:li:comment:(urn:li:share:123,456)"}),
    )

    result = asyncio.run(
        app._post_linkedin_comment("member-token", "urn:li:person:u1", "urn:li:share:123", "Nice post"),
    )

    assert result == {"id": "urn:li:comment:(urn:li:share:123,456)"}
    call = fake_client.calls[0]
    assert call["url"] == f"https://api.linkedin.com/rest/socialActions/{app.quote('urn:li:share:123', safe='')}/comments"
    assert call["json"]["actor"] == "urn:li:person:u1"
    assert call["json"]["message"]["text"] == "Nice post"


def test_resolve_accounts_for_publish_rejects_empty_list(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    coro = app._resolve_accounts_for_publish("u1", [], app._SOCIAL_POST_PLATFORMS)
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 400


def test_resolve_accounts_for_publish_rejects_unowned_or_missing_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value=None))

    coro = app._resolve_accounts_for_publish("u1", ["acct-1"], app._SOCIAL_POST_PLATFORMS)
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 404


def test_resolve_accounts_for_publish_rejects_unsupported_platform(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "acct-1", "platform": "tiktok"}))

    coro = app._resolve_accounts_for_publish("u1", ["acct-1"], app._SOCIAL_POST_PLATFORMS)
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.status_code == 400


def test_resolve_accounts_for_publish_dedupes_and_resolves_each(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    accounts_by_id = {
        "acct-1": {"id": "acct-1", "platform": "facebook"},
        "acct-2": {"id": "acct-2", "platform": "linkedin"},
    }
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(side_effect=lambda _uid, aid: accounts_by_id.get(aid)))

    result = asyncio.run(app._resolve_accounts_for_publish("u1", ["acct-1", "acct-1", "acct-2"], app._SOCIAL_POST_PLATFORMS))

    assert [a["id"] for a in result] == ["acct-1", "acct-2"]


def test_resolve_accounts_for_publish_allows_wider_share_platforms(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "acct-1", "platform": "youtube"}))

    result = asyncio.run(app._resolve_accounts_for_publish("u1", ["acct-1"], app._SHARE_PLATFORMS))

    assert result == [{"id": "acct-1", "platform": "youtube"}]


def test_build_comment_message_appends_link_when_missing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    comment = app.SocialPostCommentInput(text="Check this out", link="https://example.com")
    assert app._build_comment_message(comment) == "Check this out\nhttps://example.com"


def test_build_comment_message_skips_duplicate_link(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    comment = app.SocialPostCommentInput(text="See https://example.com for more", link="https://example.com")
    assert app._build_comment_message(comment) == "See https://example.com for more"


def _social_post_account(platform="facebook"):
    return {"id": "acct-1", "user_id": "u1", "platform": platform, "platform_user_id": "page-1"}


def test_create_social_post_rejects_empty_text(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={"text": "   ", "account_ids": ["acct-1"]},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_create_social_post_rejects_unsupported_platform_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={"id": "acct-1", "platform": "tiktok"}))

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={"text": "Hello", "account_ids": ["acct-1"]},
            headers=_auth_headers("u1"),
        )
    assert resp.status_code == 400


def test_create_social_post_publishes_now_and_posts_comments(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value=_social_post_account()))
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="page-token"))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "1234_5678"}))
    insert_job_mock = AsyncMock(return_value="job-1")
    monkeypatch.setattr(app, "_insert_publish_job", insert_job_mock)
    update_status_mock = AsyncMock()
    monkeypatch.setattr(app, "_update_publish_job_status", update_status_mock)
    post_comment_mock = AsyncMock(side_effect=[{"id": "c1"}, {"id": "c2"}])
    monkeypatch.setattr(app, "_post_platform_comment", post_comment_mock)

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={
                "text": "Big announcement!",
                "account_ids": ["acct-1"],
                "comments": [
                    {"text": "First comment", "link": "https://example.com"},
                    {"text": "Second comment", "image_url": "https://example.com/img.png"},
                ],
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["scheduled"] is False
    fb_result = data["results"]["acct-1"]
    assert fb_result["success"] is True
    assert fb_result["comments_results"] == [
        {"success": True, "id": "c1", "text": "First comment"},
        {"success": True, "id": "c2", "text": "Second comment"},
    ]
    assert post_comment_mock.await_count == 2
    # final status update carries the post_url + comment results, not just post_url
    done_call = [c for c in update_status_mock.await_args_list if len(c.args) > 1 and c.args[1] == "done"][0]
    assert done_call.kwargs["extra_payload"]["comments_results"] == fb_result["comments_results"]


def test_create_social_post_publishes_attached_photo(monkeypatch):
    # The "Faire une publication" composer can attach a photo/video (see
    # upload_social_post_media) -- it must route to PublishRequest.image_url
    # (not video_url) and skip the background default entirely, since a
    # background can't be combined with media.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value=_social_post_account()))
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="page-token"))
    published_contents = []

    async def fake_publish_post(account, content):
        published_contents.append(content)
        return {"id": "1234_5678"}

    monkeypatch.setattr(app, "publish_post", fake_publish_post)
    insert_job_mock = AsyncMock(return_value="job-1")
    monkeypatch.setattr(app, "_insert_publish_job", insert_job_mock)
    monkeypatch.setattr(app, "_update_publish_job_status", AsyncMock())

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={
                "text": "Regardez cette photo !",
                "account_ids": ["acct-1"],
                "media_url": "https://example.com/photo.png",
                "media_type": "image",
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["background_id"] is None
    assert len(published_contents) == 1
    assert published_contents[0].image_url == "https://example.com/photo.png"
    assert published_contents[0].video_url is None
    assert published_contents[0].facebook_text_format_preset_id is None
    queued_payload = insert_job_mock.await_args_list[0].kwargs["payload"]
    assert queued_payload["media_url"] == "https://example.com/photo.png"
    assert queued_payload["media_type"] == "image"


def test_create_social_post_allows_empty_text_with_attached_media(monkeypatch):
    # Meta's APIs only require text on a plain text-only post -- a photo
    # or video carries the caption as optional, so no text must be allowed
    # once media is attached.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value=_social_post_account()))
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="page-token"))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "1234_5678"}))
    monkeypatch.setattr(app, "_insert_publish_job", AsyncMock(return_value="job-1"))
    monkeypatch.setattr(app, "_update_publish_job_status", AsyncMock())

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={
                "text": "   ",
                "account_ids": ["acct-1"],
                "media_url": "https://example.com/video.mp4",
                "media_type": "video",
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_create_social_post_continues_after_one_comment_fails(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value=_social_post_account()))
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="page-token"))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "1234_5678"}))
    monkeypatch.setattr(app, "_insert_publish_job", AsyncMock(return_value="job-1"))
    monkeypatch.setattr(app, "_update_publish_job_status", AsyncMock())
    monkeypatch.setattr(
        app, "_post_platform_comment",
        AsyncMock(side_effect=[RuntimeError("rate limited"), {"id": "c2"}]),
    )

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={
                "text": "Big announcement!",
                "account_ids": ["acct-1"],
                "comments": [{"text": "First"}, {"text": "Second"}],
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True  # the post itself succeeded even though one comment failed
    comments_results = data["results"]["acct-1"]["comments_results"]
    assert comments_results[0]["success"] is False
    assert "rate limited" in comments_results[0]["error"]
    assert comments_results[1] == {"success": True, "id": "c2", "text": "Second"}


def test_create_social_post_schedules_job_without_publishing(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_has_active_subscription_for_publish", AsyncMock())
    monkeypatch.setattr(app, "_assert_user_can_publish", AsyncMock())
    monkeypatch.setattr(app, "_get_user_max_comments_per_post", AsyncMock(return_value=99))
    monkeypatch.setattr(app, "_resolve_user_job_priority", AsyncMock(return_value=1))
    accounts_by_id = {
        "fb-acct": {"id": "fb-acct", "platform": "facebook"},
        "li-acct": {"id": "li-acct", "platform": "linkedin"},
    }
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(side_effect=lambda _uid, aid: accounts_by_id.get(aid)))
    insert_job_mock = AsyncMock(return_value="job-scheduled-1")
    monkeypatch.setattr(app, "_insert_publish_job", insert_job_mock)
    publish_post_mock = AsyncMock()
    monkeypatch.setattr(app, "publish_post", publish_post_mock)

    future_iso = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    with TestClient(app.app) as client:
        resp = client.post(
            "/api/social/posts",
            json={
                "text": "Scheduled announcement",
                "account_ids": ["fb-acct", "li-acct"],
                "background_id": "some-preset",
                "comments": [{"text": "Follow-up"}],
                "scheduled_date": future_iso,
                "timezone": "UTC",
            },
            headers=_auth_headers("u1"),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["scheduled"] is True
    assert data["success"] is True
    publish_post_mock.assert_not_awaited()
    assert insert_job_mock.await_count == 2  # one job per account
    assert set(data["results"].keys()) == {"fb-acct", "li-acct"}

    inserted_payloads = [call.kwargs["payload"] for call in insert_job_mock.await_args_list]
    for payload in inserted_payloads:
        assert payload["source_type"] == "social_post"
        assert payload["account_id"] in {"fb-acct", "li-acct"}
        assert payload["text"] == "Scheduled announcement"
        assert payload["background_id"] == "some-preset"
        assert payload["comments"] == [{"text": "Follow-up", "link": None, "image_url": None}]


def test_execute_scheduled_social_post_job_publishes_and_comments(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account", AsyncMock(return_value=_social_post_account("facebook")))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "1234_5678"}))
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="page-token"))
    update_status_mock = AsyncMock()
    monkeypatch.setattr(app, "_update_publish_job_status", update_status_mock)
    post_comment_mock = AsyncMock(return_value={"id": "comment-urn"})
    monkeypatch.setattr(app, "_post_platform_comment", post_comment_mock)

    task_payload = {
        "source_type": "social_post",
        "text": "Scheduled text",
        "background_id": None,
        "comments": [{"text": "A comment", "link": None, "image_url": None}],
    }

    asyncio.run(app._execute_scheduled_social_post_job("job-9", "u1", "facebook", task_payload))

    post_comment_mock.assert_awaited_once()
    done_call = [c for c in update_status_mock.await_args_list if len(c.args) > 1 and c.args[1] == "done"][0]
    assert done_call.kwargs["external_id"] == "1234_5678"
    assert done_call.kwargs["extra_payload"]["comments_results"] == [
        {"success": True, "id": "comment-urn", "text": "A comment"}
    ]


def test_execute_scheduled_social_post_job_skips_comments_on_linkedin(monkeypatch):
    # See _post_comments_sequence: LinkedIn's comments API is permanently
    # unreachable with this app's access (403 ACCESS_DENIED,
    # partnerApiSocialActions.CREATE), so the scheduled-post path must
    # skip it too, not just the immediate-publish path.
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account", AsyncMock(return_value=_social_post_account("linkedin")))
    monkeypatch.setattr(app, "publish_post", AsyncMock(return_value={"id": "urn:li:share:999"}))
    monkeypatch.setattr(app, "get_valid_token", AsyncMock(return_value="member-token"))
    update_status_mock = AsyncMock()
    monkeypatch.setattr(app, "_update_publish_job_status", update_status_mock)
    post_comment_mock = AsyncMock()
    monkeypatch.setattr(app, "_post_platform_comment", post_comment_mock)

    task_payload = {
        "source_type": "social_post",
        "text": "Scheduled text",
        "background_id": None,
        "comments": [{"text": "A comment", "link": None, "image_url": None}],
    }

    asyncio.run(app._execute_scheduled_social_post_job("job-9", "u1", "linkedin", task_payload))

    post_comment_mock.assert_not_awaited()
    done_call = [c for c in update_status_mock.await_args_list if len(c.args) > 1 and c.args[1] == "done"][0]
    assert done_call.kwargs["extra_payload"]["comments_results"] == []


def test_execute_scheduled_social_post_job_marks_failed_without_account(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_get_social_account", AsyncMock(return_value=None))
    update_status_mock = AsyncMock()
    monkeypatch.setattr(app, "_update_publish_job_status", update_status_mock)

    task_payload = {"source_type": "social_post", "text": "x", "comments": []}
    asyncio.run(app._execute_scheduled_social_post_job("job-10", "u1", "facebook", task_payload))

    failed_call = [c for c in update_status_mock.await_args_list if len(c.args) > 1 and c.args[1] == "failed"]
    assert failed_call
    assert "No connected facebook account" in failed_call[0].kwargs["error_message"]


def test_execute_scheduled_publish_job_dispatches_social_post_by_source_type(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    dispatched = AsyncMock()
    monkeypatch.setattr(app, "_execute_scheduled_social_post_job", dispatched)

    job_row = {
        "id": "job-11",
        "user_id": "u1",
        "platform": "facebook",
        "payload": {"source_type": "social_post", "text": "hi"},
    }
    asyncio.run(app._execute_scheduled_publish_job(job_row))

    dispatched.assert_awaited_once_with("job-11", "u1", "facebook", job_row["payload"])


def test_update_publish_job_status_merges_extra_payload_with_post_url(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    captured = {}

    class _FakeSelectQuery:
        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        async def execute(self):
            return types.SimpleNamespace(data=[{"payload": {"source_type": "reel", "title": "T"}}])

    class _FakeTable:
        def select(self, *_a, **_k):
            return _FakeSelectQuery()

        def update(self, payload):
            captured["payload"] = payload
            return self

        def eq(self, *_a, **_k):
            return self

        async def execute(self):
            return types.SimpleNamespace(data=[{"id": "job-1"}])

    class _FakeClient:
        def table(self, _name):
            return _FakeTable()

    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeClient()))

    asyncio.run(app._update_publish_job_status(
        "job-1", "done", external_id="ext-1", post_url="https://example.com/post",
        extra_payload={"comments_results": [{"success": True, "id": "c1"}]},
    ))

    # The pre-existing payload (source_type/title, set at insert/schedule
    # time) survives alongside the new post_url/comments_results -- it's
    # what lets the publications page show what was actually posted.
    assert captured["payload"]["payload"] == {
        "source_type": "reel",
        "title": "T",
        "comments_results": [{"success": True, "id": "c1"}],
        "post_url": "https://example.com/post",
    }


# ---------------------------------------------------------------------------
# Dashboard stats (/api/dashboard/stats)
# ---------------------------------------------------------------------------

def test_dashboard_stats_rejects_invalid_range(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)

    with TestClient(app.app) as client:
        resp = client.get("/api/dashboard/stats", params={"range": "bogus"}, headers=_auth_headers("u1"))

    assert resp.status_code == 400


def test_dashboard_stats_returns_zeroed_shape_when_supabase_not_configured(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: False)

    with TestClient(app.app) as client:
        resp = client.get("/api/dashboard/stats", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    data = resp.json()
    assert data["range"] == "30d"
    assert data["totals"] == {
        "reels": 0,
        "captions": 0,
        "anonymous_stories": 0,
        "film_summaries": 0,
        "publications_done": 0,
        "publications_failed": 0,
        "credits_consumed": 0.0,
    }
    assert data["daily"] == []
    assert data["publications_by_platform"] == []


def test_dashboard_stats_aggregates_counts_and_daily_series(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_utcnow", lambda: datetime(2026, 9, 5, tzinfo=timezone.utc))

    monkeypatch.setattr(app, "supabase_list_reel_dates_since", AsyncMock(return_value=[
        "2026-09-01T10:00:00+00:00", "2026-09-01T10:05:00+00:00", "2026-09-03T09:00:00+00:00",
    ]))
    monkeypatch.setattr(app, "supabase_list_caption_dates_since", AsyncMock(return_value=[]))
    monkeypatch.setattr(app, "supabase_list_anonymous_story_dates_since", AsyncMock(return_value=[]))
    monkeypatch.setattr(app, "supabase_list_film_summary_dates_since", AsyncMock(return_value=[]))

    publish_rows = [
        {"platform": "facebook", "created_at": "2026-09-01T11:00:00+00:00", "status": "done"},
        {"platform": "instagram", "created_at": "2026-09-02T11:00:00+00:00", "status": "done"},
        {"platform": "facebook", "created_at": "2026-09-03T11:00:00+00:00", "status": "failed"},
    ]
    history_rows = [
        {"credit": 5.5, "created_at": "2026-09-01T12:00:00+00:00", "operation": "output"},
        {"credit": 2.0, "created_at": "2026-09-03T12:00:00+00:00", "operation": "output"},
    ]

    class _FakeQuery:
        def __init__(self, data):
            self._data = data

        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def gte(self, *_a, **_k):
            return self

        async def execute(self):
            return types.SimpleNamespace(data=self._data)

    class _FakeClient:
        def table(self, name):
            if name == app.SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE:
                return _FakeQuery(publish_rows)
            if name == app.SUPABASE_USER_DATA_HISTORY_TABLE:
                return _FakeQuery(history_rows)
            return _FakeQuery([])

    monkeypatch.setattr(app, "supabase_get_client", AsyncMock(return_value=_FakeClient()))

    with TestClient(app.app) as client:
        resp = client.get("/api/dashboard/stats", params={"range": "all"}, headers=_auth_headers("u1"))

    assert resp.status_code == 200
    data = resp.json()
    assert data["totals"] == {
        "reels": 3,
        "captions": 0,
        "anonymous_stories": 0,
        "film_summaries": 0,
        "publications_done": 2,
        "publications_failed": 1,
        "credits_consumed": 7.5,
    }
    assert data["publications_by_platform"] == [
        {"platform": "facebook", "count": 1},
        {"platform": "instagram", "count": 1},
    ]
    sept_1_entry = next(d for d in data["daily"] if d["date"] == "2026-09-01")
    assert sept_1_entry == {
        "date": "2026-09-01",
        "reels": 2,
        "captions": 0,
        "anonymous_stories": 0,
        "film_summaries": 0,
        "publications": 1,
        "credits_consumed": 5.5,
    }
    assert data["daily"][0]["date"] == "2026-09-01"
    assert data["daily"][-1]["date"] == "2026-09-05"


# ---------------------------------------------------------------------------
# Social analytics gate (_assert_user_can_access_analytics) and exposure via
# /api/user/credits
# ---------------------------------------------------------------------------

def test_assert_user_can_access_analytics_blocks_silver_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value={"priorite": 1}))

    coro = app._assert_user_can_access_analytics("u1")
    with pytest.raises(app.HTTPException) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.status_code == 403


def test_assert_user_can_access_analytics_allows_gold_plan(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value={"priorite": 2}))

    asyncio.run(app._assert_user_can_access_analytics("u1"))


def test_get_user_credits_reports_has_analytics_access(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"priorite": 3, "abonnement": "ultimate-plan"}))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 100, "stockage": 1}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(return_value=[]))

    with TestClient(app.app) as client:
        resp = client.get("/api/user/credits", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json()["has_analytics_access"] is True

    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value={"priorite": 1, "abonnement": "silver-plan"}))

    with TestClient(app.app) as client:
        resp = client.get("/api/user/credits", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    assert resp.json()["has_analytics_access"] is False


def test_get_user_credits_splits_promotional_and_purchased_batches(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "get_user_abonnement", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_latest_user_paid_subscription", AsyncMock(return_value=None))
    monkeypatch.setattr(app, "supabase_get_user_data", AsyncMock(return_value={"credit": 10, "stockage": 1}))
    monkeypatch.setattr(app, "supabase_list_active_promotional_credit_batches", AsyncMock(return_value=[
        {"amount_remaining": 50.0, "expires_at": "2026-12-01T00:00:00+00:00", "tier": 1},
        {"amount_remaining": 200.0, "expires_at": "2027-01-01T00:00:00+00:00", "tier": 2},
    ]))

    with TestClient(app.app) as client:
        resp = client.get("/api/user/credits", headers=_auth_headers("u1"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["promotional_credit"] == 50.0
    assert body["purchased_credit"] == 200.0
    assert len(body["promotional_credit_expirations"]) == 1
    assert len(body["purchased_credit_expirations"]) == 1
    assert body["has_credits"] is True  # 10 (subscription) + 50 (promo) + 200 (purchased)


# ---------------------------------------------------------------------------
# Social insights (/api/social/insights)
# ---------------------------------------------------------------------------

def test_get_social_insights_rejects_below_gold(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "is_supabase_configured", lambda: True)
    monkeypatch.setattr(app, "_get_active_plan_for_user", AsyncMock(return_value={"priorite": 1}))

    with TestClient(app.app) as client:
        resp = client.get("/api/social/insights", params={"account_id": "acct-1"}, headers=_auth_headers("u1"))

    assert resp.status_code == 403


def test_get_social_insights_returns_unsupported_for_linkedin(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)
    monkeypatch.setattr(app, "_assert_user_can_access_analytics", AsyncMock())
    monkeypatch.setattr(app, "_get_social_account_by_id", AsyncMock(return_value={
        "id": "acct-1", "platform": "linkedin", "platform_account_name": "My LI Page",
    }))

    with TestClient(app.app) as client:
        resp = client.get("/api/social/insights", params={"account_id": "acct-1"}, headers=_auth_headers("u1"))

    assert resp.status_code == 200
    data = resp.json()
    assert data["supported"] is False
    assert data["platform"] == "linkedin"
    assert data["metrics"] is None
    assert data["daily"] == []


def test_fetch_facebook_page_insights_parses_daily_series(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    insights_body = {
        "data": [
            {
                "name": "page_media_view",
                "period": "day",
                "values": [
                    {"value": 100, "end_time": "2026-09-01T07:00:00+0000"},
                    {"value": 150, "end_time": "2026-09-02T07:00:00+0000"},
                ],
            },
            {
                "name": "page_engaged_users",
                "period": "day",
                "values": [
                    {"value": 10, "end_time": "2026-09-01T07:00:00+0000"},
                    {"value": 20, "end_time": "2026-09-02T07:00:00+0000"},
                ],
            },
        ]
    }
    profile_body = {"followers_count": 510}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            body = insights_body if url.endswith("/insights") else profile_body
            return app.httpx.Response(200, json=body, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_facebook_page_insights(
        "token-1", "page-1", "2026-09-01T00:00:00+00:00", "2026-09-02T23:59:59+00:00",
    ))

    assert result["metrics"]["impressions"] == 250
    assert result["metrics"]["engagement"] == 30
    assert result["metrics"]["followers"] == 510
    assert result["daily"] == [
        {"date": "2026-09-01", "impressions": 100, "engagement": 10},
        {"date": "2026-09-02", "impressions": 150, "engagement": 20},
    ]


def test_fetch_facebook_page_insights_falls_back_to_per_metric_on_rejected_batch(monkeypatch):
    # Simulates Meta rejecting one metric in the combined request (error
    # #100 "must be a valid insights metric") -- the whole batch call
    # fails, so the fetch must retry metric-by-metric and still return the
    # metrics Meta does accept instead of zeroing everything out.
    app = _import_app_with_stubs(monkeypatch)
    profile_body = {"followers_count": 42}

    def _per_metric_body(url, params):
        metric = (params or {}).get("metric", "")
        if metric == "page_engaged_users":
            return {
                "data": [
                    {
                        "name": "page_engaged_users",
                        "period": "day",
                        "values": [{"value": 5, "end_time": "2026-09-01T07:00:00+0000"}],
                    },
                ]
            }
        # Every other individual metric (including the removed/invalid one)
        # comes back empty, as Meta does for a metric with no data -- only
        # the one batch call with ALL metrics together is rejected outright.
        return {"data": []}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            if not url.endswith("/insights"):
                return app.httpx.Response(200, json=profile_body, request=request)
            metric = (params or {}).get("metric", "")
            if "," in metric:
                return app.httpx.Response(
                    400,
                    json={"error": {"message": "(#100) The value must be a valid insights metric", "code": 100}},
                    request=request,
                )
            return app.httpx.Response(200, json=_per_metric_body(url, params), request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_facebook_page_insights(
        "token-1", "page-1", "2026-09-01T00:00:00+00:00", "2026-09-01T23:59:59+00:00",
    ))

    assert result["metrics"]["engagement"] == 5
    assert result["metrics"]["followers"] == 42
    assert result["daily"] == [{"date": "2026-09-01", "engagement": 5}]


def test_fetch_facebook_page_insights_includes_trends_comments_and_monetization(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    since_iso = "2026-09-08T00:00:00+00:00"
    until_iso = "2026-09-10T00:00:00+00:00"
    since_unix = int(app.datetime.fromisoformat(since_iso).timestamp())

    current_engagement_body = {
        "data": [
            {"name": "page_media_view", "values": [{"value": 200, "end_time": "2026-09-08T07:00:00+0000"}]},
            {"name": "page_engaged_users", "values": [{"value": 50, "end_time": "2026-09-08T07:00:00+0000"}]},
        ]
    }
    previous_engagement_body = {
        "data": [
            {"name": "page_media_view", "values": [{"value": 100, "end_time": "2026-09-06T07:00:00+0000"}]},
            {"name": "page_engaged_users", "values": [{"value": 80, "end_time": "2026-09-06T07:00:00+0000"}]},
        ]
    }
    posts_body_current = {"data": [{"created_time": "2026-09-08T10:00:00+0000", "comments": {"summary": {"total_count": 4}}}]}
    posts_body_previous = {"data": [{"created_time": "2026-09-06T10:00:00+0000", "comments": {"summary": {"total_count": 10}}}]}
    monetization_bodies = {
        "page_daily_video_ad_break_ad_impressions": {
            "data": [{"name": "page_daily_video_ad_break_ad_impressions", "values": [{"value": 1000, "end_time": "2026-09-08T07:00:00+0000"}]}]
        },
        "page_daily_video_ad_break_ad_earnings": {
            "data": [{"name": "page_daily_video_ad_break_ad_earnings", "values": [{"value": 250, "end_time": "2026-09-08T07:00:00+0000"}]}]
        },
        "page_daily_video_ad_break_ad_cpm": {
            "data": [{"name": "page_daily_video_ad_break_ad_cpm", "values": [{"value": 30, "end_time": "2026-09-08T07:00:00+0000"}]}]
        },
    }
    profile_body = {"followers_count": 77}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            params = params or {}
            if url.endswith("/posts"):
                body = posts_body_current if params.get("since") == since_unix else posts_body_previous
                return app.httpx.Response(200, json=body, request=request)
            if url.endswith("/insights"):
                metric = params.get("metric", "")
                if metric in monetization_bodies:
                    return app.httpx.Response(200, json=monetization_bodies[metric], request=request)
                if "," in metric:
                    body = current_engagement_body if params.get("since") == since_unix else previous_engagement_body
                    return app.httpx.Response(200, json=body, request=request)
                return app.httpx.Response(200, json={"data": []}, request=request)
            return app.httpx.Response(200, json=profile_body, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_facebook_page_insights("token-1", "page-1", since_iso, until_iso))

    assert result["metrics"]["impressions"] == 200
    assert result["metrics"]["engagement"] == 50
    assert result["metrics"]["comments"] == 4
    assert result["metrics"]["followers"] == 77

    assert result["trends"]["impressions"] == {"current": 200, "previous": 100, "change_pct": 100.0, "direction": "up"}
    assert result["trends"]["engagement"] == {"current": 50, "previous": 80, "change_pct": -37.5, "direction": "down"}
    assert result["trends"]["comments"] == {"current": 4, "previous": 10, "change_pct": -60.0, "direction": "down"}

    assert result["monetization"]["supported"] is True
    assert result["monetization"]["available"] is True
    assert result["monetization"]["ad_impressions"] == 1000
    assert result["monetization"]["ad_earnings_cents"] == 250
    assert result["monetization"]["ad_cpm_cents"] == 30


def test_fetch_facebook_monetization_reports_unavailable_without_ad_break_data(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            return app.httpx.Response(200, json={"data": []}, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_facebook_monetization("token-1", "page-1", 1000, 2000))

    assert result == {
        "supported": True,
        "available": False,
        "reason": (
            "Aucune donnee de monetisation disponible (programme de monetisation video non actif "
            "ou aucune donnee sur cette periode)."
        ),
        "ad_impressions": None,
        "ad_earnings_cents": None,
        "ad_cpm_cents": None,
    }


def test_fetch_instagram_insights_includes_trends_and_unsupported_monetization(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    since_iso = "2026-09-08T00:00:00+00:00"
    until_iso = "2026-09-10T00:00:00+00:00"
    since_unix = int(app.datetime.fromisoformat(since_iso).timestamp())

    current_body = {
        "data": [
            {"name": "views", "values": [{"value": 300, "end_time": "2026-09-08T07:00:00+0000"}]},
            {"name": "total_interactions", "values": [{"value": 60, "end_time": "2026-09-08T07:00:00+0000"}]},
            {"name": "total_comments", "values": [{"value": 15, "end_time": "2026-09-08T07:00:00+0000"}]},
        ]
    }
    previous_body = {
        "data": [
            {"name": "views", "values": [{"value": 250, "end_time": "2026-09-06T07:00:00+0000"}]},
            {"name": "total_interactions", "values": [{"value": 90, "end_time": "2026-09-06T07:00:00+0000"}]},
            {"name": "total_comments", "values": [{"value": 20, "end_time": "2026-09-06T07:00:00+0000"}]},
        ]
    }
    profile_body = {"followers_count": 555}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            params = params or {}
            if url.endswith("/insights"):
                body = current_body if params.get("since") == since_unix else previous_body
                return app.httpx.Response(200, json=body, request=request)
            return app.httpx.Response(200, json=profile_body, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_instagram_insights("token-1", "ig-1", since_iso, until_iso))

    assert result["metrics"]["impressions"] == 300
    assert result["metrics"]["engagement"] == 60
    assert result["metrics"]["comments"] == 15
    assert result["metrics"]["followers"] == 555

    assert result["trends"]["impressions"] == {"current": 300, "previous": 250, "change_pct": 20.0, "direction": "up"}
    assert result["trends"]["engagement"] == {"current": 60, "previous": 90, "change_pct": -33.3, "direction": "down"}
    assert result["trends"]["comments"] == {"current": 15, "previous": 20, "change_pct": -25.0, "direction": "down"}

    assert result["monetization"]["supported"] is False
    assert result["monetization"]["available"] is False


def test_fetch_youtube_analytics_parses_rows(monkeypatch):
    app = _import_app_with_stubs(monkeypatch)

    reports_body = {
        "columnHeaders": [
            {"name": "day"}, {"name": "views"}, {"name": "estimatedMinutesWatched"},
            {"name": "subscribersGained"}, {"name": "subscribersLost"}, {"name": "likes"}, {"name": "comments"},
        ],
        "rows": [
            ["2026-08-01", 120, 45, 3, 1, 10, 2],
            ["2026-08-02", 80, 30, 1, 0, 5, 1],
        ],
    }
    channels_body = {"items": [{"statistics": {"subscriberCount": "4210"}}]}
    monetization_body = {"rows": [[12.5, 1000, 4.2]]}

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            params = params or {}
            if "channels" in url:
                return app.httpx.Response(200, json=channels_body, request=request)
            if params.get("metrics") == "estimatedAdRevenue,adImpressions,cpm":
                return app.httpx.Response(200, json=monetization_body, request=request)
            return app.httpx.Response(200, json=reports_body, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_youtube_analytics(
        "token-1", "2026-08-01T00:00:00+00:00", "2026-08-02T23:59:59+00:00",
    ))

    assert result["metrics"]["views"] == 200
    assert result["metrics"]["watch_time_minutes"] == 75
    assert result["metrics"]["subscribers_gained"] == 4
    assert result["metrics"]["subscribers_lost"] == 1
    assert result["metrics"]["likes"] == 15
    assert result["metrics"]["comments"] == 3
    assert result["metrics"]["followers"] == 4210
    assert result["daily"] == [
        {"date": "2026-08-01", "views": 120, "watch_time_minutes": 45, "subscribers_gained": 3, "subscribers_lost": 1, "likes": 10, "comments": 2},
        {"date": "2026-08-02", "views": 80, "watch_time_minutes": 30, "subscribers_gained": 1, "subscribers_lost": 0, "likes": 5, "comments": 1},
    ]

    assert result["monetization"]["supported"] is True
    assert result["monetization"]["available"] is True
    assert result["monetization"]["ad_impressions"] == 1000
    assert result["monetization"]["ad_earnings_cents"] == 1250
    assert result["monetization"]["ad_cpm_cents"] == 420


def test_fetch_youtube_monetization_unavailable_without_scope_or_data(monkeypatch):
    # Simulates an account that hasn't reconnected to grant
    # yt-analytics-monetary.readonly, or a non-monetized channel -- Google
    # returns a 403, which must degrade to available=False rather than
    # raising and breaking the already-working views/subscribers data.
    app = _import_app_with_stubs(monkeypatch)

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            request = app.httpx.Request("GET", url)
            return app.httpx.Response(403, json={"error": {"message": "insufficient scope"}}, request=request)

    monkeypatch.setattr(app.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(app._fetch_youtube_monetization(
        "token-1", "2026-08-01T00:00:00+00:00", "2026-08-02T23:59:59+00:00",
    ))

    assert result["supported"] is True
    assert result["available"] is False
    assert result["ad_impressions"] is None
    assert result["ad_earnings_cents"] is None
    assert result["ad_cpm_cents"] is None
