"""
Notion API listener for auto-creating posts when Notion docs are edited.

Uses polling to check for changes in Notion pages.
"""
import os
import time
import hashlib
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv
from notion import NotionClient
from RAG import embed_notion_page, db
from llm_client import LLMClient
from topic_cycler import get_topic_cycler
from feedback_storage import FeedbackStorage

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
        self.state_file = ".notion_listener_state.json"
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
                print(f"Error loading listener state: {e}")
    
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
            print(f"Error saving listener state: {e}")
    
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
            print(f"\n{log_msg}")
            self._add_log(log_msg, "info")
            
            content = self.notion_client.get_page_as_text(self.notion_page_url)
            current_hash = self._get_content_hash(content)
            
            if self.last_content_hash is None:
                # First run - just save the hash
                log_msg = f"  📌 First check - saving baseline (hash: {current_hash[:8]}...)"
                print(log_msg)
                self._add_log(log_msg, "info")
                self.last_content_hash = current_hash
                self._save_state()
                return False
            
            if current_hash != self.last_content_hash:
                self.change_count += 1
                self.last_change_time = datetime.now().isoformat()
                log_msg = f"  ✅ CHANGE DETECTED! (hash changed: {self.last_content_hash[:8]}... → {current_hash[:8]}...)"
                print(log_msg)
                self._add_log(log_msg, "change")
                print(f"  🎉 This is change #{self.change_count} detected!")
                self.last_content_hash = current_hash
                self._save_state()
                return True
            else:
                log_msg = f"  ✓ No changes (hash: {current_hash[:8]}...)"
                print(log_msg)
                self._add_log(log_msg, "info")
                return False
                
        except Exception as e:
            error_msg = f"  ❌ Error checking for changes: {e}"
            print(error_msg)
            self._add_log(error_msg, "error")
            import traceback
            print(traceback.format_exc())
            return False
    
    def handle_page_update(self) -> Optional[str]:
        """
        Handle a page update: re-embed the page and create a new post.
        
        Returns:
            Generated post content, or None if failed
        """
        print(f"\n{'='*60}")
        print("HANDLING NOTION PAGE UPDATE")
        print('='*60)
        
        try:
            # Re-embed the updated page
            print("Re-embedding updated Notion page...")
            chunks_saved = embed_notion_page(db, self.notion_page_url)
            print(f"Saved {chunks_saved} chunks to database")
            
            # Generate a new post
            print("\nGenerating new post...")
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
            
            print(f"\n✅ Generated post ({len(post)} characters):")
            print(post)
            print('='*60)
            
            return post
            
        except Exception as e:
            print(f"❌ Error handling page update: {e}")
            import traceback
            print(traceback.format_exc())
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
                    print(f"\n🔔 NOTION PAGE UPDATED - Starting workflow...")
                    post = self.handle_page_update()
                    if post:
                        print(f"\n✅ Post generated successfully!")
                        if auto_post:
                            # Auto-post logic would go here
                            # For now, we'll just generate and return
                            print("\n⚠️  Auto-post is enabled but not fully implemented.")
                            print("   Post generated but not automatically posted.")
                            print("   Use main.py for full posting workflow with approval.")
                        else:
                            print(f"\n📝 Generated post (not auto-posting):")
                            print(f"   {post[:200]}...")
                            print(f"\n💡 To post this, run: python main.py")
                    else:
                        print(f"\n❌ Failed to generate post from Notion update")
                
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\n\n[Listener] Stopping...")
        except Exception as e:
            print(f"\n[Listener] Error in listening loop: {e}")
            import traceback
            print(traceback.format_exc())
    
    def start_listening(self, auto_post: bool = False):
        """
        Start listening for changes (polling loop) - blocking version.
        
        Args:
            auto_post: If True, automatically create and post when changes detected
                      If False, just generate and return the post for manual approval
        """
        print(f"\n{'='*60}")
        print("STARTING NOTION LISTENER")
        print('='*60)
        print(f"Monitoring: {self.notion_page_url}")
        print(f"Poll interval: {self.poll_interval} seconds ({self.poll_interval/60:.1f} minutes)")
        print(f"Auto-post: {auto_post}")
        print('='*60)
        print("\nPress Ctrl+C to stop\n")
        
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
        
        print(f"\n{'='*60}")
        print("STARTING NOTION LISTENER (BACKGROUND)")
        print('='*60)
        print(f"Monitoring: {self.notion_page_url}")
        print(f"Poll interval: {self.poll_interval} seconds ({self.poll_interval/60:.1f} minutes)")
        print(f"Auto-post: {auto_post}")
        print(f"Running in background thread...")
        print('='*60)
        
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
