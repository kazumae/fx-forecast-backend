"""タイムゾーン関連のユーティリティ"""
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional


# 日本標準時のタイムゾーン
JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")


def get_jst_now() -> datetime:
    """現在の日本時間を取得"""
    return datetime.now(JST)


def utc_to_jst(dt: Optional[datetime]) -> Optional[datetime]:
    """UTC時間を日本時間に変換"""
    if dt is None:
        return None
    
    # タイムゾーン情報がない場合はUTCとして扱う
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    
    return dt.astimezone(JST)


def ensure_jst(dt: Optional[datetime]) -> Optional[datetime]:
    """datetimeオブジェクトを確実に日本時間に変換"""
    if dt is None:
        return None
    
    # すでに日本時間の場合はそのまま返す
    if dt.tzinfo is not None and str(dt.tzinfo) == "Asia/Tokyo":
        return dt
    
    return utc_to_jst(dt)


def format_jst_datetime(dt: Optional[datetime], format_str: str = "%Y/%m/%d %H:%M:%S") -> str:
    """日本時間として日時をフォーマット"""
    if dt is None:
        return ""
    
    jst_dt = ensure_jst(dt)
    return jst_dt.strftime(format_str) if jst_dt else ""