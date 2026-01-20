import os
from dotenv import load_dotenv
from notion import NotionClient
from mastadon import MastodonClient
from llm_client import LLMClient

load_dotenv()


def main():
    notion_page_url = "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
    business_keyword = os.getenv('BUSINESS_KEYWORD', 'workshop')
    
    notion_context = None
    try:
        notion_client = NotionClient()
        notion_context = notion_client.get_page_as_text(notion_page_url)
        print(f"\n{'='*60}")
        print("NOTION PAGE CONTENT:")
        print('='*60)
        print(notion_context)
        print('='*60 + "\n")
    except Exception as e:
        print(f"Error fetching from Notion: {e}")
    
    # Generate and post promotional post about fullstack abilities
    try:
        mastodon_client = MastodonClient()
        llm_client = LLMClient()
        
        print(f"\n{'='*60}")
        print("GENERATING PROMOTIONAL POST:")
        print('='*60)
        
        promotional_post = llm_client.generate_promotional_post(
            notion_context=notion_context,
            max_length=500
        )
        
        print(f"\nGenerated post ({len(promotional_post)} characters):")
        print(promotional_post)
        print('='*60 + "\n")
        
        if not promotional_post or len(promotional_post.strip()) == 0:
            print("[ERROR] Cannot post empty content! Skipping post.")
            return
        
        print(f"[DEBUG] Attempting to post to Mastodon...")
        print(f"[DEBUG] Post length: {len(promotional_post)}")
        print(f"[DEBUG] Post preview: {promotional_post[:100]}...")
        
        try:
            result = mastodon_client.post_status(
                status=promotional_post,
                visibility='public'
            )
            print(f"✓ Posted promotional post: {result.get('url')}\n")
        except Exception as post_error:
            print(f"[ERROR] Mastodon posting error: {type(post_error).__name__}: {post_error}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise
        
    except Exception as e:
        print(f"Error posting promotional content: {e}\n")
    
    # # Generate and post replies to keyword searches
    # try:
    #     mastodon_client = MastodonClient()
    #     recent_posts = mastodon_client.get_recent_posts_by_keyword(business_keyword, limit=5)
    #     
    #     if not recent_posts:
    #         print(f"No posts found for keyword: {business_keyword}")
    #         return
    #     
    #     llm_client = LLMClient()
    #     reply_batch = llm_client.generate_replies(
    #         posts=recent_posts,
    #         notion_context=notion_context,
    #         tone='professional',
    #         max_length=500
    #     )
    #     
    #     print(f"\n{'='*60}")
    #     print("OPENROUTER GENERATED REPLIES:")
    #     print('='*60)
    #     for i, reply in enumerate(reply_batch.replies, 1):
    #         print(f"\nReply {i}:")
    #         print(f"  Post ID to reply to: {reply.post_id}")
    #         print(f"  Reply text: {reply.status}")
    #         print(f"  Visibility: {reply.visibility}")
    #         print(f"  Length: {len(reply.status)} characters")
    #     print('='*60 + "\n")
    #     
    #     for reply in reply_batch.replies:
    #         try:
    #             result = mastodon_client.post_status(
    #                 status=reply.status,
    #                 visibility=reply.visibility,
    #                 in_reply_to_id=reply.post_id
    #             )
    #             print(f"Posted reply to {reply.post_id}: {result.get('url')}")
    #         except Exception as e:
    #             print(f"Error posting reply to {reply.post_id}: {e}")
    # 
    # except Exception as e:
    #     print(f"Error: {e}")


if __name__ == "__main__":
    main()
