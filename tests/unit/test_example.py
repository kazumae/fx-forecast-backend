"""サンプルテスト（動作確認用）"""
import pytest
from decimal import Decimal


class TestExample:
    """サンプルテストクラス"""
    
    def test_basic_assertion(self):
        """基本的なアサーション"""
        assert 1 + 1 == 2
    
    def test_decimal_operations(self):
        """Decimal演算のテスト"""
        price1 = Decimal("3275.50")
        price2 = Decimal("3280.00")
        
        difference = price2 - price1
        assert difference == Decimal("4.50")
        
        # pips計算
        pips = float(difference) * 100
        assert pips == 450.0
    
    @pytest.mark.parametrize("value,expected", [
        (0, 0),
        (50, 50),
        (100, 100),
        (150, 100),  # 上限
        (-10, 0),    # 下限
    ])
    def test_score_normalization(self, value, expected):
        """スコア正規化のテスト"""
        def normalize_score(score):
            return max(0, min(100, score))
        
        assert normalize_score(value) == expected
    
    def test_risk_reward_calculation(self):
        """リスクリワード計算のテスト"""
        entry_price = Decimal("3275.00")
        stop_loss = Decimal("3270.00")
        take_profit = Decimal("3285.00")
        
        risk = float(entry_price - stop_loss) * 100  # pips
        reward = float(take_profit - entry_price) * 100  # pips
        rr_ratio = reward / risk if risk > 0 else 0
        
        assert risk == 500.0
        assert reward == 1000.0
        assert rr_ratio == 2.0