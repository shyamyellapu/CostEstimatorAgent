"""Settings API routes — rate configuration management."""
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import db_session
from app.models import RateConfiguration
from app.services.costing_engine import DEFAULT_RATES

router = APIRouter()
logger = logging.getLogger(__name__)


class RateUpdate(BaseModel):
    key: str
    value: float
    category: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def get_settings(db: AsyncSession = Depends(db_session)):
    result = await db.execute(select(RateConfiguration).where(RateConfiguration.is_active == True))
    rates = result.scalars().all()
    rate_dict = {r.key: r.value for r in rates}
    # Merge with defaults for any missing
    merged = {**DEFAULT_RATES, **rate_dict}
    return {
        "rates": merged,
        "rate_details": [
            {
                "id": str(r.id),
                "key": r.key,
                "name": r.name,
                "category": r.category,
                "value": r.value,
                "unit": r.unit,
                "description": r.description,
            }
            for r in rates
        ]
    }


@router.put("")
async def update_settings(updates: List[RateUpdate], db: AsyncSession = Depends(db_session)):
    updated = []
    for upd in updates:
        result = await db.execute(
            select(RateConfiguration).where(RateConfiguration.key == upd.key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = upd.value
            if upd.name:
                existing.name = upd.name
            if upd.unit:
                existing.unit = upd.unit
            if upd.description:
                existing.description = upd.description
        else:
            existing = RateConfiguration(
                key=upd.key,
                name=upd.name or upd.key,
                category=upd.category or "general",
                value=upd.value,
                unit=upd.unit,
                description=upd.description,
            )
            db.add(existing)
        updated.append(upd.key)
    await db.commit()
    return {"updated": updated, "message": f"{len(updated)} rate(s) updated"}


@router.post("/seed-defaults")
async def seed_default_rates(db: AsyncSession = Depends(db_session)):
    """Seed default rates into the database (run once on initial setup)."""
    created = []
    rate_meta = {
        "material_rate_per_kg": ("Material", "Steel Material Rate", "AED/kg"),
        "fabrication_rate_per_kg": ("Fabrication", "Weight-Based Fabrication Rate", "AED/kg"),
        "fabrication_hourly_rate": ("Fabrication", "Manhour Fabrication Rate", "AED/hr"),
        "manhour_factor_hr_per_kg": ("Fabrication", "Manhour Factor", "hr/kg"),
        "welding_time_per_m_hr": ("Welding", "Welding Time per Meter", "hr/m"),
        "welding_hourly_rate": ("Welding", "Welding Hourly Rate", "AED/hr"),
        "consumable_factor_kg_per_m": ("Consumables", "Consumable Factor", "kg/m"),
        "consumable_unit_rate": ("Consumables", "Consumable Unit Rate", "AED/kg"),
        "cutting_rate_per_cut": ("Cutting", "Rate per Cut", "AED/cut"),
        "surface_treatment_rate_per_m2": ("Surface", "Surface Treatment Rate", "AED/m²"),
        "overhead_percentage": ("Overhead", "Overhead Percentage", "%"),
        "profit_margin_percentage": ("Profit", "Profit Margin", "%"),
        "steel_density_kg_m3": ("Material", "Steel Density", "kg/m³"),
        "weld_length_per_joint_mm": ("Welding", "Default Weld Length per Joint", "mm"),
    }
    for key, value in DEFAULT_RATES.items():
        result = await db.execute(select(RateConfiguration).where(RateConfiguration.key == key))
        if not result.scalar_one_or_none():
            meta = rate_meta.get(key, ("General", key, ""))
            db.add(RateConfiguration(
                key=key, value=value,
                category=meta[0], name=meta[1], unit=meta[2],
            ))
            created.append(key)
    await db.commit()
    return {"created": created, "message": f"{len(created)} default rates seeded"}
