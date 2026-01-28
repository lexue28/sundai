import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
from app.models.schemas import PostFeedback
from app.utils.paths import data_path


class FeedbackStorage:
    """Simple JSON-based storage for post feedback."""
    
    def __init__(self, storage_file: Optional[Union[str, Path]] = None):
        self.storage_file = Path(storage_file) if storage_file else data_path("feedback.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_storage_file()
    
    def _ensure_storage_file(self):
        """Create storage file if it doesn't exist."""
        if not self.storage_file.exists():
            with open(self.storage_file, 'w') as f:
                json.dump([], f)
    
    def store_feedback(self, post_content: str, rejection_reason: str):
        """Store feedback for a rejected post."""
        feedback = PostFeedback(
            post_content=post_content,
            rejection_reason=rejection_reason,
            timestamp=datetime.now().isoformat()
        )
        
        # Read existing feedback
        with open(self.storage_file, 'r') as f:
            feedback_list = json.load(f)
        
        # Add new feedback
        feedback_list.append(feedback.model_dump())
        
        # Write back
        with open(self.storage_file, 'w') as f:
            json.dump(feedback_list, f, indent=2)
        
    
    def get_all_feedback(self) -> list[PostFeedback]:
        """Retrieve all stored feedback."""
        with open(self.storage_file, 'r') as f:
            feedback_list = json.load(f)
        
        return [PostFeedback(**item) for item in feedback_list]
