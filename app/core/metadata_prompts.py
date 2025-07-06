"""Prompts for extracting metadata from reviews"""

METADATA_EXTRACTION_PROMPT = """あなたはFX予測の検証結果からメタデータを抽出する専門家です。
以下の検証結果から、今後の予測に役立つ重要な情報を構造化して抽出してください。

【抽出するメタデータ】

1. **パターン分類**
   - 使用したかむかむ流ポイント（1-9）
   - 成功/失敗
   - 時間足の組み合わせ

2. **具体的な教訓**
   - 成功要因（最大3つ）
   - 失敗要因（最大3つ）
   - 注意すべき価格帯

3. **統計情報**
   - 方向性的中：○/×
   - エントリー精度：○/△/×
   - リスク管理精度：○/△/×
   - 総合スコア：X/100

4. **相場環境**
   - トレンド状態（上昇/下降/レンジ）
   - ボラティリティ（高/中/低）
   - 重要な価格帯

【出力フォーマット】
以下のJSON形式で出力してください：
```json
{
  "pattern": {
    "kamukamu_point": "ポイントX",
    "result": "success/failure",
    "timeframes_used": ["1分足", "15分足", "1時間足"]
  },
  "lessons": {
    "success_factors": [
      "成功要因1",
      "成功要因2"
    ],
    "failure_factors": [
      "失敗要因1",
      "失敗要因2"
    ],
    "caution_zones": ["3300-3350"]
  },
  "statistics": {
    "direction_accuracy": "○/×",
    "entry_accuracy": "○/△/×",
    "risk_management": "○/△/×",
    "total_score": 75
  },
  "market_context": {
    "trend": "上昇/下降/レンジ",
    "volatility": "高/中/低",
    "key_levels": ["3300", "3350"]
  },
  "key_takeaway": "最も重要な教訓を1文で"
}
```

【注意事項】
- 客観的な事実のみを抽出
- 感情的な表現は避ける
- 具体的な数値を含める
- 簡潔にまとめる
"""


def get_metadata_extraction_prompt(review_content: str) -> str:
    """Get prompt for metadata extraction from review"""
    return f"{METADATA_EXTRACTION_PROMPT}\n\n以下の検証結果からメタデータを抽出してください：\n\n{review_content}"