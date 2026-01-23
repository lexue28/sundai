"""
Test script to verify all 4 parts are integrated and working:
1. Notion API integration
2. Chunking and SQLite storage
3. Hybrid search RAG retrieval
4. Notion listener for auto-posting
"""
import os
from dotenv import load_dotenv
from RAG import embed_notion_pages, retrieve_context, db
from llm_client import LLMClient
from topic_cycler import get_topic_cycler
from notion_listener import NotionListener

load_dotenv()


def test_part1_notion_api():
    """Test Part 1: Notion API integration"""
    print("\n" + "="*60)
    print("TESTING PART 1: Notion API Integration")
    print("="*60)
    
    try:
        from notion import NotionClient
        notion_client = NotionClient()
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        content = notion_client.get_page_as_text(notion_page_url)
        print(f"✅ Notion API working - fetched {len(content)} characters")
        return True
    except Exception as e:
        print(f"❌ Notion API failed: {e}")
        return False


def test_part2_chunking_sqlite():
    """Test Part 2: Chunking and SQLite storage"""
    print("\n" + "="*60)
    print("TESTING PART 2: Chunking and SQLite Storage")
    print("="*60)
    
    try:
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        total_chunks = embed_notion_pages(db, [notion_page_url])
        print(f"✅ Chunking and SQLite storage working - saved {total_chunks} chunks")
        return True
    except Exception as e:
        print(f"❌ Chunking/SQLite failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def test_part3_rag_retrieval():
    """Test Part 3: Hybrid search RAG retrieval"""
    print("\n" + "="*60)
    print("TESTING PART 3: Hybrid Search RAG Retrieval")
    print("="*60)
    
    try:
        # Test RAG retrieval
        query = "freelance developer coding projects"
        context, results = retrieve_context(db, query, top_k=3)
        print(f"✅ RAG retrieval working - found {len(results)} results, {len(context)} chars context")
        
        # Test LLM client with RAG
        llm_client = LLMClient()
        topic_cycler = get_topic_cycler()
        topic = topic_cycler.get_current_topic()  # Don't advance, just test
        
        post = llm_client.generate_promotional_post(
            use_rag=True,
            rag_query="freelance developer coding projects",
            topic=topic,
            max_length=500
        )
        print(f"✅ Post generation with RAG working - generated {len(post)} chars")
        print(f"   Preview: {post[:100]}...")
        return True
    except Exception as e:
        print(f"❌ RAG retrieval failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def test_part4_notion_listener():
    """Test Part 4: Notion listener setup"""
    print("\n" + "="*60)
    print("TESTING PART 4: Notion Listener")
    print("="*60)
    
    try:
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        listener = NotionListener(notion_page_url, poll_interval=60)
        
        # Test change detection (should return False on first run)
        has_changes = listener.check_for_changes()
        print(f"✅ Notion listener working - change detection: {has_changes}")
        print(f"   (First run will always return False - this is expected)")
        return True
    except Exception as e:
        print(f"❌ Notion listener failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def main():
    """Run all integration tests"""
    print("\n" + "="*60)
    print("SUNDAI INTEGRATION TEST")
    print("="*60)
    print("\nTesting all 4 parts of the system...")
    
    results = {
        "Part 1: Notion API": test_part1_notion_api(),
        "Part 2: Chunking & SQLite": test_part2_chunking_sqlite(),
        "Part 3: RAG Retrieval": test_part3_rag_retrieval(),
        "Part 4: Notion Listener": test_part4_notion_listener(),
    }
    
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    for part, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{part}: {status}")
    
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED - System is ready!")
    else:
        print("❌ SOME TESTS FAILED - Check errors above")
    print("="*60)
    
    return all_passed


if __name__ == "__main__":
    main()
