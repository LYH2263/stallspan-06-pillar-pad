"""端到端：API 入口校验、提交后保留、重分按新值、旧快照不回刷。"""
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.models import AllocationRun
from app.services.seed import seed_if_empty

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

_seeded = False


def _db():
    global _seeded
    s = TestingSessionLocal()
    if not _seeded:
        seed_if_empty(s)
        _seeded = True
    return s


def _override():
    s = _db()
    try:
        yield s
    finally:
        s.close()


app.dependency_overrides[get_db] = _override
# 不进入 with，避免触发连 PostgreSQL 的 lifespan；表已在 sqlite 上建好
client = TestClient(app)


def _snapshot(run_id: int) -> dict:
    with TestingSessionLocal() as s:
        row = s.get(AllocationRun, run_id)
        return json.loads(row.result_json)


def test_pillars_list_carries_seed_clearance():
    rows = client.get("/api/pillars").json()
    assert len(rows) == 2
    assert all(r["clearance_m"] == 0.3 for r in rows)


def test_negative_clearance_rejected_and_everything_stays():
    # 先跑一次，记下 0.3 快照
    first = client.post("/api/allocate/run?segment_id=1").json()
    run_id = first["id"]
    before = client.get("/api/pillars").json()

    res = client.put("/api/pillars/1", json={"clearance_m": -0.3})
    assert res.status_code == 422  # 入口直接打回

    after = client.get("/api/pillars").json()
    assert after == before  # 列表停在改前
    snap = _snapshot(run_id)
    # 旧运行快照不被新外扩回刷（此处连新运行都不该生成）
    assert [(z["start_m"], z["end_m"]) for z in snap["blocked_zones"]] == \
        [(9.45, 10.55), (19.45, 20.55)]
    with TestingSessionLocal() as s:
        assert s.query(AllocationRun).count() == 1


def test_blocked_zones_endpoint_matches_engine():
    data = client.get("/api/pillars/blocked-zones?segment_id=1").json()
    assert [(z["start_m"], z["end_m"]) for z in data["blocked_zones"]] == \
        [(9.45, 10.55), (19.45, 20.55)]
    core = data["blocked_zones"][0]["pillars"][0]
    assert (core["core_start_m"], core["core_end_m"]) == (9.75, 10.25)
    assert core["clearance_m"] == 0.3


def test_seed_wide_stall_rejected_at_03_and_reason_wording():
    r = client.post("/api/allocate/run?segment_id=1").json()
    names = [p["vendor_name"] for p in r["placements"]]
    assert "巨型舞台车" not in names
    rej = [x for x in r["rejected"] if x["vendor_name"] == "巨型舞台车"]
    assert len(rej) == 1
    assert rej[0]["reason"].startswith("跨柱类")
    for banned in ("供电", "净距", "应急"):
        assert banned not in rej[0]["reason"]
    # 图上柱侧空白端点 = 引擎禁入端点
    assert [(z["start_m"], z["end_m"]) for z in r["blocked_zones"]] == \
        [(9.45, 10.55), (19.45, 20.55)]


def test_zero_clearance_fits_like_green_shed():
    assert client.put("/api/pillars/1", json={"clearance_m": 0}).status_code == 200
    assert client.put("/api/pillars/2", json={"clearance_m": 0}).status_code == 200
    r = client.post("/api/allocate/run?segment_id=1").json()
    assert "巨型舞台车" in [p["vendor_name"] for p in r["placements"]]
    assert [(z["start_m"], z["end_m"]) for z in r["blocked_zones"]] == \
        [(9.75, 10.25), (19.75, 20.25)]


def test_old_snapshot_not_backfilled_after_reclearance():
    # 当前外扩 0；跑一次得到 0 快照
    r0 = client.post("/api/allocate/run?segment_id=1").json()
    id0 = r0["id"]
    # 改回 0.3 再跑
    client.put("/api/pillars/1", json={"clearance_m": 0.3})
    client.put("/api/pillars/2", json={"clearance_m": 0.3})
    r1 = client.post("/api/allocate/run?segment_id=1").json()
    assert r1["id"] != id0
    old = _snapshot(id0)
    # 旧快照仍是 0 外扩端点，不被回刷
    assert [(z["start_m"], z["end_m"]) for z in old["blocked_zones"]] == \
        [(9.75, 10.25), (19.75, 20.25)]
    assert [(z["start_m"], z["end_m"]) for z in r1["blocked_zones"]] == \
        [(9.45, 10.55), (19.45, 20.55)]


def test_resubmit_persists_across_relist():
    assert client.put("/api/pillars/1", json={"clearance_m": 0.8}).status_code == 200
    rows = client.get("/api/pillars").json()
    assert rows[0]["clearance_m"] == 0.8
