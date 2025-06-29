"""
ベースリポジトリクラス
共通のCRUD操作を提供
"""

from typing import Type, TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """ベースリポジトリクラス"""
    
    def __init__(self, model: Type[ModelType], session: Session):
        self.model = model
        self.session = session
    
    def create(self, **kwargs) -> ModelType:
        """エンティティを作成"""
        obj = self.model(**kwargs)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def get_by_id(self, id: Any) -> Optional[ModelType]:
        """IDでエンティティを取得"""
        return self.session.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """全エンティティを取得"""
        return self.session.query(self.model).offset(offset).limit(limit).all()
    
    def update(self, obj: ModelType, **kwargs) -> ModelType:
        """エンティティを更新"""
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        self.session.commit()
        self.session.refresh(obj)
        return obj
    
    def delete(self, obj: ModelType) -> bool:
        """エンティティを削除"""
        try:
            self.session.delete(obj)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False
    
    def delete_by_id(self, id: Any) -> bool:
        """IDでエンティティを削除"""
        obj = self.get_by_id(id)
        if obj:
            return self.delete(obj)
        return False
    
    def find_by_criteria(self, **criteria) -> List[ModelType]:
        """条件でエンティティを検索"""
        query = self.session.query(self.model)
        
        for key, value in criteria.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        return query.all()
    
    def exists(self, **criteria) -> bool:
        """エンティティの存在確認"""
        query = self.session.query(self.model)
        
        for key, value in criteria.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        return query.first() is not None
    
    def count(self, **criteria) -> int:
        """エンティティの件数を取得"""
        query = self.session.query(self.model)
        
        for key, value in criteria.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        return query.count()
    
    def bulk_create(self, objects: List[Dict[str, Any]]) -> List[ModelType]:
        """複数エンティティの一括作成"""
        created_objects = []
        
        try:
            for obj_data in objects:
                obj = self.model(**obj_data)
                self.session.add(obj)
                created_objects.append(obj)
            
            self.session.commit()
            
            for obj in created_objects:
                self.session.refresh(obj)
                
            return created_objects
            
        except IntegrityError:
            self.session.rollback()
            raise
    
    def bulk_update(self, updates: List[Dict[str, Any]], id_field: str = 'id') -> int:
        """複数エンティティの一括更新"""
        try:
            updated_count = 0
            
            for update_data in updates:
                if id_field not in update_data:
                    continue
                
                id_value = update_data.pop(id_field)
                result = self.session.query(self.model).filter(
                    getattr(self.model, id_field) == id_value
                ).update(update_data)
                
                updated_count += result
            
            self.session.commit()
            return updated_count
            
        except Exception:
            self.session.rollback()
            raise