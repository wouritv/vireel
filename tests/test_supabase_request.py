import asyncio
import importlib
import sys
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock


class _FakeResponse:
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count


class _NotFilter:
    """Helper class to support .not_.is_() chaining pattern"""
    def __init__(self, query):
        self.query = query

    def is_(self, *args, **kwargs):
        return self.query._record("is_", *args, **kwargs)


class _FakeQuery:
    def __init__(self, table_name, events, responses):
        self.table_name = table_name
        self.events = events
        self.responses = responses
        self._not = _NotFilter(self)

    def _record(self, method, *args, **kwargs):
        self.events.append((self.table_name, method, args, kwargs))
        return self

    def select(self, *args, **kwargs):
        return self._record("select", *args, **kwargs)

    def eq(self, *args, **kwargs):
        return self._record("eq", *args, **kwargs)

    def neq(self, *args, **kwargs):
        return self._record("neq", *args, **kwargs)

    def is_(self, *args, **kwargs):
        return self._record("is_", *args, **kwargs)

    def order(self, *args, **kwargs):
        return self._record("order", *args, **kwargs)

    def range(self, *args, **kwargs):
        return self._record("range", *args, **kwargs)

    def or_(self, *args, **kwargs):
        return self._record("or_", *args, **kwargs)

    def limit(self, *args, **kwargs):
        return self._record("limit", *args, **kwargs)

    def update(self, *args, **kwargs):
        return self._record("update", *args, **kwargs)

    def insert(self, *args, **kwargs):
        return self._record("insert", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._record("delete", *args, **kwargs)

    def upsert(self, *args, **kwargs):
        return self._record("upsert", *args, **kwargs)

    def gte(self, *args, **kwargs):
        return self._record("gte", *args, **kwargs)

    def lte(self, *args, **kwargs):
        return self._record("lte", *args, **kwargs)

    def gt(self, *args, **kwargs):
        return self._record("gt", *args, **kwargs)

    def ilike(self, *args, **kwargs):
        return self._record("ilike", *args, **kwargs)

    def in_(self, *args, **kwargs):
        return self._record("in_", *args, **kwargs)

    @property
    def not_(self):
        """Return a helper object that supports .is_() chaining"""
        return self._not

    async def execute(self):
        self.events.append((self.table_name, "execute", (), {}))
        if self.responses:
            return self.responses.pop(0)
        return _FakeResponse(data=[], count=0)


class _FakeRPCCall:
    def __init__(self, fn, params, events, response):
        self.fn = fn
        self.params = params
        self.events = events
        self.response = response

    async def execute(self):
        self.events.append(("rpc", self.fn, (), self.params or {}))
        return self.response


class _FakeClient:
    def __init__(self, response_map, rpc_response_map=None):
        self.events = []
        self.response_map = {key: list(value) for key, value in (response_map or {}).items()}
        # Defaults to a no-op promo consumption so any test exercising
        # deduct_user_credits (the universal choke point calling
        # consume_promotional_credits first) doesn't need its own RPC stub
        # unless it specifically cares about promotional-credit behavior.
        self.rpc_response_map = {
            "consume_promotional_credits": _FakeResponse(data={"consumed": 0.0, "batches": []}),
            "restore_promotional_credits": _FakeResponse(data=None),
            **(rpc_response_map or {}),
        }

    def table(self, table_name):
        self.events.append((table_name, "table", (), {}))
        return _FakeQuery(table_name, self.events, self.response_map.setdefault(table_name, []))

    def rpc(self, fn, params=None):
        return _FakeRPCCall(fn, params, self.events, self.rpc_response_map.get(fn, _FakeResponse(data=None)))


def _event_args(events, table, method):
    for event_table, event_method, args, _kwargs in events:
        if event_table == table and event_method == method:
            return args
    return None


def _event_count(events, table, method):
    return sum(1 for event_table, event_method, _args, _kwargs in events if event_table == table and event_method == method)


def _patch_get_client(monkeypatch, supabase_request, fake_client):
    async def _fake_get_client():
        return fake_client

    monkeypatch.setattr(supabase_request, "get_client", _fake_get_client)


def _import_supabase_request_with_stubs(monkeypatch):
    supabase_mod = types.ModuleType("supabase")

    class _AsyncClient:
        pass

    async def _acreate_client(*args, **kwargs):
        return {"url": args[0], "key": args[1], "options": kwargs.get("options")}

    supabase_mod.AsyncClient = _AsyncClient
    supabase_mod.acreate_client = _acreate_client

    client_options_mod = types.ModuleType("supabase.lib.client_options")

    class _AsyncClientOptions:
        def __init__(self, postgrest_client_timeout):
            self.postgrest_client_timeout = postgrest_client_timeout

    client_options_mod.AsyncClientOptions = _AsyncClientOptions

    monkeypatch.setitem(sys.modules, "supabase", supabase_mod)
    monkeypatch.setitem(sys.modules, "supabase.lib.client_options", client_options_mod)

    if "supabase_request" in sys.modules:
        return importlib.reload(sys.modules["supabase_request"])
    return importlib.import_module("supabase_request")


def test_is_supabase_configured_reflects_module_settings(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    monkeypatch.setattr(supabase_request, "SUPABASE_URL", "https://db.example")
    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    assert supabase_request.is_supabase_configured() is True

    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert supabase_request.is_supabase_configured() is False


def test_ceil_credit_rounds_up_and_never_negative(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    assert supabase_request._ceil_credit(2.01) == 3
    assert supabase_request._ceil_credit(0) == 0
    assert supabase_request._ceil_credit(-10) == 0


def test_get_client_creates_singleton_once(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    monkeypatch.setattr(supabase_request, "SUPABASE_URL", "https://db.example")
    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(supabase_request, "_client", None)

    client_1 = asyncio.run(supabase_request.get_client())
    client_2 = asyncio.run(supabase_request.get_client())

    assert client_1 == client_2


def test_list_reels_builds_expected_query_and_escapes_search(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "r1"}], count=7)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_reels("user-1", page=0, page_size=999, status="termine", query="my*query")
    )

    assert rows == [{"id": "r1"}]
    assert total == 7
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "range") == (0, 99)
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "or_") == (
        'reel_title.ilike."*myquery*",reel_description.ilike."*myquery*"',
    )


def test_list_captions_uses_caption_columns_and_filters(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "c1"}], count=2)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_captions("user-2", page=2, page_size=20, status="en_cours", query="cap*tion")
    )

    assert rows == [{"id": "c1"}]
    assert total == 2
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "select") == (
        supabase_request.CAPTION_COLUMNS,
    )
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "range") == (20, 39)
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "or_") == (
        'caption_title.ilike."*caption*",caption_description.ilike."*caption*"',
    )


def test_build_ilike_or_filter_escapes_postgrest_metacharacters(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    # Security regression test (audit finding P2-7): a raw comma/paren in the
    # search term used to let it break out of the ilike value and inject
    # extra filter clauses into the PostgREST `or=(...)` string. Wrapping the
    # value in double quotes (escaping embedded backslashes/quotes) keeps
    # those characters literal instead of structural.
    injected = 'x",other_column.eq.secret'
    result = supabase_request._build_ilike_or_filter(injected, ["title", "description"])

    assert result == (
        'title.ilike."*x\\",other_column.eq.secret*",'
        'description.ilike."*x\\",other_column.eq.secret*"'
    )


def test_get_reel_returns_none_when_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reel("reel-x", "user-x"))

    assert result is None
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "limit") == (1,)


def test_update_reel_media_by_job_clip_builds_payload_and_casts_clip_index(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "row-1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(
        supabase_request.update_reel_media_by_job_clip(
            job_id="job-1",
            clip_index="3",
            reel_url="https://cdn.example/reel.mp4",
            reel_s3_key="reels/u/job-1/reel.mp4",
            reel_thumbnail_url="",
        )
    )

    assert row == {"id": "row-1"}
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_REELS_TABLE, "update")[0]
    assert update_payload["reel_url"] == "https://cdn.example/reel.mp4"
    assert update_payload["reel_s3_key"] == "reels/u/job-1/reel.mp4"
    assert "reel_thumbnail_url" in update_payload
    assert "reel_updated_at" in update_payload

    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_REELS_TABLE and method == "eq"]
    assert ("reel_clip_index", 3) in eq_calls


def test_create_project_returns_payload_fallback_and_maps_fields(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.create_project(
            user_id="user-p",
            name="Project A",
            project_type="reel",
            source_type="file",
            source_s3_key="uploads/a.mp4",
            source_size="1024",
            description="desc",
            source_url="https://example.com/a.mp4",
            source_duration=70,
            thumbnail_url="https://example.com/t.jpg",
            status="processing",
        )
    )

    assert result["user_id"] == "user-p"
    assert result["source_size"] == 1024
    assert result["output_count"] == 0
    assert result["status"] == "processing"
    assert "created_at" in result and "updated_at" in result


def test_update_project_adds_updated_at_and_returns_selected_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_PROJECTS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "proj-1", "name": "Updated"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.update_project("proj-1", "user-9", {"name": "Updated", "status": "completed"})
    )

    assert result == {"id": "proj-1", "name": "Updated"}
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "update")[0]
    assert update_payload["name"] == "Updated"
    assert update_payload["status"] == "completed"
    assert "updated_at" in update_payload
    assert _event_count(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "execute") == 2


def test_create_job_record_clamps_priority_and_attempts(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_JOBS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    payload = asyncio.run(
        supabase_request.create_job_record(
            job_id="job-raw",
            user_id="user-j",
            job_type="GENERATE_REELS",
            status="created",
            job_data={},
            queue_name="reels",
            pipeline_name="pipe",
            max_attempts=0,
            reserved_quota="1.5",
            estimated_cost_usd="0.25",
            priority=99,
        )
    )

    assert payload["max_attempts"] == 1
    assert payload["priority"] == 3
    assert payload["reserved_quota"] == 1.5
    assert payload["estimated_cost_usd"] == 0.25
    assert payload["current_step"] == "created"


def test_get_caption_by_job_clip_casts_index_and_returns_first_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "cap-x"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.get_caption_by_job_clip("job-c", "4", "user-c"))

    assert row == {"id": "cap-x"}
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_CAPTIONS_TABLE and method == "eq"]
    assert ("caption_clip_index", 4) in eq_calls
    assert _event_args(fake_client.events, supabase_request.SUPABASE_CAPTIONS_TABLE, "limit") == (1,)


def test_list_projects_applies_filters_and_pagination(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[{"id": "p1"}], count=4)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_projects(
            user_id="u-1",
            page=2,
            page_size=10,
            project_type="reel",
            status="completed",
            query="name*",
        )
    )
    assert rows == [{"id": "p1"}]
    assert total == 4
    assert _event_args(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "range") == (10, 19)
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_PROJECTS_TABLE and method == "eq"]
    assert ("project_type", "reel") in eq_calls
    assert ("status", "completed") in eq_calls


def test_get_project_returns_first_or_none(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_PROJECTS_TABLE: [
                _FakeResponse(data=[{"id": "p1"}]),
                _FakeResponse(data=[]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    assert asyncio.run(supabase_request.get_project("p1", "u1")) == {"id": "p1"}
    assert asyncio.run(supabase_request.get_project("p2", "u1")) is None


def test_update_project_status_rejects_invalid_status(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_project_status("", "completed")) is None
    assert asyncio.run(supabase_request.update_project_status("p1", "processing")) is None


def test_update_project_status_builds_payload(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[{"id": "p1", "status": "completed"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.update_project_status("p1", "completed"))
    assert row == {"id": "p1", "status": "completed"}
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_PROJECTS_TABLE, "update")[0]
    assert payload["status"] == "completed"
    assert "completed_at" in payload
    assert "updated_at" in payload


def test_caption_status_value_defaults_to_termine(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert supabase_request.caption_status_value("en_cours") == "en_cours"
    assert supabase_request.caption_status_value("echec") == "echec"
    assert supabase_request.caption_status_value("other") == "termine"


def test_add_one_month_handles_december_and_month_end(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    from datetime import datetime

    # Test December to January
    dec = datetime(2024, 12, 15, 10, 30)
    result = supabase_request.add_one_month(dec)
    assert result.month == 1
    assert result.year == 2025
    assert result.day == 15

    # Test month-end handling (Jan 31 -> Feb 28)
    jan31 = datetime(2024, 1, 31, 10, 30)
    result = supabase_request.add_one_month(jan31)
    assert result.month == 2
    assert result.day == 29  # 2024 is a leap year


def test_add_one_year_handles_leap_day(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    from datetime import datetime

    leap_day = datetime(2024, 2, 29, 10, 30)
    result = supabase_request.add_one_year(leap_day)
    assert result.year == 2025
    assert result.month == 2
    assert result.day == 28

    regular = datetime(2024, 6, 15, 10, 30)
    result = supabase_request.add_one_year(regular)
    assert result.year == 2025
    assert result.month == 6
    assert result.day == 15


def test_insert_reels_returns_empty_for_empty_input(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_reels([]))
    assert result == []


def test_soft_delete_reel_returns_bool(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "r1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_reel("r1", "u1"))
    assert result is True


# --------------------------------------------------------------------------
# Reel visuals
# --------------------------------------------------------------------------

def test_insert_reel_visual_builds_payload(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=[{"id": "v1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.insert_reel_visual("reel-1", "u1", "TOP", 12.5, 5.0, "reels/u1/job1/visual_0_v1.jpg")
    )
    assert result["id"] == "v1"
    insert_args = _event_args(fake_client.events, supabase_request.SUPABASE_REEL_VISUALS_TABLE, "insert")
    payload = insert_args[0]
    assert payload["reel_id"] == "reel-1"
    assert payload["position"] == "TOP"
    assert payload["start_time"] == 12.5
    assert payload["duration"] == 5.0


def test_list_reel_visuals_orders_by_start_time(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    rows = [{"id": "v1", "start_time": 1.0}, {"id": "v2", "start_time": 5.0}]
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=rows)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.list_reel_visuals("reel-1"))
    assert result == rows
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REEL_VISUALS_TABLE, "order") == ("start_time",)


def test_list_reel_visuals_empty_reel_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.list_reel_visuals("")) == []


def test_get_reel_visual_scoped_to_owner(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=[{"id": "v1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reel_visual("v1", "u1"))
    assert result["id"] == "v1"


def test_get_reel_visual_returns_none_when_missing(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    assert asyncio.run(supabase_request.get_reel_visual("v1", "u1")) is None


def test_update_reel_visual_builds_payload(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=[{"id": "v1", "start_time": 20.0}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.update_reel_visual("v1", "u1", {"start_time": 20.0}))
    assert result["start_time"] == 20.0


def test_update_reel_visual_noop_for_empty_updates(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_reel_visual("v1", "u1", {})) is None


def test_delete_reel_visual_returns_deleted_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=[{"id": "v1", "image_s3_key": "k1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.delete_reel_visual("v1", "u1"))
    assert result["image_s3_key"] == "k1"


def test_delete_reel_visual_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REEL_VISUALS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    assert asyncio.run(supabase_request.delete_reel_visual("v1", "u1")) is None


def test_get_reel_by_job_clip_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reel_by_job_clip("job-x", 0))
    assert result is None


def test_update_reel_media_by_job_clip_returns_none_for_missing_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    # Missing reel_url
    result = asyncio.run(
        supabase_request.update_reel_media_by_job_clip("job-1", 0, "", None, None)
    )
    assert result is None

    # Missing job_id
    result = asyncio.run(
        supabase_request.update_reel_media_by_job_clip("", 0, "http://example.com/r.mp4", None, None)
    )
    assert result is None


def test_soft_delete_project_deletes_reels_captions_and_project(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])],
        supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])],
        supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [_FakeResponse(data=[])],
        # Two responses: the ownership-verification SELECT done before any
        # cascading delete (security hardening, audit finding H5), then the
        # final project DELETE.
        supabase_request.SUPABASE_PROJECTS_TABLE: [
            _FakeResponse(data=[{"id": "p1"}]),
            _FakeResponse(data=[{"id": "p1"}]),
        ],
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_project("p1", "u1"))
    assert result is True
    assert _event_count(fake_client.events, supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE, "delete") == 1


def test_get_reels_by_project_returns_empty_list_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_reels_by_project("p-x"))
    assert result == []


def test_get_reels_by_project_returns_empty_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_reels_by_project(""))
    assert result == []


def test_get_captions_by_project_returns_empty_list(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_captions_by_project("p-y"))
    assert result == []


def test_get_anonymous_stories_by_project_returns_rows(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [_FakeResponse(data=[{"id": "s1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_anonymous_stories_by_project("p-1"))
    assert result == [{"id": "s1"}]


def test_get_anonymous_stories_by_project_returns_empty_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_anonymous_stories_by_project(""))
    assert result == []


def test_increment_project_output_count_increments_value(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_PROJECTS_TABLE: [
            _FakeResponse(data=[{"id": "p1", "output_count": 5}]),
            _FakeResponse(data=[{"id": "p1", "output_count": 6}]),
        ]
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.increment_project_output_count("p1"))
    assert result == {"id": "p1", "output_count": 6}


def test_increment_project_output_count_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_PROJECTS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.increment_project_output_count("p-missing"))
    assert result is None


def test_insert_captions_returns_empty_for_empty_input(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_captions([]))
    assert result == []


def test_get_caption_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_caption("cap-missing", "u1"))
    assert result is None


def test_get_caption_by_job_clip_any_returns_none(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_caption_by_job_clip_any("job-x", 0))
    assert result is None


def test_soft_delete_caption_returns_bool(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "c1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_caption("c1", "u1"))
    assert result is True


def test_get_transcription_by_job_clip_returns_none_for_missing_user(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_transcription_by_job_clip("job-1", 0, ""))
    assert result is None


def test_upsert_transcription_returns_none_for_empty_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.upsert_transcription(None))
    assert result is None


def test_upsert_transcription_returns_payload_when_no_response(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_TRANSCRIPTIONS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = {"user_id": "u1", "job_id": "j1", "clip_index": 0}
    result = asyncio.run(supabase_request.upsert_transcription(row))
    assert result == row


def test_insert_style_edit_version_returns_none_for_empty_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_style_edit_version(None))
    assert result is None


def test_list_style_edit_versions_returns_empty_for_missing_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.list_style_edit_versions("", 0, "u1"))
    assert result == []


# --------------------------------------------------------------------------
# Anonymous stories
# --------------------------------------------------------------------------

def test_insert_anonymous_story_returns_none_for_empty_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.insert_anonymous_story(None))
    assert result is None


def test_insert_anonymous_story_returns_inserted_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [_FakeResponse(data=[{"id": "s1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.insert_anonymous_story({"user_id": "u1"}))
    assert result == {"id": "s1"}


def test_list_anonymous_stories_applies_filters_and_pagination(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [_FakeResponse(data=[{"id": "s1"}], count=3)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(
        supabase_request.list_anonymous_stories("user-1", page=0, page_size=999, status="completed", query="my*query")
    )

    assert rows == [{"id": "s1"}]
    assert total == 3
    assert _event_args(fake_client.events, supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE, "range") == (0, 99)
    assert _event_args(fake_client.events, supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE, "or_") == (
        'title.ilike."*myquery*"',
    )


def test_get_anonymous_story_returns_none_for_missing_ids(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_anonymous_story("", "u1"))
    assert result is None


def test_get_anonymous_story_returns_first_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [_FakeResponse(data=[{"id": "s1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_anonymous_story("s1", "u1"))
    assert result == {"id": "s1"}


def test_get_anonymous_story_by_job_returns_none_for_missing_ids(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_anonymous_story_by_job("", "u1"))
    assert result is None


def test_update_anonymous_story_returns_none_for_missing_ids(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.update_anonymous_story("", "u1", {}))
    assert result is None


def test_update_anonymous_story_sets_updated_at_and_returns_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [
            _FakeResponse(data=[{"id": "s1", "status": "completed"}]),  # .update().execute()
            _FakeResponse(data=[{"id": "s1", "status": "completed"}]),  # re-select via get_anonymous_story
        ]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.update_anonymous_story("s1", "u1", {"status": "completed"}))
    assert result == {"id": "s1", "status": "completed"}
    update_args = _event_args(fake_client.events, supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE, "update")
    assert update_args[0]["status"] == "completed"
    assert "updated_at" in update_args[0]


def test_soft_delete_anonymous_story_returns_false_for_missing_ids(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.soft_delete_anonymous_story("", "u1"))
    assert result is False


def test_soft_delete_anonymous_story_returns_bool(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ANONYMOUS_STORIES_TABLE: [_FakeResponse(data=[{"id": "s1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.soft_delete_anonymous_story("s1", "u1"))
    assert result is True


def test_delete_style_edit_versions_returns_zero_for_missing_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.delete_style_edit_versions("", 0, ""))
    assert result == 0


def test_list_abonnements_returns_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ABONNEMENTS_TABLE: [_FakeResponse(data=[{"id": "a1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.list_abonnements())
    assert result == [{"id": "a1"}]
    # Explicit display order (see the "ordre" migration) replaces the
    # previous created_at ordering, which had nothing to do with how
    # plans should be presented.
    assert _event_args(fake_client.events, supabase_request.SUPABASE_ABONNEMENTS_TABLE, "order") == ("ordre",)


def test_get_abonnement_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_ABONNEMENTS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_abonnement("a-missing"))
    assert result is None


def test_insert_souscription_builds_payload_with_dates(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1",
            abonnement="plan-pro",
            payment_mode="stripe",
            payment_amount=99.99,
            payment_reference="ref-123",
            payment_status="confirmed",
        )
    )
    assert result["userid"] == "u1"
    assert result["abonnement"] == "plan-pro"
    assert "payment_start_date" in result
    assert "payment_end_date" in result


def test_insert_souscription_uses_explicit_period_end_date_and_stripe_ids(monkeypatch):
    # A Stripe subscription renewal invoice carries its own authoritative
    # billing period and IDs -- period_end_date must override the default
    # +1-calendar-month rule, and the stripe_* columns must be persisted so
    # a later renewal invoice can be traced back to it.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    period_end = datetime(2026, 11, 3, tzinfo=timezone.utc)
    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1",
            abonnement="plan-pro",
            payment_mode="stripe",
            payment_amount=99.99,
            payment_reference="in_renewal_1",
            payment_status="completed",
            billing={
                "period_end_date": period_end,
                "stripe_subscription_id": "sub_123",
                "stripe_customer_id": "cus_456",
            },
        )
    )
    assert result["payment_end_date"] == period_end.isoformat()
    assert result["stripe_subscription_id"] == "sub_123"
    assert result["stripe_customer_id"] == "cus_456"


def test_insert_souscription_annual_defaults_to_plus_one_year(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1", abonnement="plan-pro", payment_mode="stripe",
            payment_amount=114.0, payment_reference="ref-annual",
            payment_status="completed", payment_date=start,
            billing={"billing_interval": "year"},
        )
    )
    assert result["billing_interval"] == "year"
    assert result["payment_end_date"] == datetime(2027, 1, 15, tzinfo=timezone.utc).isoformat()


def test_insert_souscription_persists_plan_snapshot_and_next_allocation(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    next_allocation = datetime(2026, 2, 15, tzinfo=timezone.utc)
    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1", abonnement="plan-pro", payment_mode="stripe",
            payment_amount=114.0, payment_reference="ref-annual", payment_status="completed",
            billing={"billing_interval": "year"},
            allocation={
                "plan_credit": 500.0, "plan_stockage": 1.0,
                "next_credit_allocation_at": next_allocation,
            },
        )
    )
    assert result["plan_credit"] == 500.0
    assert result["plan_stockage"] == 1.0
    assert result["next_credit_allocation_at"] == next_allocation.isoformat()


def test_insert_souscription_monthly_credit_cycle_matches_billing_period(monkeypatch):
    # Plan-change rework spec section 2: for a monthly subscription the
    # credit-allocation cycle and the paid billing period are the same
    # thing -- credit_cycle_start_at/end_at must default to exactly the
    # same dates as payment_start_date/payment_end_date.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    start = datetime(2026, 1, 31, tzinfo=timezone.utc)
    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1", abonnement="plan-pro", payment_mode="stripe",
            payment_amount=10.0, payment_reference="ref-monthly",
            payment_status="completed", payment_date=start,
        )
    )
    assert result["credit_cycle_start_at"] == result["payment_start_date"]
    assert result["credit_cycle_end_at"] == result["payment_end_date"]
    # Jan 31 + 1 month -> Feb 28 (2026 is not a leap year), anniversary
    # day preserved for later months (see add_one_month).
    assert result["payment_end_date"] == datetime(2026, 2, 28, tzinfo=timezone.utc).isoformat()


def test_insert_souscription_annual_credit_cycle_is_one_month_subwindow(monkeypatch):
    # For an annual subscription the credit cycle is only a one-month
    # sub-window of the paid year, not the whole annual period -- must
    # default to +1 month from the cycle start, never to the annual
    # payment_end_date.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    start = datetime(2026, 1, 15, tzinfo=timezone.utc)
    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1", abonnement="plan-pro", payment_mode="stripe",
            payment_amount=114.0, payment_reference="ref-annual-cycle",
            payment_status="completed", payment_date=start,
            billing={"billing_interval": "year"},
        )
    )
    assert result["payment_end_date"] == datetime(2027, 1, 15, tzinfo=timezone.utc).isoformat()
    assert result["credit_cycle_start_at"] == start.isoformat()
    assert result["credit_cycle_end_at"] == datetime(2026, 2, 15, tzinfo=timezone.utc).isoformat()


def test_insert_souscription_credit_cycle_explicit_override_wins(monkeypatch):
    # An immediate upgrade carries the EXISTING credit-cycle dates forward
    # explicitly (spec section 3: "conserve les dates... existantes") --
    # must override both the monthly and the annual default.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    cycle_start = datetime(2026, 1, 10, tzinfo=timezone.utc)
    cycle_end = datetime(2026, 2, 10, tzinfo=timezone.utc)
    result = asyncio.run(
        supabase_request.insert_souscription(
            user_id="u1", abonnement="plan-pro", payment_mode="stripe",
            payment_amount=7.5, payment_reference="ref-upgrade",
            payment_status="completed",
            billing={"billing_interval": "year"},
            allocation={"credit_cycle_start_at": cycle_start, "credit_cycle_end_at": cycle_end},
        )
    )
    assert result["credit_cycle_start_at"] == cycle_start.isoformat()
    assert result["credit_cycle_end_at"] == cycle_end.isoformat()


def test_list_souscriptions_due_for_monthly_credit_allocation_filters_correctly(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    due_rows = [{"id": "sous-1", "userid": "u1", "plan_credit": 500.0, "plan_stockage": 1.0}]
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=due_rows)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.list_souscriptions_due_for_monthly_credit_allocation())

    assert result == due_rows
    events = fake_client.events
    assert _event_args(events, supabase_request.SUPABASE_SOUSCRIPTION_TABLE, "eq") == ("payment_status", "completed")
    assert _event_count(events, supabase_request.SUPABASE_SOUSCRIPTION_TABLE, "lte") == 1
    assert _event_count(events, supabase_request.SUPABASE_SOUSCRIPTION_TABLE, "gte") == 1


def test_get_souscription_by_reference_returns_none_for_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_souscription_by_reference(""))
    assert result is None


def test_get_souscription_by_reference_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_souscription_by_reference("missing-ref")) is None


def test_get_user_abonnement_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_user_abonnement("u-missing"))
    assert result is None


def test_get_latest_user_souscription_returns_none_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_latest_user_souscription(""))
    assert result is None


def test_get_latest_user_paid_subscription_returns_none_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_latest_user_paid_subscription(""))
    assert result is None


def test_list_user_souscriptions_returns_empty_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.list_user_souscriptions(""))
    assert result == []


def test_update_souscription_row_returns_none_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.update_souscription_row("", {"status": "cancelled"}))
    assert result is None


def test_get_job_record_returns_none_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_job_record(""))
    assert result is None


def test_get_latest_job_record_by_project_returns_none_for_empty_params(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_latest_job_record_by_project("", "u1"))
    assert result is None


def test_append_job_log_does_nothing_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    # Should not raise
    asyncio.run(supabase_request.append_job_log("", "INFO", "message"))


def test_list_job_logs_returns_empty_for_empty_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.list_job_logs(""))
    assert result == []


def test_get_user_data_returns_none_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.get_user_data(""))
    assert result is None


def test_set_user_data_balance_returns_empty_dict_for_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.set_user_data_balance("", 100.0, 50.0))
    assert result == {"user_id": "", "credit": 0.0, "stockage": 0.0, "credit_max": 0.0, "stockage_max": 0.0}


def test_deduct_user_credits_returns_false_when_no_user_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", 10.0))
    assert result is False


def test_get_client_raises_when_not_configured(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    monkeypatch.setattr(supabase_request, "SUPABASE_URL", "")
    monkeypatch.setattr(supabase_request, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(supabase_request, "_client", None)

    try:
        asyncio.run(supabase_request.get_client())
        assert False, "Expected SupabaseNotConfiguredError"
    except supabase_request.SupabaseNotConfiguredError:
        pass


def test_insert_reels_returns_data_on_success(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "r-ok"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.insert_reels([{"reel_user_id": "u1"}]))
    assert result == [{"id": "r-ok"}]


def test_get_reel_returns_first_row_when_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "reel-1"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_reel("reel-1", "u1")) == {"id": "reel-1"}


def test_get_reel_by_job_clip_returns_first_row_when_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[{"id": "reel-job"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_reel_by_job_clip("job-1", 0)) == {"id": "reel-job"}


def test_update_reel_media_by_job_clip_returns_none_when_update_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_REELS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.update_reel_media_by_job_clip("job-2", 1, "https://cdn.example/reel.mp4")
    )
    assert result is None


def test_update_project_returns_none_for_empty_project_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    result = asyncio.run(supabase_request.update_project("", "u1", {"name": "x"}))
    assert result is None


def test_get_captions_by_project_returns_empty_for_empty_project_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.get_captions_by_project("")) == []


def test_increment_project_output_count_returns_none_for_empty_project_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.increment_project_output_count("")) is None


def test_insert_captions_returns_rows_when_successful(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "cap-ok"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows = asyncio.run(supabase_request.insert_captions([{"caption_user_id": "u1"}]))
    assert rows == [{"id": "cap-ok"}]


def test_get_caption_returns_first_row_when_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[{"id": "cap-1"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_caption("cap-1", "u1")) == {"id": "cap-1"}


def test_get_caption_by_job_clip_returns_none_when_not_found(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_CAPTIONS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_caption_by_job_clip("job-miss", 2, "u1")) is None


def test_update_caption_success_and_empty_id_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_caption("", "u1", {"caption_title": "x"})) is None

    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_CAPTIONS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "cap-2", "caption_title": "Updated"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    row = asyncio.run(supabase_request.update_caption("cap-2", "u1", {"caption_title": "Updated"}))
    assert row == {"id": "cap-2", "caption_title": "Updated"}


def test_get_transcription_by_job_clip_returns_first_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({supabase_request.SUPABASE_TRANSCRIPTIONS_TABLE: [_FakeResponse(data=[{"id": "tr-1"}])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_transcription_by_job_clip("job-1", 0, "u1")) == {"id": "tr-1"}


def test_update_transcription_translations_cache_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(
        supabase_request.update_transcription_translations_cache("", 0, "u1", {"fr": "x"})
    ) is None

    fake_client = _FakeClient({supabase_request.SUPABASE_TRANSCRIPTIONS_TABLE: [_FakeResponse(data=[])]})
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _fake_get_transcription(job_id, clip_index, user_id):
        return {"job_id": job_id, "clip_index": clip_index, "user_id": user_id, "translations_cache": {"fr": "ok"}}

    monkeypatch.setattr(supabase_request, "get_transcription_by_job_clip", _fake_get_transcription)
    row = asyncio.run(
        supabase_request.update_transcription_translations_cache(
            "job-1", 2, "u1", {"fr": "ok"}, billing_details={"cost": 1}
        )
    )
    assert row["translations_cache"]["fr"] == "ok"


def test_style_edit_version_queries_success_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_STYLE_EDIT_VERSIONS_TABLE: [
                _FakeResponse(data=[{"id": "v1"}]),
                _FakeResponse(data=[{"id": "v1"}, {"id": "v2"}]),
                _FakeResponse(data=[{"id": "v1"}, {"id": "v2"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    inserted = asyncio.run(supabase_request.insert_style_edit_version({"job_id": "j1", "clip_index": 0, "user_id": "u1"}))
    listed = asyncio.run(supabase_request.list_style_edit_versions("j1", 0, "u1"))
    deleted_count = asyncio.run(supabase_request.delete_style_edit_versions("j1", 0, "u1"))

    assert inserted == {"id": "v1"}
    assert listed == [{"id": "v1"}, {"id": "v2"}]
    assert deleted_count == 2


def test_subscription_read_paths_return_rows(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_ABONNEMENTS_TABLE: [_FakeResponse(data=[{"id": "ab1"}])],
            supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [
                _FakeResponse(data=[{"id": "sub-ref"}]),
                _FakeResponse(data=[{"id": "sub-active", "abonnement": "ab1"}]),
                _FakeResponse(data=[{"id": "sub-latest"}]),
                _FakeResponse(data=[{"id": "sub-paid"}]),
                _FakeResponse(data=[{"id": "sub-1"}, {"id": "sub-2"}]),
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "sub-updated"}]),
            ],
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.get_abonnement("ab1")) == {"id": "ab1"}

    async def _fake_get_abonnement(_ab_id):
        return {"id": "ab1", "priorite": "3"}

    monkeypatch.setattr(supabase_request, "get_abonnement", _fake_get_abonnement)
    assert asyncio.run(supabase_request.get_souscription_by_reference("ref-1")) == {"id": "sub-ref"}

    active = asyncio.run(supabase_request.get_user_abonnement("u1"))
    assert active["id"] == "sub-active"
    assert active["priorite"] == 3

    assert asyncio.run(supabase_request.get_latest_user_souscription("u1")) == {"id": "sub-latest"}
    assert asyncio.run(supabase_request.get_latest_user_paid_subscription("u1")) == {"id": "sub-paid"}
    assert asyncio.run(supabase_request.list_user_souscriptions("u1", limit=999)) == [{"id": "sub-1"}, {"id": "sub-2"}]
    assert asyncio.run(supabase_request.update_souscription_row("sub-1", {"payment_status": "cancelled"})) == {"id": "sub-updated"}


def test_get_user_abonnement_orders_by_payment_end_date_desc(monkeypatch):
    # Without an explicit order, postgrest's row order when more than one
    # row matches (e.g. a legacy row with no stripe_subscription_id
    # alongside a real one created later, both still "active") is
    # unordered/arbitrary -- the query must request a deterministic order
    # so the currently governing row is the one returned.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[{"id": "sub-active", "abonnement": None}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.get_user_abonnement("u1"))
    assert result["id"] == "sub-active"
    assert _event_args(fake_client.events, supabase_request.SUPABASE_SOUSCRIPTION_TABLE, "order") == ("payment_end_date",)
    order_kwargs = next(
        kwargs for table, method, _args, kwargs in fake_client.events
        if table == supabase_request.SUPABASE_SOUSCRIPTION_TABLE and method == "order"
    )
    assert order_kwargs == {"desc": True}


def test_get_user_abonnement_falls_back_to_priority_one_on_error(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_SOUSCRIPTION_TABLE: [_FakeResponse(data=[{"id": "sub-e", "abonnement": "ab-x"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _boom(_ab_id):
        raise RuntimeError("lookup failed")

    monkeypatch.setattr(supabase_request, "get_abonnement", _boom)
    row = asyncio.run(supabase_request.get_user_abonnement("u1"))
    assert row["priorite"] == 1


def test_update_job_record_and_get_job_record_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.update_job_record("", {"status": "x"})) is None

    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_JOBS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "job-1", "status": "done"}]),
                _FakeResponse(data=[{"id": "job-1", "user_id": "u1"}]),
                _FakeResponse(data=[{"id": "job-1", "user_id": "u1"}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    updated = asyncio.run(supabase_request.update_job_record("job-1", {"status": "done"}))
    assert updated == {"id": "job-1", "status": "done"}

    row_any = asyncio.run(supabase_request.get_job_record("job-1"))
    row_scoped = asyncio.run(supabase_request.get_job_record("job-1", user_id="u1"))
    assert row_any == {"id": "job-1", "user_id": "u1"}
    assert row_scoped == {"id": "job-1", "user_id": "u1"}


def test_get_latest_job_record_by_project_match_and_none(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_JOBS_TABLE: [
                _FakeResponse(data=[
                    {"id": "j0", "job_data": {"project_id": "p-x"}},
                    {"id": "j1", "job_data": {"project_id": "p-1"}},
                ]),
                _FakeResponse(data=[{"id": "j2", "job_data": {"project_id": "other"}}]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    found = asyncio.run(supabase_request.get_latest_job_record_by_project("p-1", "u1"))
    not_found = asyncio.run(supabase_request.get_latest_job_record_by_project("p-missing", "u1"))

    assert found == {"id": "j1", "job_data": {"project_id": "p-1"}}
    assert not_found is None


def test_append_and_list_job_logs_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_JOB_LOGS_TABLE: [
                _FakeResponse(data=[]),
                _FakeResponse(data=[{"id": "l1", "level": "WARN"}], count=1),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    asyncio.run(supabase_request.append_job_log("job-1", "warn", "hello", {"step": 1}))
    rows = asyncio.run(supabase_request.list_job_logs("job-1", limit=9999))

    assert rows == [{"id": "l1", "level": "WARN"}]
    insert_payload = _event_args(fake_client.events, supabase_request.SUPABASE_JOB_LOGS_TABLE, "insert")[0]
    assert insert_payload["level"] == "WARN"
    assert insert_payload["metadata"] == {"step": 1}
    assert _event_args(fake_client.events, supabase_request.SUPABASE_JOB_LOGS_TABLE, "limit") == (1000,)


def test_list_recoverable_jobs_default_status_and_limit(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_JOBS_TABLE: [_FakeResponse(data=[{"id": "j-recover"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows = asyncio.run(supabase_request.list_recoverable_jobs("reels", limit=0))
    assert rows == [{"id": "j-recover"}]
    assert _event_args(fake_client.events, supabase_request.SUPABASE_JOBS_TABLE, "in_") == (
        "status", ["queued", "processing", "retry_wait"]
    )
    assert _event_args(fake_client.events, supabase_request.SUPABASE_JOBS_TABLE, "limit") == (1,)


def test_upsert_user_data_credits_existing_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1", "credit": 13.0}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing(_uid):
        return {
            "user_id": "u1",
            "credit": 10,
            "credit_debt": 5,
            "stockage": 2.0,
            "credit_max": 10,
            "stockage_max": 2.0,
        }

    bank_entry = types.SimpleNamespace(calls=[])

    async def _bank(**kwargs):
        bank_entry.calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", _bank)

    result = asyncio.run(
        supabase_request.upsert_user_data_credits(
            "u1",
            credit_delta=8,
            storage_delta=1.0,
            update_credit_max=True,
            update_stockage_max=True,
            operation_type="subscription",
            operation_id="sub-1",
        )
    )

    assert result["user_id"] == "u1"
    assert bank_entry.calls
    assert bank_entry.calls[0]["direction"] == "debt_payment"
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")[0]
    assert payload["credit"] == 13.0
    assert payload["credit_debt"] == 0.0
    assert payload["stockage"] == 3.0
    assert payload["credit_max"] == 18.0
    assert payload["stockage_max"] == 3.0


def test_upsert_user_data_credits_caps_credit_max_when_needed(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u2", "credit": 7.0}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing(_uid):
        return {
            "user_id": "u2",
            "credit": 5,
            "credit_debt": 0,
            "stockage": 1.0,
            "credit_max": 3,
            "stockage_max": 1.0,
        }

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", lambda **_kwargs: None)

    asyncio.run(
        supabase_request.upsert_user_data_credits(
            "u2",
            credit_delta=2,
            storage_delta=0.0,
            update_credit_max=False,
            update_stockage_max=False,
        )
    )
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")[0]
    assert payload["credit"] == 7.0
    assert payload["credit_max"] == 7.0


def test_upsert_user_data_credits_create_user_path(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _missing(_uid):
        return None

    monkeypatch.setattr(supabase_request, "get_user_data", _missing)
    created = asyncio.run(supabase_request.upsert_user_data_credits("u3", 2.2, storage_delta=1.5))
    assert created["user_id"] == "u3"
    assert created["credit"] == 3
    assert created["stockage"] == 1.5


def test_set_user_data_balance_existing_and_insert_paths(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_USER_DATA_TABLE: [
                _FakeResponse(data=[{"user_id": "u1", "credit": 7.0}]),
                _FakeResponse(data=[]),
            ]
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    async def _existing(_uid):
        return {
            "user_id": "u1",
            "credit": 1,
            "credit_debt": 3,
            "stockage": 2.0,
            "credit_max": 2,
            "stockage_max": 2.0,
        }

    bank_calls = []

    async def _bank(**kwargs):
        bank_calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", _bank)
    updated = asyncio.run(supabase_request.set_user_data_balance("u1", credit=10, storage=3.0))
    assert updated["user_id"] == "u1"
    assert bank_calls
    assert bank_calls[0]["direction"] == "debt_payment"
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")[0]
    assert payload["credit"] == 7.0
    assert payload["credit_debt"] == 0.0
    assert payload["stockage"] == 3.0
    assert payload["credit_max"] == 7.0
    assert payload["stockage_max"] == 2.0

    async def _missing(_uid):
        return None

    monkeypatch.setattr(supabase_request, "get_user_data", _missing)
    inserted = asyncio.run(supabase_request.set_user_data_balance("u9", credit=4, storage=1.0))
    assert inserted["user_id"] == "u9"
    assert inserted["credit"] == 4


def test_deduct_user_credits_debt_path_and_storage_never_blocks(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    # Security hardening (audit finding C7) caps how much debt an account can
    # accrue; the default ceiling is 0, which would reject this test's
    # debt-accrual scenario outright, so raise it high enough for the
    # scenario below to exercise the "allowed, bounded debt" path.
    monkeypatch.setattr(supabase_request, "MAX_CREDIT_DEBT", 10.0)

    async def _existing_for_debt(_uid):
        return {
            "user_id": "u1",
            "credit": 2,
            "credit_debt": 1,
            "stockage": 0.0,
            "stockage_max": 10.0,
        }

    bank_calls = []

    async def _bank(**kwargs):
        bank_calls.append(kwargs)
        return kwargs

    monkeypatch.setattr(supabase_request, "get_user_data", _existing_for_debt)
    monkeypatch.setattr(supabase_request, "insert_user_credit_bank_entry", _bank)
    assert asyncio.run(supabase_request.deduct_user_credits("u1", credits=5, storage_delta=0.0)) is True
    assert bank_calls and bank_calls[0]["direction"] == "debt_increase"

    # Storage is no longer a quota that can block a deduction (see
    # retention_config.py / the storage-quota removal) -- a large negative
    # storage_delta must settle fine as long as the credit side is within
    # its own debt ceiling. Fresh fake_client: the one above already
    # consumed its single queued update response.
    fake_client_2 = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client_2)

    async def _existing_large_storage_delta(_uid):
        return {
            "user_id": "u1",
            "credit": 100,
            "credit_debt": 0,
            "stockage": 0.0,
            "stockage_max": 10.0,
        }

    monkeypatch.setattr(supabase_request, "get_user_data", _existing_large_storage_delta)
    assert asyncio.run(supabase_request.deduct_user_credits("u1", credits=1, storage_delta=-100.0)) is True


def test_insert_credit_bank_entry_and_user_history(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_USER_CREDIT_BANK_TABLE: [_FakeResponse(data=[])],
            supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [_FakeResponse(data=[])],
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    entry = asyncio.run(
        supabase_request.insert_user_credit_bank_entry(
            user_id="u1",
            direction="  DEBT_PAYMENT  ",
            amount=-5,
            debt_balance_after=-1,
            operation_type="subscription",
            operation_id="op-1",
            metadata={"x": 1},
        )
    )
    history = asyncio.run(
        supabase_request.insert_user_data_history(
            user_id="u1",
            credit=2.2,
            storage=0.5,
            operation="output",
            operation_type="captions",
            operation_id="h-1",
        )
    )

    assert entry["direction"] == "debt_payment"
    assert entry["amount"] == 0.0
    assert entry["debt_balance_after"] == 0.0
    assert history["credit"] == 3
    assert history["operation_id"] == "h-1"


def test_upsert_user_data_history_entry_inserts_when_no_existing_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [
                _FakeResponse(data=[]),  # the merge lookup finds nothing
                _FakeResponse(data=[{"id": "h-new", "credit": 3, "storage": 0.0, "operation_type": "generation_reel"}]),
            ],
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.upsert_user_data_history_entry(
            user_id="u1", credit=2.2, storage=0.0, operation="output",
            operation_type="generation_reel", operation_id="job-1",
        )
    )

    assert result["id"] == "h-new"
    assert result["credit"] == 3
    assert _event_count(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "insert") == 1
    assert _event_count(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "update") == 0


def test_upsert_user_data_history_entry_merges_into_existing_row_and_keeps_operation_type(monkeypatch):
    # The second (sub-)charge for the same job_id must sum into the
    # existing row's credit/storage rather than create a new row, and
    # must never overwrite the operation_type the row was created with --
    # "la nature de l'operation reste l'operation principale".
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {
            supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [
                _FakeResponse(data=[{"id": "h-1", "credit": 3, "storage": 0.1, "operation_type": "generation_reel", "operation": "output"}]),
                _FakeResponse(data=[{"id": "h-1", "credit": 5, "storage": 0.1, "operation_type": "generation_reel", "operation": "output"}]),
            ],
        }
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.upsert_user_data_history_entry(
            user_id="u1", credit=1.6, storage=0.0, operation="output",
            operation_type="sous_titre", operation_id="job-1",
        )
    )

    assert result["id"] == "h-1"
    update_args = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "update")
    # existing credit (3) + ceil(1.6) == 5, never the child's own operation_type.
    assert update_args[0] == {"credit": 5, "storage": 0.1}
    assert _event_count(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "insert") == 0


def test_upsert_user_data_history_entry_falls_back_to_insert_when_operation_id_empty(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [_FakeResponse(data=[{"id": "h-no-key"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(
        supabase_request.upsert_user_data_history_entry(
            user_id="u1", credit=1.0, storage=0.0, operation="output",
            operation_type="generation_reel", operation_id="",
        )
    )

    assert result["id"] == "h-no-key"
    # No merge lookup at all -- straight to insert, same as insert_user_data_history itself.
    assert _event_count(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "select") == 0
    assert _event_count(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "insert") == 1


def test_get_user_data_history_query_and_pagination(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE: [_FakeResponse(data=[{"id": "h1"}], count=4)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows, total = asyncio.run(supabase_request.get_user_data_history("u1", page=0, page_size=999))
    assert rows == [{"id": "h1"}]
    assert total == 4
    assert _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_HISTORY_TABLE, "range") == (0, 99)


def test_get_user_data_history_returns_empty_for_missing_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    rows, total = asyncio.run(supabase_request.get_user_data_history(""))
    assert rows == []
    assert total == 0


# --------------------------------------------------------------------------
# Referral program
# --------------------------------------------------------------------------

def test_generate_referral_code_has_expected_length_and_alphabet(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    code = supabase_request._generate_referral_code()
    assert len(code) == supabase_request._REFERRAL_CODE_LENGTH
    assert all(c in supabase_request._REFERRAL_CODE_ALPHABET for c in code)
    # No ambiguous characters -- these must never appear in a generated code.
    assert not any(c in code for c in "0O1IL")


def test_get_or_create_referral_code_returns_existing_without_insert(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REFERRAL_CODES_TABLE: [_FakeResponse(data=[{"code": "ABC1234"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    code = asyncio.run(supabase_request.get_or_create_referral_code("u1"))
    assert code == "ABC1234"
    assert _event_count(fake_client.events, supabase_request.SUPABASE_REFERRAL_CODES_TABLE, "insert") == 0


def test_get_or_create_referral_code_generates_when_missing(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_REFERRAL_CODES_TABLE: [
            _FakeResponse(data=[]),  # the initial get_referral_code lookup: none yet
            _FakeResponse(data=[{"code": "ZZZ9999"}]),  # the insert
        ]
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    code = asyncio.run(supabase_request.get_or_create_referral_code("u1"))
    assert code == "ZZZ9999"


def test_get_or_create_referral_code_retries_on_collision(monkeypatch):
    # A unique-constraint conflict on insert (code collision, or a
    # concurrent request already created this exact user's code) must be
    # retried rather than raised -- re-reading first in case it was this
    # user's own code that just got created concurrently.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    from postgrest.exceptions import APIError

    class _RetryOnceClient:
        def __init__(self):
            self.insert_attempts = 0

        async def _get_lookup(self):
            return _FakeResponse(data=[])

        def table(self, table_name):
            attempts = self

            class _Query:
                def select(self, *a, **k):
                    return self

                def eq(self, *a, **k):
                    return self

                def insert(self, *a, **k):
                    attempts.insert_attempts += 1
                    self._is_insert = True
                    return self

                def limit(self, *a, **k):
                    return self

                async def execute(self):
                    if getattr(self, "_is_insert", False) and attempts.insert_attempts == 1:
                        raise APIError({"message": "duplicate key", "code": "23505", "hint": None, "details": None})
                    if getattr(self, "_is_insert", False):
                        return _FakeResponse(data=[{"code": "RETRY01"}])
                    return _FakeResponse(data=[])

            return _Query()

    fake_client = _RetryOnceClient()
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    code = asyncio.run(supabase_request.get_or_create_referral_code("u1"))
    assert code == "RETRY01"
    assert fake_client.insert_attempts == 2


def test_get_referral_code_owner_case_insensitive_lookup(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REFERRAL_CODES_TABLE: [_FakeResponse(data=[{"user_id": "referrer-1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    owner = asyncio.run(supabase_request.get_referral_code_owner("abc1234"))
    assert owner == "referrer-1"
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REFERRAL_CODES_TABLE, "ilike") == ("code", "abc1234")


def test_get_referral_code_owner_returns_none_for_empty_code(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.get_referral_code_owner("")) is None


def test_insert_referral_creates_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REFERRALS_TABLE: [_FakeResponse(data=[{"id": "ref-1", "referred_user_id": "u2"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row, created = asyncio.run(supabase_request.insert_referral("u1", "u2", "ABC1234"))
    assert created is True
    assert row["id"] == "ref-1"


def test_insert_referral_is_idempotent_on_conflict(monkeypatch):
    # A second association attempt for an already-referred user must
    # never raise -- it returns the EXISTING row with created=False, so
    # the caller treats it as "no-op", never granting a second bonus.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    from postgrest.exceptions import APIError

    class _ConflictThenLookupClient:
        def table(self, table_name):
            class _Query:
                def insert(self, *a, **k):
                    self._is_insert = True
                    return self

                def select(self, *a, **k):
                    return self

                def eq(self, *a, **k):
                    return self

                def limit(self, *a, **k):
                    return self

                async def execute(self):
                    if getattr(self, "_is_insert", False):
                        raise APIError({"message": "duplicate key", "code": "23505", "hint": None, "details": None})
                    return _FakeResponse(data=[{"id": "existing-ref", "referred_user_id": "u2"}])

            return _Query()

    _patch_get_client(monkeypatch, supabase_request, _ConflictThenLookupClient())

    row, created = asyncio.run(supabase_request.insert_referral("u1", "u2", "ABC1234"))
    assert created is False
    assert row["id"] == "existing-ref"


def test_claim_referral_subscription_reward_succeeds_once(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REFERRALS_TABLE: [_FakeResponse(data=[{"id": "ref-1", "status": "rewarded"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.claim_referral_subscription_reward("ref-1", "month", "sous-1"))
    assert row["status"] == "rewarded"
    assert _event_args(fake_client.events, supabase_request.SUPABASE_REFERRALS_TABLE, "is_") == ("subscription_reward_granted_at", "null")


def test_claim_referral_subscription_reward_idempotent_when_already_claimed(monkeypatch):
    # The conditional UPDATE affects 0 rows once subscription_reward_granted_at
    # is no longer null -- the fake client models that by returning no rows.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REFERRALS_TABLE: [_FakeResponse(data=[])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.claim_referral_subscription_reward("ref-1", "month", "sous-1"))
    assert row is None


def test_invalidate_referral_sets_status_and_reason(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_REFERRALS_TABLE: [_FakeResponse(data=[{"id": "ref-1", "status": "invalid"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.invalidate_referral("ref-1", "self_referral_suspected"))
    assert row["status"] == "invalid"
    update_args = _event_args(fake_client.events, supabase_request.SUPABASE_REFERRALS_TABLE, "update")
    assert update_args[0]["status"] == "invalid"
    assert update_args[0]["invalidated_reason"] == "self_referral_suspected"


def test_get_auth_user_created_at_returns_parsed_datetime(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    class _FakeAdmin:
        async def get_user_by_id(self, user_id):
            return types.SimpleNamespace(user=types.SimpleNamespace(created_at="2026-01-15T10:00:00+00:00"))

    class _FakeAuth:
        admin = _FakeAdmin()

    class _FakeClientWithAuth:
        auth = _FakeAuth()

    _patch_get_client(monkeypatch, supabase_request, _FakeClientWithAuth())

    result = asyncio.run(supabase_request.get_auth_user_created_at("u1"))
    assert result == datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


def test_get_auth_user_created_at_returns_none_on_failure(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    class _FakeAdmin:
        async def get_user_by_id(self, user_id):
            raise RuntimeError("not found")

    class _FakeAuth:
        admin = _FakeAdmin()

    class _FakeClientWithAuth:
        auth = _FakeAuth()

    _patch_get_client(monkeypatch, supabase_request, _FakeClientWithAuth())

    assert asyncio.run(supabase_request.get_auth_user_created_at("u1")) is None


# --------------------------------------------------------------------------
# Promotional credits
# --------------------------------------------------------------------------

def test_insert_promotional_credit_batch_sets_expiry_and_touches_user_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1", "credit": 0.0}])],
        supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE: [_FakeResponse(data=[{"id": "batch-1"}])],
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    before = datetime.now(timezone.utc)
    row = asyncio.run(
        supabase_request.insert_promotional_credit_batch(
            "u1", 50.0, "REFERRAL_SIGNUP", expiration_days=60, source_reference="ref-1",
        )
    )
    assert row["id"] == "batch-1"
    insert_args = _event_args(fake_client.events, supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE, "insert")
    payload = insert_args[0]
    assert payload["amount_initial"] == 50.0
    assert payload["amount_remaining"] == 50.0
    assert payload["source"] == "REFERRAL_SIGNUP"
    assert payload["source_reference"] == "ref-1"
    expires_at = datetime.fromisoformat(payload["expires_at"])
    assert (expires_at - before).days in (59, 60)  # ~60 days out, defensive against test timing
    assert payload["tier"] == supabase_request.CREDIT_BATCH_TIER_PROMOTIONAL  # default


def test_insert_promotional_credit_batch_accepts_purchased_tier(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1", "credit": 0.0}])],
        supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE: [_FakeResponse(data=[{"id": "batch-2"}])],
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    asyncio.run(
        supabase_request.insert_promotional_credit_batch(
            "u1", 200.0, "CREDIT_PURCHASE", expiration_days=365, source_reference="sous-1",
            tier=supabase_request.CREDIT_BATCH_TIER_PURCHASED,
        )
    )
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE, "insert")[0]
    assert payload["tier"] == supabase_request.CREDIT_BATCH_TIER_PURCHASED


def test_zero_subscription_credit_zeroes_credit_keeps_storage(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    async def _existing(_uid):
        return {"user_id": "u1", "credit": 150.0, "stockage": 5.0, "stockage_max": 20.0}

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    balance_mock = AsyncMock(return_value={"user_id": "u1"})
    monkeypatch.setattr(supabase_request, "set_user_data_balance", balance_mock)
    history_mock = AsyncMock()
    monkeypatch.setattr(supabase_request, "insert_user_data_history", history_mock)

    asyncio.run(supabase_request.zero_subscription_credit("u1", operation_id="in_123"))

    balance_mock.assert_awaited_once_with(
        user_id="u1", credit=0.0, storage=5.0, credit_max=0.0, storage_max=20.0,
        operation_type="subscription_payment_failed", operation_id="in_123",
    )
    history_mock.assert_awaited_once_with(
        user_id="u1", credit=150.0, storage=0.0, operation="output",
        operation_type="subscription_payment_failed", operation_id="in_123",
    )


def test_zero_subscription_credit_noop_without_existing_user_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    async def _missing(_uid):
        return None

    monkeypatch.setattr(supabase_request, "get_user_data", _missing)
    balance_mock = AsyncMock()
    monkeypatch.setattr(supabase_request, "set_user_data_balance", balance_mock)

    asyncio.run(supabase_request.zero_subscription_credit("u1"))

    balance_mock.assert_not_awaited()


def test_set_user_max_daily_publications_updates_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1", "credit": 0.0}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    asyncio.run(supabase_request.set_user_max_daily_publications("u1", 5))

    update_payloads = [
        args[0] for table, method, args, _kwargs in fake_client.events
        if table == supabase_request.SUPABASE_USER_DATA_TABLE and method == "update"
    ]
    assert any(p.get("max_daily_publications") == 5 for p in update_payloads)


def test_consume_publish_quota_allows_unlimited_when_max_is_zero(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    async def _existing(_uid):
        return {"user_id": "u1", "max_daily_publications": 0, "publications_today": 999}

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.consume_publish_quota("u1", 3))

    assert result["allowed"] is True
    assert result["max_daily"] == 0


def test_consume_publish_quota_blocks_once_daily_cap_reached(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    today = datetime.now(timezone.utc).date().isoformat()

    async def _existing(_uid):
        return {"user_id": "u1", "max_daily_publications": 3, "publications_today": 3, "publications_count_date": today}

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)

    result = asyncio.run(supabase_request.consume_publish_quota("u1", 1))

    assert result["allowed"] is False
    assert result["max_daily"] == 3
    assert result["used_today"] == 3
    assert result["resets_at"] is not None
    # resets at the next UTC midnight -- strictly in the future.
    resets_at = datetime.fromisoformat(result["resets_at"])
    assert resets_at > datetime.now(timezone.utc)


def test_consume_publish_quota_lazily_resets_on_new_day(monkeypatch):
    # A stale publications_count_date (yesterday or earlier) must be
    # treated as a fresh day -- no scheduled reset job exists.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    async def _existing(_uid):
        return {"user_id": "u1", "max_daily_publications": 2, "publications_today": 2, "publications_count_date": "2000-01-01"}

    monkeypatch.setattr(supabase_request, "get_user_data", _existing)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[{"user_id": "u1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.consume_publish_quota("u1", 1))

    assert result["allowed"] is True
    assert result["used_today"] == 1
    payload = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")[0]
    assert payload["publications_today"] == 1


def test_consume_publish_quota_allows_when_no_existing_user_data(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)

    async def _missing(_uid):
        return None

    monkeypatch.setattr(supabase_request, "get_user_data", _missing)

    result = asyncio.run(supabase_request.consume_publish_quota("u1", 5))

    assert result["allowed"] is True


def test_list_active_promotional_credit_batches_filters_and_orders(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    rows = [{"id": "b1", "expires_at": "2026-02-01T00:00:00+00:00"}]
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE: [_FakeResponse(data=rows)]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.list_active_promotional_credit_batches("u1"))
    assert result == rows
    events = fake_client.events
    assert _event_args(events, supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE, "is_") == ("revoked_at", "null")
    assert _event_count(events, supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE, "gt") == 2


def test_list_active_promotional_credit_batches_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.list_active_promotional_credit_batches("")) == []


def test_revoke_promotional_credit_batches_by_source_reference_zeroes_remaining(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient({
        supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE: [
            _FakeResponse(data=[{"id": "b1", "amount_remaining": 0}])
        ],
    })
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    count = asyncio.run(
        supabase_request.revoke_promotional_credit_batches_by_source_reference("sous-1", "chargeback")
    )
    assert count == 1
    update_args = _event_args(fake_client.events, supabase_request.SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE, "update")
    assert update_args[0]["amount_remaining"] == 0
    assert update_args[0]["revoked_reason"] == "chargeback"


def test_revoke_promotional_credit_batches_empty_source_reference_is_noop(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.revoke_promotional_credit_batches_by_source_reference("", "x")) == 0


# --------------------------------------------------------------------------
# deduct_user_credits -- promotional-credits-first (FEFO) consumption
# --------------------------------------------------------------------------

def test_deduct_user_credits_consumes_promo_before_standard(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[
            {"user_id": "u1", "credit": 1000.0, "stockage": 0.0, "stockage_max": 0.0, "credit_debt": 0.0},
        ])]},
        rpc_response_map={
            "consume_promotional_credits": _FakeResponse(data={"consumed": 50.0, "batches": [{"id": "b1", "amount": 50.0}]}),
        },
    )
    fake_client.response_map[supabase_request.SUPABASE_USER_DATA_TABLE].append(
        _FakeResponse(data=[{"user_id": "u1", "credit": 950.0}])
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", credits=100.0))
    assert result is True
    # Only the 50 left after promo (100 - 50) should hit the standard balance.
    update_args = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")
    assert update_args[0]["credit"] == 950.0  # 1000 - 50 remaining, not 1000 - 100


def test_deduct_user_credits_fully_covered_by_promo_skips_standard_debit(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [
            _FakeResponse(data=[{"user_id": "u1", "credit": 1000.0, "stockage": 0.0, "stockage_max": 0.0, "credit_debt": 0.0}]),
            _FakeResponse(data=[{"user_id": "u1", "credit": 1000.0}]),
        ]},
        rpc_response_map={
            "consume_promotional_credits": _FakeResponse(data={"consumed": 100.0, "batches": [{"id": "b1", "amount": 100.0}]}),
        },
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", credits=100.0))
    assert result is True
    update_args = _event_args(fake_client.events, supabase_request.SUPABASE_USER_DATA_TABLE, "update")
    assert update_args[0]["credit"] == 1000.0  # untouched -- promo covered the whole amount


def test_deduct_user_credits_restores_promo_when_standard_side_infeasible(monkeypatch):
    # Debt cap exceeded on the standard-credit remainder must restore
    # whatever promo credits were already drawn -- the whole deduction is
    # all-or-nothing.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    monkeypatch.setattr(supabase_request, "MAX_CREDIT_DEBT", 0.0)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [
            _FakeResponse(data=[{"user_id": "u1", "credit": 10.0, "stockage": 0.0, "stockage_max": 0.0, "credit_debt": 0.0}]),
        ]},
        rpc_response_map={
            "consume_promotional_credits": _FakeResponse(data={"consumed": 20.0, "batches": [{"id": "b1", "amount": 20.0}]}),
            "restore_promotional_credits": _FakeResponse(data=None),
        },
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    # Needs 1000 total; only 20 promo + 10 standard available, and debt is disallowed.
    result = asyncio.run(supabase_request.deduct_user_credits("u1", credits=1000.0))
    assert result is False
    restore_calls = [e for e in fake_client.events if e[0] == "rpc" and e[1] == "restore_promotional_credits"]
    assert len(restore_calls) == 1
    assert restore_calls[0][3]["p_batches"] == [{"id": "b1", "amount": 20.0}]


def test_deduct_user_credits_restores_promo_when_no_user_data_row(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [_FakeResponse(data=[])]},
        rpc_response_map={
            "consume_promotional_credits": _FakeResponse(data={"consumed": 10.0, "batches": [{"id": "b1", "amount": 10.0}]}),
        },
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", credits=10.0))
    assert result is False
    restore_calls = [e for e in fake_client.events if e[0] == "rpc" and e[1] == "restore_promotional_credits"]
    assert len(restore_calls) == 1


def test_deduct_user_credits_zero_or_negative_amount_skips_promo_rpc(monkeypatch):
    # Storage-only deductions (credits=0.0) must not pay the promo-RPC
    # cost on every single call across the whole app.
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [
            _FakeResponse(data=[{"user_id": "u1", "credit": 10.0, "stockage": 5.0, "stockage_max": 100.0, "credit_debt": 0.0}]),
            _FakeResponse(data=[{"user_id": "u1", "credit": 10.0}]),
        ]},
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", credits=0.0, storage_delta=-1.0))
    assert result is True
    rpc_calls = [e for e in fake_client.events if e[0] == "rpc"]
    assert rpc_calls == []


def test_deduct_user_credits_retries_on_concurrent_standard_balance_conflict(monkeypatch):
    # Two concurrent deductions on the standard balance: the conditional
    # UPDATE (WHERE credit/stockage still match what was just read) loses
    # the race and affects 0 rows -- this must retry against the fresh
    # balance instead of silently dropping the deduction. (True
    # concurrency-safety for the PROMOTIONAL side comes from the
    # Postgres consume_promotional_credits function's row-level FOR
    # UPDATE lock, a single atomic transaction this fake-client unit test
    # can't exercise -- only a real-Postgres integration test could.)
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_USER_DATA_TABLE: [
            _FakeResponse(data=[{"user_id": "u1", "credit": 100.0, "stockage": 0.0, "stockage_max": 0.0, "credit_debt": 0.0}]),
            _FakeResponse(data=[]),  # conditional update loses the race (stale read)
            _FakeResponse(data=[{"user_id": "u1", "credit": 90.0, "stockage": 0.0, "stockage_max": 0.0, "credit_debt": 0.0}]),  # fresh read after a concurrent -10 debit
            _FakeResponse(data=[{"user_id": "u1", "credit": 80.0}]),  # this retry's update succeeds
        ]},
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.deduct_user_credits("u1", credits=10.0))
    assert result is True
    update_calls = [e for e in fake_client.events if e[0] == supabase_request.SUPABASE_USER_DATA_TABLE and e[1] == "update"]
    assert len(update_calls) == 2
    # The winning retry's update is against the fresh 90, not the stale 100.
    assert update_calls[1][2][0]["credit"] == 80.0


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

def test_insert_notification_builds_payload(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_NOTIFICATIONS_TABLE: [_FakeResponse(data=[{"id": "n1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(
        supabase_request.insert_notification("u1", "referral_signup_bonus", "Bienvenue !", "Tu as recu 50 credits.", {"amount": 50})
    )
    assert row["id"] == "n1"
    insert_args = _event_args(fake_client.events, supabase_request.SUPABASE_NOTIFICATIONS_TABLE, "insert")
    assert insert_args[0]["type"] == "referral_signup_bonus"
    assert insert_args[0]["data"] == {"amount": 50}


def test_list_notifications_returns_items_and_unread_count(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_NOTIFICATIONS_TABLE: [
            _FakeResponse(data=[{"id": "n1"}, {"id": "n2"}]),
            _FakeResponse(data=[{"id": "n1"}], count=1),
        ]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    items, unread_count = asyncio.run(supabase_request.list_notifications("u1", limit=20))
    assert items == [{"id": "n1"}, {"id": "n2"}]
    assert unread_count == 1


def test_list_notifications_empty_user_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    items, unread_count = asyncio.run(supabase_request.list_notifications(""))
    assert items == []
    assert unread_count == 0


def test_mark_notification_read_scopes_to_owner(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_NOTIFICATIONS_TABLE: [_FakeResponse(data=[{"id": "n1", "read_at": "now"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    row = asyncio.run(supabase_request.mark_notification_read("n1", "u1"))
    assert row["id"] == "n1"
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_NOTIFICATIONS_TABLE and method == "eq"]
    assert ("id", "n1") in eq_calls
    assert ("user_id", "u1") in eq_calls


def test_mark_all_notifications_read_returns_count(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_NOTIFICATIONS_TABLE: [_FakeResponse(data=[{"id": "n1"}, {"id": "n2"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    count = asyncio.run(supabase_request.mark_all_notifications_read("u1"))
    assert count == 2


def test_insert_media_asset_sends_fixed_policy_snapshot(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expires = datetime(2026, 1, 31, tzinfo=timezone.utc)
    row = asyncio.run(supabase_request.insert_media_asset(
        user_id="u1",
        content_kind=supabase_request.CONTENT_KIND_REEL,
        content_id="r1",
        media_type="produced",
        subscription_status_at_creation="active",
        retention_days=30,
        retention_started_at=started,
        retention_expires_at=expires,
        storage={
            "job_id": "job-1",
            "s3_bucket": "bucket",
            "s3_key": "key.mp4",
            "size_bytes": 4_000_000_000,
        },
        billing={
            "s3_storage_cost_per_gb_day": 0.0008,
            "retention_storage_cost_usd": 0.096,
            "retention_storage_credit_cost": 1.5,
        },
    ))
    assert row["id"] == "m1"
    insert_payload = _event_args(fake_client.events, supabase_request.SUPABASE_MEDIA_ASSETS_TABLE, "insert")[0]
    assert insert_payload["content_kind"] == "reel"
    assert insert_payload["media_type"] == "produced"
    assert insert_payload["retention_days"] == 30
    assert insert_payload["retention_started_at"] == started.isoformat()
    assert insert_payload["retention_expires_at"] == expires.isoformat()
    assert insert_payload["size_bytes"] == 4_000_000_000


def test_get_media_asset_by_content_requires_both_keys(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.get_media_asset_by_content("", "r1")) is None
    assert asyncio.run(supabase_request.get_media_asset_by_content("reel", "")) is None

    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)
    row = asyncio.run(supabase_request.get_media_asset_by_content("reel", "r1"))
    assert row["id"] == "m1"
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "eq"]
    assert ("content_kind", "reel") in eq_calls
    assert ("content_id", "r1") in eq_calls


def test_list_media_assets_due_for_expiration_filters_available_and_expired(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}, {"id": "m2"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows = asyncio.run(supabase_request.list_media_assets_due_for_expiration(limit=50))
    assert rows == [{"id": "m1"}, {"id": "m2"}]
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "eq"]
    assert ("media_status", "AVAILABLE") in eq_calls
    assert _event_args(fake_client.events, supabase_request.SUPABASE_MEDIA_ASSETS_TABLE, "limit") == (50,)


def test_mark_media_asset_expired_only_targets_available_rows(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.mark_media_asset_expired("m1")) is True
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_MEDIA_ASSETS_TABLE, "update")[0]
    assert update_payload["media_status"] == "EXPIRED"
    assert "media_deleted_at" in update_payload
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "eq"]
    assert ("media_status", "AVAILABLE") in eq_calls


def test_mark_media_asset_expired_empty_id_is_noop(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.mark_media_asset_expired("")) is False


def test_mark_media_asset_missing(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.mark_media_asset_missing("m1")) is True
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_MEDIA_ASSETS_TABLE, "update")[0]
    assert update_payload["media_status"] == "MISSING"


def test_mark_media_asset_deleted(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.mark_media_asset_deleted("m1")) is True
    update_payload = _event_args(fake_client.events, supabase_request.SUPABASE_MEDIA_ASSETS_TABLE, "update")[0]
    assert update_payload["media_status"] == "DELETED"
    assert "media_deleted_at" in update_payload


def test_list_media_assets_by_content_ids_builds_map_keyed_by_content_id(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[
            {"content_id": "r1", "media_status": "AVAILABLE"},
            {"content_id": "r2", "media_status": "EXPIRED"},
        ])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    result = asyncio.run(supabase_request.list_media_assets_by_content_ids("reel", ["r1", "r2", "r1"]))
    assert result["r1"]["media_status"] == "AVAILABLE"
    assert result["r2"]["media_status"] == "EXPIRED"
    in_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "in_"]
    assert in_calls == [("content_id", ["r1", "r2"])]


def test_list_media_assets_by_content_ids_empty_without_ids(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    assert asyncio.run(supabase_request.list_media_assets_by_content_ids("reel", [])) == {}
    assert asyncio.run(supabase_request.list_media_assets_by_content_ids("", ["r1"])) == {}


def test_list_produced_media_due_for_notification_excludes_source_and_notified(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    rows = asyncio.run(supabase_request.list_produced_media_due_for_notification(limit=10))
    assert rows == [{"id": "m1"}]
    eq_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "eq"]
    assert ("media_status", "AVAILABLE") in eq_calls
    assert ("media_type", "produced") in eq_calls
    is_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "is_"]
    assert ("notified_before_expiry_at", "null") in is_calls


def test_mark_media_asset_notified_is_idempotent_guarded(monkeypatch):
    supabase_request = _import_supabase_request_with_stubs(monkeypatch)
    fake_client = _FakeClient(
        {supabase_request.SUPABASE_MEDIA_ASSETS_TABLE: [_FakeResponse(data=[{"id": "m1"}])]}
    )
    _patch_get_client(monkeypatch, supabase_request, fake_client)

    assert asyncio.run(supabase_request.mark_media_asset_notified("m1")) is True
    is_calls = [args for table, method, args, _ in fake_client.events if table == supabase_request.SUPABASE_MEDIA_ASSETS_TABLE and method == "is_"]
    assert ("notified_before_expiry_at", "null") in is_calls

    assert asyncio.run(supabase_request.mark_media_asset_notified("")) is False




