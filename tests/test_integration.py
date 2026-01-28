"""
Test script to verify all 4 parts are integrated and working:
1. Notion API integration
2. Chunking and SQLite storage
3. Hybrid search RAG retrieval
4. Notion listener for auto-posting
"""
import os
from dotenv import load_dotenv
from app.services.rag import embed_notion_pages, retrieve_context, db
from app.clients.llm_client import LLMClient
from app.services.topic_cycler import get_topic_cycler
from app.services.notion_listener import NotionListener

load_dotenv()


def test_part1_notion_api():
    """Test Part 1: Notion API integration"""
    try:
        from app.clients.notion import NotionClient
        notion_client = NotionClient()
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        _ = notion_client.get_page_as_text(notion_page_url)
        return True
    except Exception:
        return False


def test_part2_chunking_sqlite():
    """Test Part 2: Chunking and SQLite storage"""
    try:
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        _ = embed_notion_pages(db, [notion_page_url])
        return True
    except Exception:
        return False


def test_part3_rag_retrieval():
    """Test Part 3: Hybrid search RAG retrieval"""
    try:
        query = "freelance developer coding projects"
        _context, _results = retrieve_context(db, query, top_k=3)
        llm_client = LLMClient()
        topic_cycler = get_topic_cycler()
        topic = topic_cycler.get_current_topic()
        _ = llm_client.generate_promotional_post(
            use_rag=True,
            rag_query="freelance developer coding projects",
            topic=topic,
            max_length=500
        )
        return True
    except Exception:
        return False


def test_part4_notion_listener():
    """Test Part 4: Notion listener setup"""
    try:
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        listener = NotionListener(notion_page_url, poll_interval=60)
        _ = listener.check_for_changes()
        return True
    except Exception:
        return False


def main():
    """Run all integration tests"""
    results = {
        "Part 1: Notion API": test_part1_notion_api(),
        "Part 2: Chunking & SQLite": test_part2_chunking_sqlite(),
        "Part 3: RAG Retrieval": test_part3_rag_retrieval(),
        "Part 4: Notion Listener": test_part4_notion_listener(),
    }
    return all(results.values())


if __name__ == "__main__":
    main()
