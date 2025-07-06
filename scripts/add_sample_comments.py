#!/usr/bin/env python
"""
Script to add sample comment data to existing forecasts in the database.
This demonstrates the hierarchical comment structure with replies.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.forecast import ForecastRequest, ForecastComment
from app.core.config import settings
import random
import json

# Create database connection
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def add_sample_comments():
    """Add sample comments with various types and reply structures"""
    db = SessionLocal()
    
    try:
        # Get all existing forecasts
        forecasts = db.query(ForecastRequest).all()
        
        if not forecasts:
            print("No forecasts found in database. Please create some forecasts first.")
            return
        
        print(f"Found {len(forecasts)} forecasts. Adding sample comments...")
        
        # Sample comments data
        sample_questions = [
            {
                "content": "このサポートラインは本当に有効でしょうか？過去のデータではどの程度機能していますか？",
                "answer": "過去3ヶ月のデータを見ると、このサポートラインは4回テストされ、3回は反発しています。特に直近の2回は強い反発を示しており、有効性は高いと判断できます。ただし、ファンダメンタルズの急変には注意が必要です。"
            },
            {
                "content": "現在のボリュームインジケーターから、トレンドの継続性についてどう判断されますか？",
                "answer": "ボリュームは上昇トレンドと共に増加しており、これは健全なトレンドの兆候です。特に直近のブレイクアウト時のボリュームスパイクは、機関投資家の参入を示唆しています。ただし、RSIが70を超えているため、短期的な調整の可能性も考慮すべきです。"
            },
            {
                "content": "MACDのダイバージェンスが見られますが、これをどう解釈すべきでしょうか？",
                "answer": "確かにMACDと価格の間に弱気ダイバージェンスが形成されています。これは上昇モメンタムの減速を示しており、トレンド転換の早期警告信号の可能性があります。ただし、ダイバージェンスだけでエントリーするのは危険です。価格アクションの確認を待つことをお勧めします。"
            }
        ]
        
        sample_notes = [
            "重要な経済指標発表が明日予定されています。ポジションサイズに注意。",
            "このパターンは教科書的なヘッドアンドショルダーの形成過程に見えます。ネックラインに注目。",
            "前回の分析から状況が変化しました。トレンドラインのブレイクを確認。",
            "ボリュームプロファイルから、1.3500付近に強い売り圧力があることが分かります。"
        ]
        
        sample_replies = [
            "なるほど、その視点は考慮していませんでした。ありがとうございます。",
            "追加の分析をありがとうございます。とても参考になります。",
            "その通りですね。リスク管理の観点からも重要なポイントです。",
            "確かにそのレベルは重要そうです。ウォッチリストに追加します。"
        ]
        
        # Add comments to each forecast
        for i, forecast in enumerate(forecasts[:3]):  # Limit to first 3 forecasts for demo
            print(f"\nAdding comments to forecast {forecast.id} ({forecast.currency_pair})...")
            
            # Add 1-2 questions with AI answers
            num_questions = random.randint(1, 2)
            for j in range(num_questions):
                question_data = random.choice(sample_questions)
                
                # Create question
                question = ForecastComment(
                    forecast_id=forecast.id,
                    parent_comment_id=None,
                    comment_type="question",
                    content=question_data["content"],
                    author="User",
                    is_ai_response=False,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 7))
                )
                db.add(question)
                db.flush()  # Get the ID
                
                # Create AI answer
                answer = ForecastComment(
                    forecast_id=forecast.id,
                    parent_comment_id=question.id,
                    comment_type="answer",
                    content=question_data["answer"],
                    author="AI Assistant",
                    is_ai_response=True,
                    extra_metadata={
                        "confidence": random.choice(["high", "medium", "low"]),
                        "reasoning": "Based on technical analysis and historical patterns"
                    },
                    created_at=question.created_at + timedelta(minutes=random.randint(1, 5))
                )
                db.add(answer)
                
                # Maybe add a follow-up reply to the answer
                if random.random() > 0.5:
                    reply = ForecastComment(
                        forecast_id=forecast.id,
                        parent_comment_id=answer.id,
                        comment_type="note",
                        content=random.choice(sample_replies),
                        author="User",
                        is_ai_response=False,
                        created_at=answer.created_at + timedelta(minutes=random.randint(10, 30))
                    )
                    db.add(reply)
            
            # Add 1-2 standalone notes
            num_notes = random.randint(1, 2)
            for j in range(num_notes):
                note = ForecastComment(
                    forecast_id=forecast.id,
                    parent_comment_id=None,
                    comment_type="note",
                    content=random.choice(sample_notes),
                    author="User",
                    is_ai_response=False,
                    extra_metadata={
                        "importance": random.choice(["high", "medium", "low"])
                    },
                    created_at=datetime.utcnow() - timedelta(days=random.randint(0, 5))
                )
                db.add(note)
                db.flush()
                
                # Maybe add replies to notes
                if random.random() > 0.7:
                    num_replies = random.randint(1, 2)
                    for k in range(num_replies):
                        reply = ForecastComment(
                            forecast_id=forecast.id,
                            parent_comment_id=note.id,
                            comment_type="note",
                            content=random.choice(sample_replies),
                            author=random.choice(["User", "Another User"]),
                            is_ai_response=False,
                            created_at=note.created_at + timedelta(hours=random.randint(1, 24))
                        )
                        db.add(reply)
        
        # Commit all changes
        db.commit()
        print("\nSample comments added successfully!")
        
        # Show summary
        total_comments = db.query(ForecastComment).count()
        questions = db.query(ForecastComment).filter(ForecastComment.comment_type == "question").count()
        answers = db.query(ForecastComment).filter(ForecastComment.comment_type == "answer").count()
        notes = db.query(ForecastComment).filter(ForecastComment.comment_type == "note").count()
        
        print(f"\nComment summary:")
        print(f"- Total comments: {total_comments}")
        print(f"- Questions: {questions}")
        print(f"- Answers: {answers}")
        print(f"- Notes: {notes}")
        
    except Exception as e:
        print(f"Error adding sample comments: {e}")
        db.rollback()
    finally:
        db.close()


def show_comment_structure():
    """Display the comment structure for verification"""
    db = SessionLocal()
    
    try:
        # Get forecasts with comments
        forecasts = db.query(ForecastRequest).join(ForecastComment).distinct().all()
        
        for forecast in forecasts:
            print(f"\n{'='*60}")
            print(f"Forecast {forecast.id}: {forecast.currency_pair}")
            print(f"{'='*60}")
            
            # Get root comments (no parent)
            root_comments = db.query(ForecastComment).filter(
                ForecastComment.forecast_id == forecast.id,
                ForecastComment.parent_comment_id == None
            ).order_by(ForecastComment.created_at).all()
            
            for comment in root_comments:
                print_comment_tree(comment, db, level=0)
    
    finally:
        db.close()


def print_comment_tree(comment, db, level=0):
    """Recursively print comment tree structure"""
    indent = "  " * level
    type_emoji = {"question": "❓", "answer": "💡", "note": "📝"}.get(comment.comment_type, "")
    ai_marker = "🤖" if comment.is_ai_response else "👤"
    
    print(f"{indent}{type_emoji} {ai_marker} [{comment.comment_type}] {comment.author}")
    print(f"{indent}   {comment.content[:80]}{'...' if len(comment.content) > 80 else ''}")
    print(f"{indent}   Created: {comment.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    # Get replies
    replies = db.query(ForecastComment).filter(
        ForecastComment.parent_comment_id == comment.id
    ).order_by(ForecastComment.created_at).all()
    
    for reply in replies:
        print_comment_tree(reply, db, level + 1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Add sample comments to forecasts")
    parser.add_argument("--show", action="store_true", help="Show comment structure")
    args = parser.parse_args()
    
    if args.show:
        show_comment_structure()
    else:
        add_sample_comments()
        print("\nShowing comment structure:")
        show_comment_structure()