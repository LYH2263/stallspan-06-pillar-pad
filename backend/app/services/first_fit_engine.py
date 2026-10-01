"""1D First-Fit stall placement along a street segment; stalls cannot cross pillars."""
from __future__ import annotations
from dataclasses import asdict, dataclass

# 拒因只写空档不足 / 跨柱类：不与供电不足、净距不足并句，也不写成应急占用
REJECT_REASON = "无连续空档可放下且不跨越挡柱"

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

def pillar_band(position_m: float, thickness_m: float, setback_m: float = 0.0) -> tuple[float, float]:
    """禁入带唯一定义：厚度半宽 + 外扩，以柱心向两侧对称延伸。

    柱编辑页、切空引擎、主图空隙、放不下原因四处共用此函数，只改一处即废。
    外扩为 0 时退化为仅厚度（与绿仓口径相同）；负数在入口即被打回，不会传到这里。
    """
    half = thickness_m / 2.0 + setback_m
    return position_m - half, position_m + half

def _merged_bands(width_m: float, pillars: list[dict]) -> list[list[float]]:
    """未取整的合并禁入带：邻柱外扩相交（或相接）即并成一段连续禁入，不留夹缝。"""
    blocked = []
    for p in pillars:
        lo, hi = pillar_band(p["position_m"], p.get("thickness_m", 0.4), p.get("setback_m", 0.0))
        lo = max(0.0, lo)
        hi = min(width_m, hi)
        if hi > lo:
            blocked.append((lo, hi))
    blocked.sort()
    merged: list[list[float]] = []
    for lo, hi in blocked:
        if not merged or lo > merged[-1][1] + 1e-9:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    return merged

def blocked_bands(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """合并后的连续禁入带（供主图与柱页画带）；端点与空档端点同数。"""
    return [(round(a, 3), round(b, 3)) for a, b in _merged_bands(width_m, pillars)]

def free_spans_from_pillars(width_m: float, pillars: list[dict]) -> list[tuple[float, float]]:
    """空档 = 街段减去合并禁入带；与 blocked_bands 同源同取整，端点一致。"""
    spans = []
    cursor = 0.0
    for lo, hi in _merged_bands(width_m, pillars):
        if lo > cursor:
            spans.append((cursor, lo))
        cursor = hi
    if cursor < width_m:
        spans.append((cursor, width_m))
    return [(round(a, 3), round(b, 3)) for a, b in spans if b - a > 1e-6]

def allocate_first_fit(width_m: float, vendors: list[dict], pillars: list[dict]) -> AllocResult:
    """vendors sorted by priority ascending then id; each needs stall_width_m contiguous in one free span (no pillar cross)."""
    spans = free_spans_from_pillars(width_m, pillars)
    # mutable remaining capacity per span
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
                placements.append(Placement(v["id"], v["name"], round(start, 3), round(end, 3), need))
                span[0] = end
                placed = True
                break
        if not placed:
            rejected.append(Rejected(v["id"], v["name"], need, REJECT_REASON))
    free = [(round(a, 3), round(b, 3)) for a, b in remain if b - a > 1e-6]
    return AllocResult(placements, rejected, free)

def result_to_dict(r: AllocResult) -> dict:
    return {
        "placements": [asdict(p) for p in r.placements],
        "rejected": [asdict(x) for x in r.rejected],
        "free_spans": [{"start_m": a, "end_m": b} for a, b in r.free_spans],
    }
