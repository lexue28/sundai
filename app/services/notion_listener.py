"""
Notion API listener for auto-creating posts when Notion docs are edited.

Uses polling to check for changes in Notion pages.
"""
import os
import time
import hashlib
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from app.clients.notion import NotionClient
from app.services.rag import embed_notion_page, db
from app.clients.llm_client import LLMClient
from app.services.topic_cycler import get_topic_cycler
from app.services.feedback_storage import FeedbackStorage
from app.utils.paths import state_path

load_dotenv()


class NotionListener:
    """Listens for changes in Notion pages and triggers post creation."""
    
    def __init__(self, notion_page_url: str, poll_interval: int = 60):
        """
        Initialize the Notion listener.
        
        Args:
            notion_page_url: URL of the Notion page to monitor
            poll_interval: How often to check for changes (seconds, default: 60 = 1 minute)
        """
        self.notion_page_url = notion_page_url
        self.poll_interval = poll_interval
        self.notion_client = NotionClient()
        self.last_content_hash = None
        self.state_file = state_path("notion_listener_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_history = []  # Store recent log entries
        self.max_log_history = 100  # Keep last 100 log entries
        self.last_change_time = None
        self.change_count = 0
        
        # Load last known state
        self._load_state()
    
    def _load_state(self):
        """Load the last known content hash from disk."""
        if os.path.exists(self.state_file):
            try:
                import json
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_content_hash = state.get('last_content_hash')
            except Exception as e:
                pass
    
    def _save_state(self):
        """Save the current content hash to disk."""
        try:
            import json
            with open(self.state_file, 'w') as f:
                json.dump({
                    'last_content_hash': self.last_content_hash,
                    'last_check': datetime.now().isoformat()
                }, f)
        except Exception as e:
            pass
    
    def _get_content_hash(self, content: str) -> str:
        """Generate a hash of the content to detect changes."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _add_log(self, message: str, level: str = "info"):
        """Add a log entry to history."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }
        self.log_history.append(log_entry)
        # Keep only last N entries
        if len(self.log_history) > self.max_log_history:
            self.log_history = self.log_history[-self.max_log_history:]
    
    def check_for_changes(self) -> bool:
        """
        Check if the Notion page has been updated.
        
        Returns:
            True if content has changed, False otherwise
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_msg = f"[{timestamp}] 🔍 Checking Notion page for changes..."
            self._add_log(log_msg, "info")
            
            content = self.notion_client.get_page_as_text(self.notion_page_url)
            current_hash = self._get_content_hash(content)
            
            if self.last_content_hash is None:
                # First run - just save the hash
                log_msg = f"First check - saving baseline (hash: {current_hash[:8]}...)"
                self._add_log(log_msg, "info")
                self.last_content_hash = current_hash
                self._save_state()
                return False
            
            if current_hash != self.last_content_hash:
                self.change_count += 1
                self.last_change_time = datetime.now().isoformat()
                log_msg = f"(hash changed: {self.last_content_hash[:8]}... → {current_hash[:8]}...)"
                self._add_log(log_msg, "change")
                self.last_content_hash = current_hash
                self._save_state()
                return True
            else:
                log_msg = f"No changes (hash: {current_hash[:8]}...)"
                self._add_log(log_msg, "info")
                return False
                
        except Exception as e:
            error_msg = f"Error checking for changes: {e}"
            self._add_log(error_msg, "error")
            return False
    
    def handle_page_update(self) -> Optional[str]:
        """
        Handle a page update: re-embed the page and create a new post.
        
        Returns:
            Generated post content, or None if failed
        """
        
        try:
            # Re-embed the updated page
            chunks_saved = embed_notion_page(db, self.notion_page_url)
            
            # Generate a new post
            llm_client = LLMClient()
            feedback_storage = FeedbackStorage()
            past_feedback = feedback_storage.get_all_feedback()
            
            # Get next topic from cycler
            topic_cycler = get_topic_cycler()
            topic = topic_cycler.get_next_topic()
            
            # Generate post with RAG
            post = llm_client.generate_promotional_post(
                use_rag=True,
                rag_query=topic,
                topic=topic,
                feedback_list=past_feedback,
                max_length=500
            )
            
            
            return post
            
        except Exception as e:
            return None
    
    def _listen_loop(self, auto_post: bool = False):
        """
        Internal listening loop (runs in background thread).
        
        Args:
            auto_post: If True, automatically create and post when changes detected
                      If False, just generate and return the post for manual approval
        """
        try:
            while True:
                if self.check_for_changes():
                    self.handle_page_update()
                
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            return
        except Exception as e:
            return
    
    def start_listening(self, auto_post: bool = False):
        """
        Start listening for changes (polling loop) - blocking version.
        
        Args:
            auto_post: If True, automatically create and post when changes detected
                      If False, just generate and return the post for manual approval
        """
        
        self._listen_loop(auto_post)
    
    def start_listening_background(self, auto_post: bool = False):
        """
        Start listening in a background thread (non-blocking).
        
        Args:
            auto_post: If True, automatically create and post when changes detected
                      If False, just generate and return the post for manual approval
        
        Returns:
            Thread object (can be used to stop it later)
        """
        import threading

        thread = threading.Thread(
            target=self._listen_loop,
            args=(auto_post,),
            daemon=True,  # Dies when main program exits
            name="NotionListener"
        )
        thread.start()
        return thread


def main():
    """Main entry point for the listener."""
    import sys
    
    notion_page_url = os.getenv(
        "NOTION_PAGE_URL",
        "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
    )
    
    poll_interval = int(os.getenv("NOTION_POLL_INTERVAL", "60"))  # 1 minute default
    auto_post = os.getenv("NOTION_AUTO_POST", "false").lower() == "true"
    
    listener = NotionListener(notion_page_url, poll_interval)
    listener.start_listening(auto_post=auto_post)


if __name__ == "__main__":
    main()
