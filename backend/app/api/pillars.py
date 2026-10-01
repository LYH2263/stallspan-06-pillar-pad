from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Pillar
from app.services.first_fit_engine import pillar_band

router = APIRouter(prefix="/pillars", tags=["pillars"])

class PillarUpdate(BaseModel):
    # 外扩填负数（或非有限数）入口直接打回：校验失败不落库，列表/图/拒绝名单/运行一律停在改前
    setback_m: float = Field(ge=0, allow_inf_nan=False)

def _row(r: Pillar) -> dict:
    # 禁入带与引擎共用同一定义（厚度半宽 + 外扩），不在此处另算
    lo, hi = pillar_band(r.position_m, r.thickness_m, r.setback_m)
    return {"id": r.id, "segment_id": r.segment_id, "position_m": r.position_m,
            "thickness_m": r.thickness_m, "setback_m": r.setback_m, "label": r.label,
            "band_start_m": round(lo, 3), "band_end_m": round(hi, 3)}

@router.get("")
def list_pillars(db: Session = Depends(get_db)):
    return [_row(r) for r in db.scalars(select(Pillar).order_by(Pillar.position_m)).all()]

@router.put("/{pillar_id}")
def update_setback(pillar_id: int, body: PillarUpdate, db: Session = Depends(get_db)):
    p = db.get(Pillar, pillar_id)
    if not p:
        raise HTTPException(404, "挡柱不存在")
    p.setback_m = body.setback_m
    db.commit()
    return _row(p)
