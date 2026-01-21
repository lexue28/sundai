import os
import json
from datetime import datetime
from pathlib import Path
from models import PostFeedback


class FeedbackStorage:
    """Simple JSON-based storage for post feedback."""
    
    def __init__(self, storage_file: str = "feedback.json"):
        self.storage_file = Path(storage_file)
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
        
        print(f"📝 Feedback stored: {rejection_reason}")
    
    def get_all_feedback(self) -> list[PostFeedback]:
        """Retrieve all stored feedback."""
        with open(self.storage_file, 'r') as f:
            feedback_list = json.load(f)
        
        return [PostFeedback(**item) for item in feedback_list]
