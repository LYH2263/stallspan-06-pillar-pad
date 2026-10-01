from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Pillar, Segment
from app.services.first_fit_engine import blocked_zone_records

router = APIRouter(prefix="/pillars", tags=["pillars"])


def _serialize(r: Pillar) -> dict:
    return {"id": r.id, "segment_id": r.segment_id, "position_m": r.position_m,
            "thickness_m": r.thickness_m, "clearance_m": r.clearance_m,
            "label": r.label}


@router.get("")
def list_pillars(db: Session = Depends(get_db)):
    return [_serialize(r)
            for r in db.scalars(select(Pillar).order_by(Pillar.position_m)).all()]


@router.get("/blocked-zones")
def blocked_zones(segment_id: int = 1, db: Session = Depends(get_db)):
    """按挡柱页当前已提交值实时计算的禁入带；与切空引擎是同一个函数、同一份端点。"""
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    rows = db.scalars(
        select(Pillar).where(Pillar.segment_id == segment_id).order_by(Pillar.position_m)
    ).all()
    pillar_dicts = [{"id": r.id, "position_m": r.position_m, "thickness_m": r.thickness_m,
                     "clearance_m": r.clearance_m, "label": r.label} for r in rows]
    return {
        "segment_id": segment_id,
        "width_m": seg.width_m,
        "pillars": [_serialize(r) for r in rows],
        # 与切空引擎同函数同端点，挡柱页柱侧空白只能取自这里
        "blocked_zones": blocked_zone_records(seg.width_m, pillar_dicts),
    }


class PillarUpdate(BaseModel):
    position_m: float | None = None
    thickness_m: float | None = Field(default=None, ge=0)
    # 负数外扩入口直接打回（422），列表/图/拒绝名单/运行抽屉一律停在改前
    clearance_m: float | None = Field(default=None, ge=0)
    label: str | None = None


@router.put("/{pillar_id}")
def update_pillar(pillar_id: int, body: PillarUpdate, db: Session = Depends(get_db)):
    row = db.get(Pillar, pillar_id)
    if not row:
        raise HTTPException(404, "挡柱不存在")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return _serialize(row)
