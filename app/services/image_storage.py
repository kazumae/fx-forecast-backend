"""Image storage service for saving chart images"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Tuple
import shutil
from app.utils.timezone import get_jst_now


class ImageStorageService:
    def __init__(self):
        self.base_path = Path("/app/data/images")
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure image storage directories exist"""
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def generate_filename(self, timeframe: str, original_filename: str) -> str:
        """Generate unique filename for storing image"""
        timestamp = get_jst_now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        extension = Path(original_filename).suffix or ".jpg"
        return f"{timestamp}_{timeframe}_{unique_id}{extension}"
    
    def save_image(self, image_data: bytes, timeframe: str, original_filename: str) -> Tuple[str, str, int]:
        """
        Save image to disk and return (filename, file_path, file_size)
        """
        # Create year/month subdirectory
        now = get_jst_now()
        sub_dir = self.base_path / f"{now.year:04d}" / f"{now.month:02d}"
        sub_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = self.generate_filename(timeframe, original_filename)
        file_path = sub_dir / filename
        
        # Save file
        with open(file_path, 'wb') as f:
            f.write(image_data)
        
        # Get relative path from base directory
        relative_path = str(file_path.relative_to(Path("/app")))
        
        return filename, relative_path, len(image_data)
    
    def get_image_path(self, relative_path: str) -> Path:
        """Get absolute path for serving image"""
        return Path("/app") / relative_path
    
    def delete_forecast_images(self, forecast_id: int, image_paths: list[str]):
        """Delete images associated with a forecast"""
        for path in image_paths:
            full_path = Path("/app") / path
            if full_path.exists():
                try:
                    full_path.unlink()
                except Exception:
                    pass  # Ignore errors when deleting


def save_uploaded_image(image_data: bytes, filename: str, subdirectory: str = None) -> str:
    """
    Save uploaded image to disk
    
    Args:
        image_data: Binary image data
        filename: Desired filename
        subdirectory: Optional subdirectory under images folder
    
    Returns:
        Relative path to saved image
    """
    base_path = Path("/app/data/images")
    
    # Create year/month subdirectory
    now = datetime.now()
    date_path = f"{now.year:04d}/{now.month:02d}"
    
    if subdirectory:
        full_path = base_path / subdirectory / date_path
    else:
        full_path = base_path / date_path
    
    full_path.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = full_path / filename
    with open(file_path, 'wb') as f:
        f.write(image_data)
    
    # Return relative path from data directory
    return str(file_path.relative_to(Path("/app")))