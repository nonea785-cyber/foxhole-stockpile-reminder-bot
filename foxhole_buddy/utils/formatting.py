from foxhole_buddy.core.store import Stockpile, EXPIRY_HOURS, remaining_time

def unix_ts(value) -> int:
    return int(value.timestamp())

def stockpile_type_label(stockpile: Stockpile) -> str:
    return "Storage Depot" if stockpile.type == "storage_depot" else "Seaport"

def stockpile_status(stockpile: Stockpile) -> tuple[str, int]:
    remaining = remaining_time(stockpile)
    seconds_left = remaining.total_seconds()
    if seconds_left <= 0:
        return "PUBLIC RISK", 0xD83A3A
    if seconds_left <= 2 * 3600:
        return "CRITICAL", 0xF04747
    if seconds_left <= 6 * 3600:
        return "URGENT", 0xF59E0B
    if seconds_left <= 24 * 3600:
        return "WATCH", 0xEAB308
    return "SECURE", 0x2D7D46

def progress_bar(stockpile: Stockpile) -> str:
    total_seconds = EXPIRY_HOURS * 3600
    seconds_left = max(0, int(remaining_time(stockpile).total_seconds()))
    filled = round((seconds_left / total_seconds) * 10)
    filled = max(0, min(10, filled))
    return f"{'█' * filled}{'░' * (10 - filled)}"
