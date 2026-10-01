import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import AllocationRun, Pillar, Segment, Vendor
from app.services.first_fit_engine import allocate_first_fit, blocked_bands, result_to_dict
router = APIRouter(prefix="/allocate", tags=["allocate"])

def _run_result(seg: Segment, db: Session) -> dict:
    # 提交瞬间从库里取挡柱（含外扩），重分一律按当下新值切空
    pillars = [{"id": p.id, "position_m": p.position_m, "thickness_m": p.thickness_m,
                "setback_m": p.setback_m, "label": p.label}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == seg.id)
                                   .order_by(Pillar.position_m)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m, "priority": v.priority}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    result = result_to_dict(allocate_first_fit(seg.width_m, vendors, pillars))
    result["segment"] = {"id": seg.id, "name": seg.name, "width_m": seg.width_m}
    result["pillars"] = pillars
    # 主图直接消费引擎合并后的禁入带，图上柱侧空白端点与引擎禁入端点同数
    result["blocked"] = [{"start_m": a, "end_m": b} for a, b in blocked_bands(seg.width_m, pillars)]
    return result

@router.post("/run")
def run_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    seg = db.get(Segment, segment_id)
    if not seg: raise HTTPException(404, "街段不存在")
    result = _run_result(seg, db)
    run = AllocationRun(segment_id=segment_id, created_at=datetime.utcnow(),
                        result_json=json.dumps(result, ensure_ascii=False))
    db.add(run); db.commit(); db.refresh(run)
    return {"id": run.id, **result}

@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if not run:
        return run_allocate(segment_id=segment_id, db=db)
    data = json.loads(run.result_json)
    if "blocked" not in data and "segment" in data:
        # 旧快照按自身留存的挡柱数据补算禁入带：只读补全，不改写快照、不用新外扩回刷
        data["blocked"] = [{"start_m": a, "end_m": b}
                           for a, b in blocked_bands(data["segment"]["width_m"], data.get("pillars", []))]
    return {"id": run.id, **data}
