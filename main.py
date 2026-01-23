import os
import asyncio
import replicate
from dotenv import load_dotenv
from notion import NotionClient
from mastadon import MastodonClient
from llm_client import LLMClient
from telegram_client import TelegramClient
from feedback_storage import FeedbackStorage

load_dotenv()

# Verify Replicate API token is set
replicate_api_token = os.getenv('REPLICATE_API_TOKEN')
if not replicate_api_token:
    raise ValueError("REPLICATE_API_TOKEN not found in environment variables. Please add it to your .env file.")


def start_notion_listener_background():
    """Start the Notion listener in a background thread."""
    try:
        from notion_listener import NotionListener
        
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        poll_interval = int(os.getenv("NOTION_POLL_INTERVAL", "60"))  # 1 minute default
        auto_post = os.getenv("NOTION_AUTO_POST", "false").lower() == "true"
        
        listener = NotionListener(notion_page_url, poll_interval)
        thread = listener.start_listening_background(auto_post=auto_post)
        
        print("✅ Notion listener started in background")
        return listener, thread
    except Exception as e:
        print(f"⚠️  Could not start Notion listener: {e}")
        print("   Continuing without background monitoring...")
        return None, None


async def main():
    notion_page_url = "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
    business_keyword = os.getenv('BUSINESS_KEYWORD', 'workshop')
    
    # Start Notion listener in background (Part 4) - runs continuously
    listener, listener_thread = start_notion_listener_background()
    
    if listener:
        print("\n💡 Notion listener is running in the background.")
        print("   It will check for changes every 1 minute (or as configured).")
        print("   When changes are detected, it will print a notification and generate a post.")
        print("   Keep this process running to monitor Notion changes!\n")
    
    # Initialize RAG database with Notion content (Part 1 & 2)
    try:
        from RAG import embed_notion_pages, db
        print(f"\n{'='*60}")
        print("INITIALIZING RAG DATABASE:")
        print('='*60)
        print("Embedding Notion page into SQLite database...")
        chunks_saved = embed_notion_pages(db, [notion_page_url])
        if chunks_saved > 0:
            print(f"✅ Successfully embedded {chunks_saved} chunks into database")
        else:
            print("⚠️  No chunks saved - database may already be up to date")
    except Exception as e:
        print(f"⚠️  Error initializing RAG database: {e}")
        print("   Continuing with existing database if available...")
    
    # Generate and post promotional post using RAG (Part 3)
    try:
        mastodon_client = MastodonClient()
        llm_client = LLMClient()
        
        print(f"\n{'='*60}")
        print("GENERATING PROMOTIONAL POST WITH RAG:")
        print('='*60)
        
        # Load past feedback to improve future posts
        feedback_storage = FeedbackStorage()
        past_feedback = feedback_storage.get_all_feedback()
        if past_feedback:
            print(f"📚 Loaded {len(past_feedback)} past feedback items to improve post generation")
        
        # Generate post using RAG (automatically uses topic cycling)
        promotional_post = llm_client.generate_promotional_post(
            use_rag=True,  # Use RAG for context retrieval
            feedback_list=past_feedback,
            max_length=500
        )
        
        print(f"\nGenerated post ({len(promotional_post)} characters):")
        print(promotional_post)
        print('='*60 + "\n")
        
        if not promotional_post or len(promotional_post.strip()) == 0:
            print("[ERROR] Cannot post empty content! Skipping post.")
            return
        
        # Send for human approval via Telegram
        print(f"\n{'='*60}")
        print("SENDING FOR HUMAN APPROVAL:")
        print('='*60)
        telegram_client = TelegramClient()
        
        decision, rejection_reason = await telegram_client.wait_for_approval_with_feedback(promotional_post)
        
        if decision == "reject":
            # Store feedback if rejected
            if rejection_reason:
                feedback_storage.store_feedback(promotional_post, rejection_reason)
            else:
                feedback_storage.store_feedback(promotional_post, "No reason provided")
            print("❌ Post rejected. Feedback stored.")
            return
        
        if decision != "approve":
            print(f"[ERROR] Unexpected decision: {decision}. Skipping post.")
            return
        
        # Post was approved, proceed with publishing
        print("✅ Post approved. Proceeding with publishing...")
        
        # Generate image with Replicate
        print("Generating image with Replicate...")
        output = replicate.run(
            "sundai-club/linda_model:4e616b5b9ce6bb30d1be9fa2539ed6d98777ce306e42bfacffb561d199a88ec5",
            input={
                "prompt": """portrait photo of a young asian woman, female, 20s,
SUNDAI, the same woman from the training dataset,
freelance software engineer, computer science themed""",
                "model": "dev",
                "go_fast": False,
                "lora_scale": 0.5,
                "megapixels": "1",
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "webp",
                "guidance_scale": 10,
                "output_quality": 80,
                "prompt_strength": 0.8,
                "extra_lora_scale": 1,
                "num_inference_steps": 28
            }
        )
        
        print(f"Image generated: {output[0].url}")
        
        # Save image to disk
        image_path = "my-image.webp"
        with open(image_path, "wb") as file:
            file.write(output[0].read())
        print(f"Image saved to {image_path}")
        
        # Upload image to Mastodon
        print("Uploading image to Mastodon...")
        media_id = mastodon_client.upload_media(image_path)
        print(f"Image uploaded, media_id: {media_id}")
        
        print(f"[DEBUG] Attempting to post to Mastodon...")
        print(f"[DEBUG] Post length: {len(promotional_post)}")
        print(f"[DEBUG] Post preview: {promotional_post[:100]}...")
        
        try:
            result = mastodon_client.post_status(
                status=promotional_post,
                visibility='public',
                media_ids=[media_id]
            )
            print(f"✓ Posted promotional post with image: {result.get('url')}\n")
        except Exception as post_error:
            print(f"[ERROR] Mastodon posting error: {type(post_error).__name__}: {post_error}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            raise
        
    except Exception as e:
        print(f"Error posting promotional content: {e}\n")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
    
    # Keep the program running so the listener thread continues
    if listener:
        print(f"\n{'='*60}")
        print("MAIN WORKFLOW COMPLETE - LISTENER STILL RUNNING")
        print('='*60)
        print("The Notion listener is still monitoring for changes in the background.")
        print("Press Ctrl+C to stop both the listener and this program.")
        print('='*60 + "\n")
        
        # Keep the main thread alive so the daemon listener thread can continue
        try:
            heartbeat_count = 0
            while True:
                await asyncio.sleep(60)  # Sleep for 1 minute at a time
                heartbeat_count += 1
                # Print a heartbeat every 5 minutes to show it's still running
                if heartbeat_count % 5 == 0:  # Every 5 minutes (heartbeat, not check interval)
                    from datetime import datetime
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💓 Listener still running...")
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down...")
    
    # Generate and post replies to keyword searches
    # COMMENTED OUT - Replying functionality disabled
    # try:
    #     mastodon_client = MastodonClient()
    #     recent_posts = mastodon_client.get_recent_posts_by_keyword(business_keyword, limit=5)
        
    #     if not recent_posts:
    #         print(f"No posts found for keyword: {business_keyword}")
    #         return
        
    #     llm_client = LLMClient()
    #     reply_batch = llm_client.generate_replies(
    #         posts=recent_posts,
    #         notion_context=notion_context,
    #         tone='professional',
    #         max_length=500
    #     )
        
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


if __name__ == "__main__":
    asyncio.run(main())
