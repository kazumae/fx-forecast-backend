import random
from datetime import datetime, timedelta
from typing import List

from src.batch.base import BaseBatchJob
from src.models.forex import ForexRate
from src.services import forex as forex_service


class FetchForexRatesBatch(BaseBatchJob):
    """為替レートを取得するバッチジョブ"""
    
    def __init__(self, currency_pairs: List[str] = None):
        super().__init__("FetchForexRates")
        self.currency_pairs = currency_pairs or ["USD/JPY", "EUR/USD", "GBP/USD", "EUR/JPY"]
    
    def execute(self):
        """為替レートを取得してデータベースに保存"""
        saved_count = 0
        error_count = 0
        
        for currency_pair in self.currency_pairs:
            try:
                # 実際のAPIから取得する場合はここで外部APIを呼び出す
                # 今回はモックデータを生成
                rate_data = self._fetch_rate_from_api(currency_pair)
                
                # データベースに保存
                new_rate = ForexRate(
                    currency_pair=currency_pair,
                    rate=rate_data['rate'],
                    bid=rate_data['bid'],
                    ask=rate_data['ask'],
                    volume=rate_data['volume'],
                    timestamp=datetime.utcnow()
                )
                
                self.db.add(new_rate)
                saved_count += 1
                
                self.logger.info(
                    f"Saved rate for {currency_pair}: "
                    f"rate={rate_data['rate']}, bid={rate_data['bid']}, ask={rate_data['ask']}"
                )
                
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error fetching rate for {currency_pair}: {str(e)}")
        
        # 実行詳細を設定（Slack通知に含まれる）
        self.set_execution_detail("取得対象通貨ペア", len(self.currency_pairs))
        self.set_execution_detail("取得成功", saved_count)
        self.set_execution_detail("取得失敗", error_count)
        
        # コミットは基底クラスで行われる
        self.logger.info(f"Successfully saved {saved_count} forex rates")
        return {"saved_count": saved_count, "error_count": error_count}
    
    def _fetch_rate_from_api(self, currency_pair: str) -> dict:
        """
        外部APIから為替レートを取得（モック実装）
        実際の実装では、ここで外部APIを呼び出す
        """
        # ベースレートの設定
        base_rates = {
            "USD/JPY": 150.0,
            "EUR/USD": 1.08,
            "GBP/USD": 1.27,
            "EUR/JPY": 162.0
        }
        
        base_rate = base_rates.get(currency_pair, 100.0)
        
        # ランダムな変動を追加（±1%）
        rate = base_rate * (1 + random.uniform(-0.01, 0.01))
        spread = rate * 0.0001  # 0.01%のスプレッド
        
        return {
            "rate": round(rate, 4),
            "bid": round(rate - spread, 4),
            "ask": round(rate + spread, 4),
            "volume": round(random.uniform(1000000, 10000000), 2)
        }