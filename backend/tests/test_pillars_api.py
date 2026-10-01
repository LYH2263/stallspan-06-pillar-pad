import os

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(os.path.dirname(__file__), "test_pillars_api.db")
os.environ["SEED_ON_EMPTY"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
    if os.path.exists(db_path):
        os.remove(db_path)
    with TestClient(app) as c:
        yield c
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture(autouse=True)
def reset_setbacks(client):
    # 每个用例前把两柱外扩复位到种子值 0.3，保证用例互不依赖
    for p in client.get("/api/pillars").json():
        client.put(f"/api/pillars/{p['id']}", json={"setback_m": 0.3})


def test_seed_pillars_carry_setback_and_shared_band(client):
    rows = client.get("/api/pillars").json()
    assert len(rows) == 2
    for r in rows:
        assert r["setback_m"] == 0.3
        # 柱页禁入带与引擎同一定义：厚度半宽 0.25 + 外扩 0.3
        assert r["band_start_m"] == round(r["position_m"] - 0.55, 3)
        assert r["band_end_m"] == round(r["position_m"] + 0.55, 3)


def test_negative_setback_rejected_and_everything_stays(client):
    rows = client.get("/api/pillars").json()
    pid = rows[0]["id"]
    before = client.get("/api/pillars").json()
    runs_before = client.get("/api/allocate/latest?segment_id=1").json()

    r = client.put(f"/api/pillars/{pid}", json={"setback_m": -0.5})
    assert r.status_code in (400, 422)
    r = client.put(f"/api/pillars/{pid}", json={"setback_m": float("nan")})
    assert r.status_code in (400, 422)

    # 列表停在改前
    assert client.get("/api/pillars").json() == before
    # 图与拒绝名单与运行记录停在改前（不产生新运行、不回刷旧快照）
    runs_after = client.get("/api/allocate/latest?segment_id=1").json()
    assert runs_after["id"] == runs_before["id"]
    assert runs_after["blocked"] == runs_before["blocked"]
    assert runs_after["rejected"] == runs_before["rejected"]


def test_update_setback_persists_and_rerun_uses_new_value(client):
    pid = client.get("/api/pillars").json()[0]["id"]
    r = client.put(f"/api/pillars/{pid}", json={"setback_m": 0.9})
    assert r.status_code == 200
    assert r.json()["setback_m"] == 0.9
    # 提交后再进列表保留
    assert client.get("/api/pillars").json()[0]["setback_m"] == 0.9

    run = client.post("/api/allocate/run?segment_id=1").json()
    # 重分按提交瞬间新值切空：柱1 禁入带 = 10 ± (0.25 + 0.9)
    assert {"start_m": 8.85, "end_m": 11.15} in run["blocked"]
    # 主图空隙端点与引擎禁入端点同数
    spans = [(s["start_m"], s["end_m"]) for s in run["free_spans"]]
    bands = [(b["start_m"], b["end_m"]) for b in run["blocked"]]
    for (a, b), (c, d) in zip(spans, bands):
        assert b == c
    # 合法摊边不得吃进外扩带
    for p in run["placements"]:
        for lo, hi in bands:
            assert p["end_m"] <= lo + 1e-9 or p["start_m"] >= hi - 1e-9


def test_old_run_snapshot_not_rebrushed_by_new_setback(client):
    run_a = client.post("/api/allocate/run?segment_id=1").json()
    pid = client.get("/api/pillars").json()[0]["id"]
    client.put(f"/api/pillars/{pid}", json={"setback_m": 1.2})

    latest = client.get("/api/allocate/latest?segment_id=1").json()
    # 旧运行快照不得被新外扩回刷
    assert latest["id"] == run_a["id"]
    assert latest["blocked"] == run_a["blocked"]
    assert latest["pillars"][0]["setback_m"] == 0.3

    run_b = client.post("/api/allocate/run?segment_id=1").json()
    # 重分后按新值画空隙，主图与放不下同源同一次运行
    assert run_b["id"] != run_a["id"]
    assert {"start_m": 8.55, "end_m": 11.45} in run_b["blocked"]
    assert client.get("/api/allocate/latest?segment_id=1").json()["id"] == run_b["id"]


def test_zero_setback_matches_thickness_only(client):
    pid = client.get("/api/pillars").json()[0]["id"]
    client.put(f"/api/pillars/{pid}", json={"setback_m": 0})
    run = client.post("/api/allocate/run?segment_id=1").json()
    # 外扩填 0 只按厚度：柱1 禁入带 = 10 ± 0.25
    assert {"start_m": 9.75, "end_m": 10.25} in run["blocked"]
