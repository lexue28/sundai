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
        print(f"[DEBUG] Notion context length: {len(notion_context) if notion_context else 0}")
        print(f"[DEBUG] Feedback items: {len(feedback_list) if feedback_list else 0}")
        
        context_snippet = ""
        if notion_context:
            context_snippet = f"\nContext about my work and projects:\n{notion_context[:800]}\n"
        
        feedback_snippet = ""
        if feedback_list and len(feedback_list) > 0:
            # Summarize recent feedback to help avoid past mistakes
            recent_feedback = feedback_list[-5:]  # Get last 5 feedback items
            feedback_reasons = [f.rejection_reason for f in recent_feedback]
            unique_reasons = list(set(feedback_reasons))
            
            feedback_snippet = f"\n\nIMPORTANT - Learn from past rejections:\n"
            feedback_snippet += "The following posts were previously rejected. Avoid these issues:\n"
            for i, reason in enumerate(unique_reasons, 1):
                feedback_snippet += f"- {reason}\n"
            feedback_snippet += "\nMake sure your post addresses these concerns and avoids the mistakes mentioned above.\n"
        
        prompt = f"""You are creating a Mastodon post to advertise a freelance fullstack developer. Write a compelling post that:

- Highlights fullstack development skills (React, Node.js, Python, databases, APIs, etc.)
- Mentions availability for freelance work
- Sounds confident and professional, not desperate
- Makes people want to hire them
- Includes hashtags like #FreelanceDeveloper #FullStackDeveloper #HireMe #WebDev
- Stays under {max_length} characters total
- Is specific about technical capabilities
{context_snippet}{feedback_snippet}
Write ONLY the post content itself - no explanations or meta commentary. Make it engaging and memorable."""

        print(f"[DEBUG] Sending request to OpenRouter...")
        print(f"[DEBUG] Prompt length: {len(prompt)} characters")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a skilled copywriter who writes engaging, authentic social media posts. You create compelling content that helps developers get hired. Always return the post text directly without any explanation or commentary."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.8
            )
            
            print(f"[DEBUG] OpenRouter response received")
            print(f"[DEBUG] Response object type: {type(response)}")
            print(f"[DEBUG] Response choices count: {len(response.choices) if response.choices else 0}")
            
            if not response.choices:
                print("[ERROR] No choices in response!")
                return "Freelance fullstack developer available for hire! 🚀 React, Node.js, Python, APIs. Building scalable web apps. Let's create something amazing! #FreelanceDeveloper #FullStackDeveloper #HireMe"
            
            message = response.choices[0].message
            print(f"[DEBUG] Message type: {type(message)}")
            print(f"[DEBUG] Message content type: {type(message.content)}")
            print(f"[DEBUG] Message content (raw): {repr(message.content)}")
            print(f"[DEBUG] Message content length: {len(message.content) if message.content else 0}")
            
            if not message.content:
                print("[ERROR] Message content is None or empty!")
                print(f"[DEBUG] Full response structure: {response}")
                return "Freelance fullstack developer available for hire! 🚀 React, Node.js, Python, APIs. Building scalable web apps. Let's create something amazing! #FreelanceDeveloper #FullStackDeveloper #HireMe"
            
            post_content = message.content.strip()
            print(f"[DEBUG] After strip, content length: {len(post_content)}")
            print(f"[DEBUG] After strip, content: {repr(post_content)}")
            
            # Remove any markdown formatting if present
            if post_content.startswith('"') and post_content.endswith('"'):
                post_content = post_content[1:-1]
                print(f"[DEBUG] Removed outer quotes")
            if post_content.startswith("'") and post_content.endswith("'"):
                post_content = post_content[1:-1]
                print(f"[DEBUG] Removed outer single quotes")
            
            if not post_content or len(post_content) == 0:
                print("[ERROR] Post content is empty after processing!")
                print(f"[DEBUG] Returning fallback post")
                return "Freelance fullstack developer available for hire! 🚀 React, Node.js, Python, APIs. Building scalable web apps. Let's create something amazing! #FreelanceDeveloper #FullStackDeveloper #HireMe"
            
            print(f"[DEBUG] Final post content length: {len(post_content)}")
            return post_content
            
        except Exception as e:
            print(f"[ERROR] Exception in generate_promotional_post: {type(e).__name__}: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            return "Freelance fullstack developer available for hire! 🚀 React, Node.js, Python, APIs. Building scalable web apps. Let's create something amazing! #FreelanceDeveloper #FullStackDeveloper #HireMe"
    
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
