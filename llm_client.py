import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from models import ReplyBatch, Reply

load_dotenv()


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv('OPEN_API_KEY') or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPEN_API_KEY not found in environment variables")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/lexue28/sundai",
                "X-Title": "Sundai Workshop"
            }
        )
        self.model = os.getenv('OPENROUTER_MODEL', 'nvidia/nemotron-3-nano-30b-a3b:free')
    
    def generate_social_media_post(self, content, platform='Mastodon', tone='professional', max_length=500):
        """Generates a social media post from given content using an LLM."""
        prompt = f"""Generate a {tone} social media post for {platform} based on this content.

Requirements:
- Engaging and relevant
- Under {max_length} characters
- Include relevant hashtags if appropriate
- Tone: {tone}

Source content:
{content}

Generate the social media post:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a skilled social media content creator."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    def generate_promotional_post(self, notion_context=None, feedback_list=None, max_length=500):
        """
        Generate a promotional post advertising fullstack abilities and availability for freelance work.
        
        Args:
            notion_context: Context from Notion page
            feedback_list: List of PostFeedback objects with past rejection reasons
            max_length: Maximum character length for the post
        """
        print(f"\n[DEBUG] Starting promotional post generation...")
        print(f"[DEBUG] Model: {self.model}")
        print(f"[DEBUG] Model from env: {os.getenv('OPENROUTER_MODEL', 'NOT SET - using default')}")
        print(f"[DEBUG] Notion context length: {len(notion_context) if notion_context else 0}")
        print(f"[DEBUG] Feedback items: {len(feedback_list) if feedback_list else 0}")
        
        context_snippet = ""
        if notion_context:
            # Ultra-short context - just first 100 chars
            context_snippet = f"\n{notion_context[:100]}\n"
        
        feedback_snippet = ""
        if feedback_list and len(feedback_list) > 0:
            # Get the most recent feedback and pass it directly to the model
            latest_reason = feedback_list[-1].rejection_reason.strip()
            feedback_snippet = f"\nFollow this feedback: {latest_reason}\n"
        
        # Add variation to prompt to prevent cached responses
        import random
        variation_hints = [
            "Creative",
            "Fresh",
            "Unique",
            "Personal"
        ]
        variation = random.choice(variation_hints)
        
        # Build prompt with feedback prominently featured
        base_prompt = f"""Write a Mastodon post for a freelance fullstack developer.

Skills: React, Node.js, Python, databases, APIs
Available for freelance work
Under {max_length} chars
Hashtags: #FreelanceDeveloper #FullStackDeveloper #HireMe
{variation}
{context_snippet}"""
        
        # Add feedback prominently at the end so it's fresh in the model's context
        if feedback_snippet:
            prompt = f"""{base_prompt}

{feedback_snippet}
Return ONLY the post text."""
        else:
            prompt = f"""{base_prompt}

Return ONLY the post text."""

        print(f"[DEBUG] Sending request to OpenRouter...")
        print(f"[DEBUG] Prompt length: {len(prompt)} characters")
        
        try:
            # Use OpenRouter responses.create format (exactly as user's example)
            system_prompt = "You write social media posts. Return only the post text."
            
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
            )
            
            print(f"[DEBUG] Response type: {type(response)}")
            post_content = response.output_text.strip() if response.output_text else None
            
            print(f"[DEBUG] Response content: {repr(post_content[:200]) if post_content else 'None'}")
            
            if not post_content or len(post_content) == 0:
                raise ValueError("Post content is empty after processing.")
            # Remove any markdown formatting if present
            if post_content.startswith('"') and post_content.endswith('"'):
                post_content = post_content[1:-1]
            if post_content.startswith("'") and post_content.endswith("'"):
                post_content = post_content[1:-1]
            
            print(f"[DEBUG] Final post content length: {len(post_content)}")
            print(f"[DEBUG] Final post content: {post_content[:100]}...")
            return post_content
            
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"[ERROR] Exception in generate_promotional_post: {type(e).__name__}: {e}")
            print(f"{'='*60}")
            import traceback
            print(f"[ERROR] Full traceback:")
            print(traceback.format_exc())
            print(f"{'='*60}\n")
            
            # Don't silently return fallback - raise the error so user knows something is wrong
            raise RuntimeError(
                f"Failed to generate post: {e}\n"
                f"Check your API key (OPEN_API_KEY or OPENROUTER_API_KEY) and model ({self.model}).\n"
                f"Make sure the model is available and you have sufficient credits."
            ) from e
    
    def generate_replies(self, posts, notion_context=None, tone='professional', max_length=500):
        """
        Generate replies to multiple Mastodon posts using structured outputs.
        Uses structured outputs similar to the example with retry logic.
        """
        posts_text = []
        for post in posts:
            content = post.content if hasattr(post, 'content') else post.get('content', '')
            username = post.account.username if hasattr(post, 'account') else post.get('account', {}).get('username', 'Unknown')
            post_id = post.id if hasattr(post, 'id') else post.get('id', '')
            posts_text.append(f"Post ID: {post_id}\n@{username}: {content}")
        
        posts_context = "\n\n".join(posts_text)
        
        prompt = f"""You are managing social media for a business. Generate professional, engaging replies to these Mastodon posts.

{f'Business context: {notion_context}' if notion_context else ''}

Posts to reply to:
{posts_context}

Requirements for each reply:
- Professional and engaging
- Under {max_length} characters
- Relevant to the original post
- Tone: {tone}
- Be helpful and add value
- Not the same as original post

Generate replies for all {len(posts)} posts. Each reply must have:
- post_id: The exact post ID to reply to (must be a numeric string)
- status: The reply text (max {max_length} chars, cannot be empty)
- visibility: "public" (default)

Respond with JSON matching the ReplyBatch structure."""

        try:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a skilled social media manager. Always respond with valid JSON matching the ReplyBatch schema."},
                    {"role": "user", "content": prompt}
                ],
                response_format=ReplyBatch,
                temperature=0.7
            )
            
            reply_batch: ReplyBatch = response.choices[0].message.parsed
            return reply_batch
        except Exception as e:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a skilled social media manager. Respond only with valid JSON matching the ReplyBatch schema."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                
                content = response.choices[0].message.content
                parsed_json = json.loads(content)
                reply_batch = ReplyBatch(**parsed_json)
                return reply_batch
            except Exception as parse_error:
                raise ValueError(f"Failed to parse structured output: {parse_error}. Original error: {e}")
