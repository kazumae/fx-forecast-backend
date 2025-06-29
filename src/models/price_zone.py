"""
価格ゾーンモデル
サポート・レジスタンスラインの管理
"""

from sqlalchemy import Column, BIGINT, TEXT, DECIMAL, INTEGER, BOOLEAN, TIMESTAMP, func
from .base import Base


class PriceZone(Base):
    __tablename__ = 'price_zones'
    
    id = Column(BIGINT, primary_key=True, autoincrement=True)
    symbol = Column(TEXT, nullable=False)
    zone_type = Column(TEXT, nullable=False)  # 'support', 'resistance'
    price_level = Column(DECIMAL(12, 6), nullable=False)
    strength = Column(INTEGER, default=1)
    first_touch = Column(TIMESTAMP(timezone=True), nullable=False)
    last_touch = Column(TIMESTAMP(timezone=True))
    touch_count = Column(INTEGER, default=1)
    is_active = Column(BOOLEAN, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<PriceZone(symbol='{self.symbol}', type='{self.zone_type}', level={self.price_level}, strength={self.strength})>"
    
    def to_dict(self):
        """辞書形式に変換"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'zone_type': self.zone_type,
            'price_level': float(self.price_level) if self.price_level else None,
            'strength': self.strength,
            'first_touch': self.first_touch.isoformat() if self.first_touch else None,
            'last_touch': self.last_touch.isoformat() if self.last_touch else None,
            'touch_count': self.touch_count,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_support(cls, symbol: str, price_level: float, timestamp=None):
        """サポートラインインスタンス作成"""
        return cls(
            symbol=symbol,
            zone_type='support',
            price_level=price_level,
            first_touch=timestamp or func.now(),
            strength=1,
            touch_count=1,
            is_active=True
        )
    
    @classmethod
    def create_resistance(cls, symbol: str, price_level: float, timestamp=None):
        """レジスタンスラインインスタンス作成"""
        return cls(
            symbol=symbol,
            zone_type='resistance',
            price_level=price_level,
            first_touch=timestamp or func.now(),
            strength=1,
            touch_count=1,
            is_active=True
        )
    
    def add_touch(self, timestamp=None):
        """タッチ回数を増加"""
        self.touch_count += 1
        self.last_touch = timestamp or func.now()
        self.strength = min(self.strength + 1, 10)  # 最大強度は10
        self.updated_at = func.now()
    
    def deactivate(self):
        """ゾーンを無効化"""
        self.is_active = False
        self.updated_at = func.now()
    
    def is_near_price(self, price: float, tolerance_pips: int = 10) -> bool:
        """指定価格がゾーン近辺かどうか判定"""
        pip_value = 0.1  # XAUUSDの場合、1pip = 0.1
        tolerance = tolerance_pips * pip_value
        
        return abs(float(self.price_level) - price) <= tolerance
    
    def get_strength_level(self) -> str:
        """強度レベルを文字列で返す"""
        if self.strength >= 8:
            return 'very_strong'
        elif self.strength >= 5:
            return 'strong'
        elif self.strength >= 3:
            return 'moderate'
        else:
            return 'weak'