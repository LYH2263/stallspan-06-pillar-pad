import pytest
from pydantic import ValidationError

from app.api.pillars import PillarUpdate
from app.services.first_fit_engine import (
    REASON_CROSSES_PILLAR,
    REASON_GAP_TOO_SMALL,
    allocate_first_fit,
    blocked_zone_records,
    blocked_zones_from_pillars,
    free_spans_from_blocked,
    free_spans_from_pillars,
)

P = lambda pos, th=0.5, cl=0.0: {"position_m": pos, "thickness_m": th, "clearance_m": cl}


def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, [P(10.0), P(20.0)])
    assert len(spans) == 3
    assert spans[0][0] == 0.0


def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    r = allocate_first_fit(30.0, vendors, [P(10.0)])
    assert any(p.vendor_name == "A" for p in r.placements)
    assert len(r.placements) + len(r.rejected) == 2


def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    r = allocate_first_fit(30.0, vendors, [P(10.0), P(20.0)])
    assert len(r.rejected) == 1
    assert r.rejected[0].vendor_name == "Huge"


def test_clearance_zero_equals_thickness_only():
    """外扩 0 与不传外扩（绿仓口径）完全一致。"""
    a = blocked_zones_from_pillars(30.0, [{"position_m": 10.0, "thickness_m": 0.5}])
    b = blocked_zones_from_pillars(30.0, [P(10.0, 0.5, 0.0)])
    assert a == b == [(9.75, 10.25)]


def test_clearance_extends_half_thickness_each_side():
    zones = blocked_zones_from_pillars(30.0, [P(10.0, 0.5, 0.3)])
    assert zones == [(9.45, 10.55)]


def test_overlapping_clearances_merge_no_gap():
    """两柱外扩相交：必须合并成一条连续禁入，夹缝不得塞摊。"""
    # 柱芯 10/14，厚 0.5（半宽 0.25），外扩 1.75 → [8,12] 与 [12,16] 端点相接
    zones = blocked_zones_from_pillars(30.0, [P(10.0, 0.5, 1.75), P(14.0, 0.5, 1.75)])
    assert zones == [(8.0, 16.0)]
    spans = free_spans_from_blocked(30.0, zones)
    # 夹缝 12 处不允许出现独立空档
    assert all(not (11.9 < a and b < 12.1) for a, b in spans)


def test_overlapping_clearances_merge_with_overlap():
    # 厚 0.5（半宽 0.25）、外扩 2.05 → [7.7,12.3] 与 [11.7,16.3] 相交
    zones = blocked_zones_from_pillars(30.0, [P(10.0, 0.5, 2.05), P(14.0, 0.5, 2.05)])
    assert zones == [(7.7, 16.3)]


def test_engine_endpoints_equal_zone_records():
    """切空空档端点与禁入带记录端点必须同数（互补集）。"""
    pillars = [P(10.0, 0.5, 0.3), P(20.0, 0.5, 0.3)]
    recs = blocked_zone_records(30.0, pillars)
    tuples = [(z["start_m"], z["end_m"]) for z in recs]
    spans = free_spans_from_pillars(30.0, pillars)
    # 每条空档的边界都取自禁入端点或街段端点
    boundaries = {0.0, 30.0}
    for a, b in tuples:
        boundaries.add(a); boundaries.add(b)
    for a, b in spans:
        assert a in boundaries and b in boundaries
    assert tuples == [(9.45, 10.55), (19.45, 20.55)]
    assert spans == [(0.0, 9.45), (10.55, 19.45), (20.55, 30.0)]


def test_seed_wide_stall_fits_at_zero_but_rejected_at_03():
    """种子宽摊 9.5 m：外扩 0 勉强进端档 9.75；外扩 0.3 端档 9.45 → 放不下。"""
    vendors = [{"id": 7, "name": "巨型舞台车", "stall_width_m": 9.5, "priority": 1}]
    fit = allocate_first_fit(30.0, vendors, [P(10.0), P(20.0)])
    assert any(p.vendor_name == "巨型舞台车" for p in fit.placements)
    rej = allocate_first_fit(30.0, vendors, [P(10.0, 0.5, 0.3), P(20.0, 0.5, 0.3)])
    assert not any(p.vendor_name == "巨型舞台车" for p in rej.placements)
    assert len(rej.rejected) == 1


def test_reject_reason_wording_only_two_kinds():
    """拒因只允许空档不足/跨柱类，不得与供电、净距、应急占用并句。"""
    small_vendors = [{"id": 1, "name": "宽摊", "stall_width_m": 9.5, "priority": 1}]
    r = allocate_first_fit(30.0, small_vendors, [P(10.0, 0.5, 0.3), P(20.0, 0.5, 0.3)])
    assert r.rejected[0].reason == REASON_CROSSES_PILLAR

    huge = [{"id": 2, "name": "超长车", "stall_width_m": 31.0, "priority": 1}]
    r2 = allocate_first_fit(30.0, huge, [])
    assert r2.rejected[0].reason == REASON_GAP_TOO_SMALL

    for x in r.rejected + r2.rejected:
        for banned in ("供电", "净距", "应急"):
            assert banned not in x.reason


def test_negative_clearance_in_api_model_rejected():
    """负数外扩在入口（pydantic）直接 422 打回。"""
    with pytest.raises(ValidationError):
        PillarUpdate(clearance_m=-0.01)
    ok = PillarUpdate(clearance_m=0.0)
    assert ok.clearance_m == 0.0


def test_engine_treats_negative_clearance_as_zero_defensively():
    zones = blocked_zones_from_pillars(30.0, [P(10.0, 0.5, -1.0)])
    assert zones == [(9.75, 10.25)]


def test_result_dict_carries_blocked_zones():
    r = allocate_first_fit(30.0,
                           [{"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1}],
                           [P(10.0, 0.5, 0.3)])
    d = r.blocked_zones
    assert d[0]["start_m"] == 9.45 and d[0]["end_m"] == 10.55
    assert d[0]["pillars"][0]["core_start_m"] == 9.75
    assert d[0]["pillars"][0]["clearance_m"] == 0.3
