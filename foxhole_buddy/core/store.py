from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


EXPIRY_HOURS = 48
WARNING_THRESHOLDS = {
    "24h": timedelta(hours=24),
    "6h": timedelta(hours=6),
    "2h": timedelta(hours=2),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def dt_to_str(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@dataclass
class Stockpile:
    id: str
    guild_id: int
    channel_id: int
    message_id: int | None
    name: str
    location: str
    type: str
    created_by_user_id: int
    last_refreshed_at: str
    expires_at: str
    last_refreshed_by_user_id: int
    warned_24h: bool
    warned_6h: bool
    warned_2h: bool
    expired_notified: bool
    created_at: str
    updated_at: str

    @property
    def expires_datetime(self) -> datetime:
        return parse_dt(self.expires_at)

    @property
    def last_refreshed_datetime(self) -> datetime:
        return parse_dt(self.last_refreshed_at)


class StockpileStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_raw(self) -> dict:
        if not self.path.exists():
            return {"guild_channels": {}, "stockpiles": []}
        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        # Back-compat: old format only had {"stockpiles": [...]}
        raw.setdefault("guild_channels", {})
        return raw

    def _save_raw(self, raw: dict) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2)
            handle.write("\n")
        tmp_path.replace(self.path)

    # ------------------------------------------------------------------
    # Guild configuration
    # ------------------------------------------------------------------

    def get_guild_channel(self, guild_id: int) -> int | None:
        cfg = self._load_raw().get("guild_channels", {}).get(str(guild_id))
        return cfg.get("channel_id") if cfg else None

    def get_guild_urgent_role(self, guild_id: int) -> int | None:
        cfg = self._load_raw().get("guild_channels", {}).get(str(guild_id))
        return cfg.get("urgent_role_id") if cfg else None

    def set_guild_config(
        self,
        guild_id: int,
        channel_id: int,
        urgent_role_id: int | None = None,
    ) -> None:
        raw = self._load_raw()
        guild_channels = raw.setdefault("guild_channels", {})
        entry = guild_channels.get(str(guild_id), {})
        entry["channel_id"] = channel_id
        if urgent_role_id is not None:
            entry["urgent_role_id"] = urgent_role_id
        elif "urgent_role_id" in entry and urgent_role_id is None:
            entry.pop("urgent_role_id", None)
        guild_channels[str(guild_id)] = entry
        self._save_raw(raw)

    # ------------------------------------------------------------------
    # Stockpile CRUD
    # ------------------------------------------------------------------

    def all(self, guild_id: int | None = None) -> list[Stockpile]:
        raw = self._load_raw()
        stockpiles = [Stockpile(**item) for item in raw.get("stockpiles", [])]
        if guild_id is not None:
            stockpiles = [s for s in stockpiles if s.guild_id == guild_id]
        return stockpiles

    def save_all(self, stockpiles: Iterable[Stockpile]) -> None:
        raw = self._load_raw()
        raw["stockpiles"] = [asdict(item) for item in stockpiles]
        self._save_raw(raw)

    def get(self, stockpile_id: str, guild_id: int | None = None) -> Stockpile | None:
        return next(
            (s for s in self.all(guild_id=guild_id) if s.id == stockpile_id), None
        )

    def create(
        self,
        *,
        guild_id: int,
        channel_id: int,
        name: str,
        location: str,
        stockpile_type: str,
        user_id: int,
        now: datetime | None = None,
    ) -> Stockpile:
        current = now or utc_now()
        current_str = dt_to_str(current)
        stockpile = Stockpile(
            id=uuid.uuid4().hex[:8],
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=None,
            name=name.strip(),
            location=location.strip(),
            type=stockpile_type,
            created_by_user_id=user_id,
            last_refreshed_at=current_str,
            expires_at=dt_to_str(current + timedelta(hours=EXPIRY_HOURS)),
            last_refreshed_by_user_id=user_id,
            warned_24h=False,
            warned_6h=False,
            warned_2h=False,
            expired_notified=False,
            created_at=current_str,
            updated_at=current_str,
        )
        stockpiles = self.all()
        stockpiles.append(stockpile)
        self.save_all(stockpiles)
        return stockpile

    def update(self, updated: Stockpile) -> Stockpile:
        stockpiles = self.all()
        for index, stockpile in enumerate(stockpiles):
            if stockpile.id == updated.id:
                updated.updated_at = dt_to_str(utc_now())
                stockpiles[index] = updated
                self.save_all(stockpiles)
                return updated
        raise KeyError(f"Unknown stockpile id: {updated.id}")

    def set_message_id(self, stockpile_id: str, message_id: int) -> Stockpile:
        stockpile = self.get(stockpile_id)
        if stockpile is None:
            raise KeyError(f"Unknown stockpile id: {stockpile_id}")
        stockpile.message_id = message_id
        return self.update(stockpile)

    def refresh(
        self,
        stockpile_id: str,
        *,
        user_id: int,
        guild_id: int | None = None,
        now: datetime | None = None,
    ) -> Stockpile:
        stockpile = self.get(stockpile_id, guild_id=guild_id)
        if stockpile is None:
            raise KeyError(f"Unknown stockpile id: {stockpile_id}")

        current = now or utc_now()
        stockpile.last_refreshed_at = dt_to_str(current)
        stockpile.expires_at = dt_to_str(current + timedelta(hours=EXPIRY_HOURS))
        stockpile.last_refreshed_by_user_id = user_id
        stockpile.warned_24h = False
        stockpile.warned_6h = False
        stockpile.warned_2h = False
        stockpile.expired_notified = False
        return self.update(stockpile)

    def delete(self, stockpile_id: str, guild_id: int | None = None) -> bool:
        stockpile = self.get(stockpile_id, guild_id=guild_id)
        if stockpile is None:
            return False
        stockpiles = self.all()
        kept = [s for s in stockpiles if s.id != stockpile_id]
        self.save_all(kept)
        return True


def remaining_time(stockpile: Stockpile, now: datetime | None = None) -> timedelta:
    return stockpile.expires_datetime - (now or utc_now())


def warning_due(stockpile: Stockpile, now: datetime | None = None) -> str | None:
    remaining = remaining_time(stockpile, now)
    if remaining <= timedelta(seconds=0):
        return "expired" if not stockpile.expired_notified else None
    if remaining <= WARNING_THRESHOLDS["2h"] and not stockpile.warned_2h:
        return "2h"
    if remaining <= WARNING_THRESHOLDS["6h"] and not stockpile.warned_6h:
        return "6h"
    if remaining <= WARNING_THRESHOLDS["24h"] and not stockpile.warned_24h:
        return "24h"
    return None


def mark_warning_sent(stockpile: Stockpile, warning: str) -> Stockpile:
    if warning == "24h":
        stockpile.warned_24h = True
    elif warning == "6h":
        stockpile.warned_6h = True
    elif warning == "2h":
        stockpile.warned_2h = True
    elif warning == "expired":
        stockpile.expired_notified = True
    else:
        raise ValueError(f"Unknown warning: {warning}")
    return stockpile


def format_remaining(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "expired"

    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# ── Resource needs ─────────────────────────────────────────────────────────────

@dataclass
class ResourceNeed:
    """Tracks a material farming need posted by a regiment."""
    id: str
    guild_id: int
    channel_id: int
    message_id: int | None
    material: str
    amount_needed: int
    created_by_user_id: int
    created_at: str
    updated_at: str
    claims: list          # list[dict] — {user_id, pledged, farmed}
    fulfilled: bool = False


# Attach resource methods to StockpileStore via extension pattern
def _get_resource_needs(self, guild_id: int | None = None) -> list[ResourceNeed]:
    raw = self._load_raw()
    needs = [ResourceNeed(**item) for item in raw.get("resource_needs", [])]
    if guild_id is not None:
        needs = [n for n in needs if n.guild_id == guild_id]
    return needs


def _save_resource_needs(self, needs: Iterable[ResourceNeed]) -> None:
    raw = self._load_raw()
    raw["resource_needs"] = [asdict(n) for n in needs]
    self._save_raw(raw)


def _get_resource_need(self, need_id: str, guild_id: int | None = None) -> ResourceNeed | None:
    return next((n for n in self.get_resource_needs(guild_id) if n.id == need_id), None)


def _create_resource_need(self, *, guild_id: int, channel_id: int, material: str, amount_needed: int, user_id: int) -> ResourceNeed:
    now = dt_to_str(utc_now())
    need = ResourceNeed(
        id=uuid.uuid4().hex[:8],
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=None,
        material=material.strip(),
        amount_needed=amount_needed,
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
        claims=[],
        fulfilled=False,
    )
    needs = self.get_resource_needs()
    needs.append(need)
    self._save_resource_needs(needs)
    return need


def _update_resource_need(self, updated: ResourceNeed) -> ResourceNeed:
    needs = self.get_resource_needs()
    for i, n in enumerate(needs):
        if n.id == updated.id:
            updated.updated_at = dt_to_str(utc_now())
            needs[i] = updated
            self._save_resource_needs(needs)
            return updated
    raise KeyError(f"Unknown resource need id: {updated.id}")


def _set_resource_need_message_id(self, need_id: str, message_id: int) -> ResourceNeed:
    need = self.get_resource_need(need_id)
    if need is None:
        raise KeyError(need_id)
    need.message_id = message_id
    return self.update_resource_need(need)


def _claim_resource(self, need_id: str, *, user_id: int, amount: int, guild_id: int | None = None) -> ResourceNeed:
    need = self.get_resource_need(need_id, guild_id)
    if need is None:
        raise KeyError(need_id)
    for claim in need.claims:
        if claim["user_id"] == user_id:
            claim["pledged"] += amount
            return self.update_resource_need(need)
    need.claims.append({"user_id": user_id, "pledged": amount, "farmed": 0})
    return self.update_resource_need(need)


def _log_farmed(self, need_id: str, *, user_id: int, amount: int, guild_id: int | None = None) -> ResourceNeed:
    need = self.get_resource_need(need_id, guild_id)
    if need is None:
        raise KeyError(need_id)
    for claim in need.claims:
        if claim["user_id"] == user_id:
            claim["farmed"] += amount
            break
    else:
        need.claims.append({"user_id": user_id, "pledged": 0, "farmed": amount})
    if sum(c["farmed"] for c in need.claims) >= need.amount_needed:
        need.fulfilled = True
    return self.update_resource_need(need)


# ── Base Inventory ─────────────────────────────────────────────────────────────

def _get_base_inventory(self, guild_id: int) -> dict[str, float]:
    raw = self._load_raw()
    return raw.get("base_inventory", {}).get(str(guild_id), {})


def _add_to_base_inventory(self, guild_id: int, material: str, amount: float) -> dict[str, float]:
    if amount <= 0:
        raise ValueError("Amount to add must be greater than zero.")
    
    material = material.strip().title()
    raw = self._load_raw()
    inv_dict = raw.setdefault("base_inventory", {})
    guild_inv = inv_dict.setdefault(str(guild_id), {})
    
    current = guild_inv.get(material, 0.0)
    guild_inv[material] = current + amount
    
    self._save_raw(raw)
    return guild_inv


def _remove_from_base_inventory(self, guild_id: int, material: str, amount: float) -> dict[str, float]:
    if amount <= 0:
        raise ValueError("Amount to remove must be greater than zero.")
        
    material = material.strip().title()
    raw = self._load_raw()
    inv_dict = raw.setdefault("base_inventory", {})
    guild_inv = inv_dict.setdefault(str(guild_id), {})
    
    if material not in guild_inv:
        raise KeyError(f"'{material}' is not in the base inventory.")
        
    current = guild_inv[material]
    if amount > current:
        raise ValueError(f"Cannot remove {amount} {material}. Only {current} available.")
        
    new_amount = current - amount
    if new_amount <= 0:
        del guild_inv[material]
    else:
        guild_inv[material] = new_amount
        
    self._save_raw(raw)
    return guild_inv


# ── Factory Alarms ─────────────────────────────────────────────────────────────

@dataclass
class FactoryAlarm:
    id: str
    guild_id: int
    channel_id: int
    message_id: int | None
    facility_name: str
    created_by_user_id: int
    end_time: str
    single_ping: bool
    warned_before: bool
    warned_exact: bool
    warned_after: bool
    completed: bool

    @property
    def end_datetime(self) -> datetime:
        return parse_dt(self.end_time)


def _get_factory_alarms(self, guild_id: int | None = None) -> list[FactoryAlarm]:
    raw = self._load_raw()
    alarms = [FactoryAlarm(**item) for item in raw.get("factory_alarms", [])]
    if guild_id is not None:
        alarms = [a for a in alarms if a.guild_id == guild_id]
    return alarms

def _save_factory_alarms(self, alarms: Iterable[FactoryAlarm]) -> None:
    raw = self._load_raw()
    raw["factory_alarms"] = [asdict(a) for a in alarms]
    self._save_raw(raw)

def _get_factory_alarm(self, alarm_id: str, guild_id: int | None = None) -> FactoryAlarm | None:
    return next((a for a in self.get_factory_alarms(guild_id) if a.id == alarm_id), None)

def _create_factory_alarm(self, *, guild_id: int, channel_id: int, facility_name: str, duration_minutes: int, single_ping: bool, user_id: int) -> FactoryAlarm:
    now = utc_now()
    end_time = dt_to_str(now + timedelta(minutes=duration_minutes))
    alarm = FactoryAlarm(
        id=uuid.uuid4().hex[:8],
        guild_id=guild_id,
        channel_id=channel_id,
        message_id=None,
        facility_name=facility_name.strip(),
        created_by_user_id=user_id,
        end_time=end_time,
        single_ping=single_ping,
        warned_before=False,
        warned_exact=False,
        warned_after=False,
        completed=False,
    )
    alarms = self.get_factory_alarms()
    alarms.append(alarm)
    self._save_factory_alarms(alarms)
    return alarm

def _update_factory_alarm(self, updated: FactoryAlarm) -> FactoryAlarm:
    alarms = self.get_factory_alarms()
    for i, a in enumerate(alarms):
        if a.id == updated.id:
            alarms[i] = updated
            self._save_factory_alarms(alarms)
            return updated
    raise KeyError(f"Unknown factory alarm id: {updated.id}")

def _set_factory_alarm_message_id(self, alarm_id: str, message_id: int) -> FactoryAlarm:
    alarm = self.get_factory_alarm(alarm_id)
    if alarm is None:
        raise KeyError(alarm_id)
    alarm.message_id = message_id
    return self.update_factory_alarm(alarm)

def _delete_factory_alarm(self, alarm_id: str, guild_id: int | None = None) -> bool:
    alarm = self.get_factory_alarm(alarm_id, guild_id)
    if alarm is None:
        return False
    alarms = self.get_factory_alarms()
    kept = [a for a in alarms if a.id != alarm_id]
    self._save_factory_alarms(kept)
    return True

def _mark_factory_alarm_warned(self, alarm_id: str, warn_type: str) -> FactoryAlarm:
    alarm = self.get_factory_alarm(alarm_id)
    if alarm is None:
        raise KeyError(alarm_id)
    if warn_type == "before":
        alarm.warned_before = True
    elif warn_type == "exact":
        alarm.warned_exact = True
    elif warn_type == "after":
        alarm.warned_after = True
    elif warn_type == "completed":
        alarm.completed = True
    return self.update_factory_alarm(alarm)


# Bind methods onto StockpileStore
StockpileStore._save_resource_needs = _save_resource_needs
StockpileStore.get_resource_needs = _get_resource_needs
StockpileStore.get_resource_need = _get_resource_need
StockpileStore.create_resource_need = _create_resource_need
StockpileStore.update_resource_need = _update_resource_need
StockpileStore.set_resource_need_message_id = _set_resource_need_message_id
StockpileStore.claim_resource = _claim_resource
StockpileStore.log_farmed = _log_farmed
StockpileStore.get_base_inventory = _get_base_inventory
StockpileStore.add_to_base_inventory = _add_to_base_inventory
StockpileStore.remove_from_base_inventory = _remove_from_base_inventory
StockpileStore._save_factory_alarms = _save_factory_alarms
StockpileStore.get_factory_alarms = _get_factory_alarms
StockpileStore.get_factory_alarm = _get_factory_alarm
StockpileStore.create_factory_alarm = _create_factory_alarm
StockpileStore.update_factory_alarm = _update_factory_alarm
StockpileStore.set_factory_alarm_message_id = _set_factory_alarm_message_id
StockpileStore.delete_factory_alarm = _delete_factory_alarm
StockpileStore.mark_factory_alarm_warned = _mark_factory_alarm_warned
