"""1D First-Fit stall placement along a street segment.

唯一禁入口径：每根挡柱的禁入带 = 厚度半宽 + 单侧外扩（clearance_m）。
blocked_zone_records / blocked_zones_from_pillars 是切空引擎、主图空隙、
挡柱页示意、拒绝名单共用的唯一端点来源 —— 不要在前端或其它后端模块
再算第二份「柱侧空白」。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

# 拒因只允许落到这两类措辞；禁止与「供电不足」「净距不足」并句，
# 也不得写成「应急占用」。
REASON_GAP_TOO_SMALL = "空档不足：街段内没有足够宽的连续空档"
REASON_CROSSES_PILLAR = "跨柱类：连续空档均放不下，摊位不得跨越挡柱禁入带"

EPS = 1e-9


@dataclass
class Placement:
    vendor_id: int
    vendor_name: str
    start_m: float
    end_m: float
    width_m: float


@dataclass
class Rejected:
    vendor_id: int
    vendor_name: str
    width_m: float
    reason: str


@dataclass
class AllocResult:
    placements: list[Placement]
    rejected: list[Rejected]
    free_spans: list[tuple[float, float]]
    blocked_zones: list[dict]


def _pillar_record(p: dict, width_m: float) -> dict:
    """单柱：柱芯按厚度半宽，禁入带按厚度半宽 + 单侧外扩。

    clearance_m 缺省/为 0 时禁入带等于柱芯（与绿仓口径相同）；
    负数在 API 入口已被打回，这里兜底按 0 处理。
    """
    half = float(p.get("thickness_m", 0.4)) / 2.0
    extra = max(0.0, float(p.get("clearance_m", 0.0) or 0.0))
    center = float(p["position_m"])
    core_lo = max(0.0, center - half)
    core_hi = min(float(width_m), center + half)
    zone_lo = max(0.0, center - half - extra)
    zone_hi = min(float(width_m), center + half + extra)
    return {
        "position_m": round(center, 3),
        "core_start_m": round(core_lo, 3),
        "core_end_m": round(core_hi, 3),
        "zone_start_m": round(zone_lo, 3),
        "zone_end_m": round(zone_hi, 3),
        "clearance_m": round(extra, 3),
        "label": p.get("label", "挡柱"),
        "pillar_id": p.get("id"),
    }


def blocked_zone_records(width_m: float, pillars: list[dict]) -> list[dict]:
    """合并后的连续禁入带；相交（含端点相接）立即合并，杜绝邻柱外扩夹缝。"""
    records = [_pillar_record(p, width_m) for p in pillars]
    records = [r for r in records if r["zone_end_m"] - r["zone_start_m"] > EPS]
    records.sort(key=lambda r: (r["zone_start_m"], r["zone_end_m"]))
    merged: list[dict] = []
    for r in records:
        if not merged or r["zone_start_m"] > merged[-1]["end_m"]:
            merged.append({"start_m": r["zone_start_m"], "end_m": r["zone_end_m"],
                           "pillars": [r]})
        else:
            # 相交或相接 → 合并成一条连续禁入，夹缝处不得再塞摊
            merged[-1]["end_m"] = max(merged[-1]["end_m"], r["zone_end_m"])
            merged[-1]["pillars"].append(r)
    out = []
    for z in merged:
        z["start_m"] = round(z["start_m"], 3)
        z["end_m"] = round(z["end_m"], 3)
        out.append(z)
    return out


def blocked_zones_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """连续禁入带端点（切空引擎直接消费）。"""
    return [(z["start_m"], z["end_m"]) for z in blocked_zone_records(width_m, pillars)]


def free_spans_from_blocked(
    width_m: float, blocked: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """禁入带在 [0, width] 内的补集；空白端点直接取自禁入端点，保证同数。"""
    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for lo, hi in blocked:
        if lo - cursor > EPS:
            spans.append((cursor, lo))
        cursor = max(cursor, hi)
    if width_m - cursor > EPS:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > 1e-6]


def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """保留旧入口：内部仍走唯一的禁入带函数。"""
    return free_spans_from_blocked(width_m, blocked_zones_from_pillars(width_m, pillars))


def _reject_reason(need: float, width_m: float) -> str:
    # 摊位比整条街还宽 → 空档不足；否则是被挡柱禁入带切碎 → 跨柱类。
    if need > width_m + EPS:
        return REASON_GAP_TOO_SMALL
    return REASON_CROSSES_PILLAR


def allocate_first_fit(
    width_m: float, vendors: list[dict], pillars: list[dict]
) -> AllocResult:
    """vendors 按 priority 再按 id 排序；摊位须在同一段连续空档内放下，禁入带不可跨越。"""
    zones = blocked_zone_records(width_m, pillars)
    blocked = [(z["start_m"], z["end_m"]) for z in zones]
    spans = free_spans_from_blocked(width_m, blocked)
    # 每段空档的剩余可分配区间
    remain = [[a, b] for a, b in spans]
    ordered = sorted(vendors, key=lambda v: (v.get("priority", 1), v["id"]))
    placements: list[Placement] = []
    rejected: list[Rejected] = []
    for v in ordered:
        need = float(v["stall_width_m"])
        placed = False
        for span in remain:
            avail = span[1] - span[0]
            if avail + 1e-9 >= need:
                start = span[0]
                end = start + need
                placements.append(
                    Placement(v["id"], v["name"], round(start, 3), round(end, 3), need)
                )
                span[0] = end
                placed = True
                break
        if not placed:
            rejected.append(
                Rejected(v["id"], v["name"], need, _reject_reason(need, width_m))
            )
    free = [
        (round(a, 3), round(b, 3))
        for a, b in remain
        if b - a > 1e-6
    ]
    return AllocResult(placements, rejected, free, zones)


def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
        # 主图与挡柱页直接消费这份端点画柱侧空白，禁止再按旧外扩自行留白
        "blocked_zones": r.blocked_zones,
    }
