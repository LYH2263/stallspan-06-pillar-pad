from app.services.first_fit_engine import (
    REJECT_REASON,
    allocate_first_fit,
    blocked_bands,
    free_spans_from_pillars,
    pillar_band,
)

def test_free_spans_with_pillars():
    spans = free_spans_from_pillars(30.0, [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}])
    assert len(spans) == 3
    assert spans[0][0] == 0.0

def test_first_fit_no_cross_pillar():
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 12.0, "priority": 1},
    ]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert any(p.vendor_name == "A" for p in r.placements)
    # 12m may fit in a free span after first placement depending on remainders
    assert len(r.placements) + len(r.rejected) == 2

def test_reject_oversized():
    vendors = [{"id": 1, "name": "Huge", "stall_width_m": 25.0, "priority": 1}]
    pillars = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]
    r = allocate_first_fit(30.0, vendors, pillars)
    assert len(r.rejected) == 1
    assert r.rejected[0].vendor_name == "Huge"

def test_pillar_band_is_half_thickness_plus_setback():
    # 唯一定义：厚度半宽 + 外扩
    assert pillar_band(10.0, 0.5, 0.3) == (9.45, 10.55)
    assert pillar_band(10.0, 0.5, 0.0) == (9.75, 10.25)

def test_setback_zero_same_as_thickness_only():
    # 外扩填 0 时只按厚度，与绿仓相同
    plain = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]
    zeroed = [{**p, "setback_m": 0.0} for p in plain]
    assert free_spans_from_pillars(30.0, zeroed) == free_spans_from_pillars(30.0, plain)
    assert blocked_bands(30.0, zeroed) == blocked_bands(30.0, plain)

def test_adjacent_setbacks_merge_into_continuous_band():
    # 邻柱外扩相交必须合并成连续禁入，两柱外扩夹缝不得成为可塞摊的第三条空档
    pillars = [
        {"position_m": 10.0, "thickness_m": 0.4, "setback_m": 0.5},
        {"position_m": 10.8, "thickness_m": 0.4, "setback_m": 0.5},
    ]
    assert blocked_bands(30.0, pillars) == [(9.3, 11.5)]
    spans = free_spans_from_pillars(30.0, pillars)
    assert spans == [(0.0, 9.3), (11.5, 30.0)]

def test_free_span_endpoints_match_blocked_endpoints():
    # 图上柱侧空白端点与引擎禁入端点必须同数
    pillars = [
        {"position_m": 10.0, "thickness_m": 0.5, "setback_m": 0.3},
        {"position_m": 20.0, "thickness_m": 0.5, "setback_m": 0.3},
    ]
    bands = blocked_bands(30.0, pillars)
    spans = free_spans_from_pillars(30.0, pillars)
    assert spans[0][1] == bands[0][0]
    assert spans[1][0] == bands[0][1]
    assert spans[1][1] == bands[1][0]
    assert spans[2][0] == bands[1][1]

def test_wide_stall_rejected_only_after_setback():
    # 种子两柱外扩改 0.3 后，原勉强塞进的宽摊应改放不下
    vendors = [{"id": 1, "name": "W", "stall_width_m": 9.6, "priority": 1}]
    plain = [{"position_m": 10.0, "thickness_m": 0.5}, {"position_m": 20.0, "thickness_m": 0.5}]
    widened = [{**p, "setback_m": 0.3} for p in plain]
    assert len(allocate_first_fit(30.0, vendors, plain).placements) == 1
    r = allocate_first_fit(30.0, vendors, widened)
    assert len(r.placements) == 0
    assert len(r.rejected) == 1
    # 拒因只写空档不足 / 跨柱类，不与供电、净距并句，也不写应急占用
    assert r.rejected[0].reason == REJECT_REASON
    for word in ("供电", "净距", "应急"):
        assert word not in r.rejected[0].reason

def test_placement_edges_never_enter_setback_band():
    # 合法摊边不得吃进外扩带
    vendors = [
        {"id": 1, "name": "A", "stall_width_m": 4.0, "priority": 1},
        {"id": 2, "name": "B", "stall_width_m": 3.0, "priority": 1},
        {"id": 3, "name": "C", "stall_width_m": 6.0, "priority": 1},
        {"id": 4, "name": "D", "stall_width_m": 5.0, "priority": 2},
        {"id": 5, "name": "E", "stall_width_m": 2.5, "priority": 2},
    ]
    pillars = [
        {"position_m": 10.0, "thickness_m": 0.5, "setback_m": 0.3},
        {"position_m": 20.0, "thickness_m": 0.5, "setback_m": 0.3},
    ]
    r = allocate_first_fit(30.0, vendors, pillars)
    for lo, hi in blocked_bands(30.0, pillars):
        for p in r.placements:
            assert p.end_m <= lo + 1e-9 or p.start_m >= hi - 1e-9
