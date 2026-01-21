import os
import replicate
from dotenv import load_dotenv
from notion import NotionClient
from mastadon import MastodonClient
from llm_client import LLMClient

load_dotenv()

# Verify Replicate API token is set
replicate_api_token = os.getenv('REPLICATE_API_TOKEN')
if not replicate_api_token:
    raise ValueError("REPLICATE_API_TOKEN not found in environment variables. Please add it to your .env file.")


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
    
    # Generate and post replies to keyword searches
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

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
