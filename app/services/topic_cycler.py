"""
Topic cycler for SF Tech Bro stereotypes.
Cycles through a list of topics to keep posts varied.
"""
import json
import os
from pathlib import Path
from typing import List
from app.utils.paths import state_path

# SF Tech Bro stereotypes
SF_TECH_BRO_TOPICS = [
    "Stealth startups, constant pivots",
    "AI-powered everything",
    "LLM wrappers, AGI takes",
    "Prompt engineering flex",
    "YC name-dropping",
    "Move fast philosophy",
    "Anti-regulation hot takes",
    "Kubernetes for 5 users",
    "Rust rewrites for vibes",
    "Dark mode discourse",
    "Patagonia vest uniform",
    "Cold plunges, biohacking",
    "Equity > salary cope",
    "Crypto cycles explained badly",
    "Mars > Earth priorities",
    "Longevity startups",
    "Founders are built different",
    "This could be a unicorn"
]


class TopicCycler:
    """Cycles through topics, persisting state to disk."""
    
    def __init__(self, state_file: str = None):
        self.state_file = Path(state_file) if state_file else state_path("topic_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.topics = SF_TECH_BRO_TOPICS.copy()
        self.current_index = self._load_state()
    
    def _load_state(self) -> int:
        """Load the current topic index from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    index = state.get('current_index', 0)
                    # Ensure index is valid
                    return index % len(self.topics)
            except Exception as e:
                return 0
        return 0
    
    def _save_state(self):
        """Save the current topic index to disk."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({'current_index': self.current_index}, f)
        except Exception as e:
            pass
    
    def get_next_topic(self) -> str:
        """Get the next topic and advance the index."""
        topic = self.topics[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.topics)
        self._save_state()
        return topic
    
    def get_current_topic(self) -> str:
        """Get the current topic without advancing."""
        return self.topics[self.current_index]
    
    def reset(self):
        """Reset to the first topic."""
        self.current_index = 0
        self._save_state()


# Global instance
_topic_cycler = None

def get_topic_cycler() -> TopicCycler:
    """Get the global topic cycler instance."""
    global _topic_cycler
    if _topic_cycler is None:
        _topic_cycler = TopicCycler()
    return _topic_cycler
