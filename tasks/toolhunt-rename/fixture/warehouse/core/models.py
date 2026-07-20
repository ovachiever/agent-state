"""Domain models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Sku:
    sku_id: str
    description: str
    daily_demand: float
    lead_time_days: float
    safety_stock: float


@dataclass(frozen=True)
class Bin:
    bin_id: str
    zone: str
    capacity: int
