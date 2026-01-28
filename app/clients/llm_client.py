import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from app.models.schemas import ReplyBatch, Reply

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
    
    def generate_post_with_rag(self, topic: str, context: str, max_length: int = 500, feedback: str = None) -> str:
        """
        Generate a post using RAG context and a specific topic.
        Base prompt is about Linda the freelance coder, with SF tech bro topic as an angle.
        
        Args:
            topic: The SF tech bro topic to incorporate as an angle (e.g., "AI-powered everything")
            context: Context retrieved from RAG database (about Linda's projects/skills)
            max_length: Maximum character length for the post
            feedback: Optional feedback to incorporate into the prompt
            
        Returns:
            Generated post text
        """
        # Base prompt about Linda the freelance coder
        base_prompt = f"""Write a Mastodon post for Linda, a freelance fullstack developer.

About Linda:
- Freelance coder and fullstack developer
- Skills: React, Node.js, Python, databases, APIs
- Available for freelance work
- Has past projects and coding experience

Relevant context from past work/projects:
{context}

SF Tech Bro Topic Angle: {topic}
(Incorporate this topic as a theme/angle, but keep the focus on Linda's coding work and projects)

Requirements:
- Primary focus: Linda's coding skills, projects, or freelance availability
- Incorporate the SF tech bro topic ({topic}) as a subtle angle or theme
- Engaging and authentic
- Under {max_length} characters
- Include relevant hashtags like #FreelanceDeveloper #FullStackDeveloper #HireMe
- Professional but personal tone"""
        
        # Add feedback if provided
        if feedback:
            prompt = f"""{base_prompt}

Important feedback to follow:
{feedback}

Output ONLY the post text."""
        else:
            prompt = f"""{base_prompt}

Output ONLY the post text."""
        
        try:
            max_output_tokens = 300
            max_total_tokens = max_output_tokens + 400  # Extra for reasoning
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You write social media posts. Return only the post text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_total_tokens,  # Increased for thinking models
                temperature=0.7
            )
            if not response.choices or len(response.choices) == 0:
                raise ValueError("No choices in API response")
            
            message = response.choices[0].message
            
            # Extract content - handle thinking models that put output in reasoning field
            post_content = None
            
            # Method 1: Standard content field (works for non-thinking models)
            if message.content and len(message.content.strip()) > 0:
                post_content = str(message.content).strip()
            
            # Method 2: For thinking models, extract from reasoning field
            # Thinking models put reasoning in reasoning field, and actual output might be there too
            if not post_content:
                reasoning_text = None
                
                # Try to get reasoning from message object
                if hasattr(message, 'reasoning') and message.reasoning:
                    reasoning_text = str(message.reasoning)
                elif hasattr(message, 'model_dump'):
                    msg_dict = message.model_dump()
                    reasoning_text = msg_dict.get('reasoning', '')
                    if reasoning_text:
                        reasoning_text = str(reasoning_text)
                
                if reasoning_text and len(reasoning_text) > 100:
                    import re
                    
                    # Pattern 1: Look for text after "Draft:" in quotes
                    match = re.search(r'Draft:\s*\n\s*["\']([^"\']+)["\']', reasoning_text, re.DOTALL)
                    if match:
                        post_content = match.group(1).strip()
                    
                    # Pattern 2: Look for the actual post pattern (has hashtags)
                    if not post_content:
                        match = re.search(r'([^"\']*Building[^"\']*#FreelanceDeveloper[^"\']*)', reasoning_text)
                        if match:
                            post_content = match.group(1).strip()
                            # Clean up if it has extra quotes
                            if post_content.startswith('"') and post_content.endswith('"'):
                                post_content = post_content[1:-1]
                    
                    # Pattern 3: Find longest quoted string (likely the post)
                    if not post_content:
                        quoted_matches = re.findall(r'["\']([^"\']{100,})["\']', reasoning_text)
                        if quoted_matches:
                            # Take the longest one that contains hashtags or looks like a post
                            for match in sorted(quoted_matches, key=len, reverse=True):
                                if '#' in match or len(match) > 150:
                                    post_content = match.strip()
                                    break
            
            # Method 3: Try accessing as dict (for Pydantic models) - check reasoning there too
            if not post_content:
                try:
                    if hasattr(message, 'model_dump'):
                        msg_dict = message.model_dump()
                        # Check content first
                        post_content = msg_dict.get('content', '').strip() if msg_dict.get('content') else None
                        # Then check reasoning
                        if not post_content and msg_dict.get('reasoning'):
                            reasoning = str(msg_dict.get('reasoning', ''))
                            import re
                            # Extract from reasoning
                            match = re.search(r'["\']([^"\']{100,})["\']', reasoning)
                            if match:
                                post_content = match.group(1).strip()
                    elif hasattr(message, 'dict'):
                        msg_dict = message.dict()
                        post_content = msg_dict.get('content', '').strip() if msg_dict.get('content') else None
                except Exception:
                    pass
            
            if not post_content:
                raise ValueError("API returned empty content - could not extract from content or reasoning fields")
            
            # Remove any markdown formatting if present
            if post_content.startswith('"') and post_content.endswith('"'):
                post_content = post_content[1:-1]
            if post_content.startswith("'") and post_content.endswith("'"):
                post_content = post_content[1:-1]
            
            return post_content
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate post: {e}") from e
    
    def generate_promotional_post(self, notion_context=None, feedback_list=None, max_length=500, use_rag=True, rag_query=None, topic=None):
        """
        Generate a promotional post using RAG and topic cycling.
        Now uses generate_post_with_rag internally.
        
        Args:
            notion_context: Optional context from Notion page (if not using RAG) - deprecated, use RAG instead
            feedback_list: List of PostFeedback objects with past rejection reasons
            max_length: Maximum character length for the post
            use_rag: If True, use RAG to retrieve context from database (default: True)
            rag_query: Query string for RAG retrieval (default: based on topic)
            topic: Specific topic to use (default: cycles through SF tech bro topics)
        """
        
        # Get topic (cycle through SF tech bro topics if not provided)
        if not topic:
            from app.services.topic_cycler import get_topic_cycler
            topic_cycler = get_topic_cycler()
            topic = topic_cycler.get_next_topic()
        # Get context from RAG (about Linda's projects/skills)
        context = ""
        if use_rag:
            try:
                from app.services.rag import retrieve_context, db
                # Query for coding/projects context (not the SF tech bro topic)
                query = rag_query or "freelance developer coding projects skills React Node.js Python"
                rag_context, _ = retrieve_context(db, query, top_k=5)
                if rag_context and rag_context != "No relevant context found.":
                    context = rag_context
                else:
                    # Fallback to notion_context if provided
                    if notion_context:
                        context = notion_context[:500]
            except Exception as e:
                if notion_context:
                    context = notion_context[:500]
        elif notion_context:
            context = notion_context[:500]
        
        if not context:
            context = "Freelance fullstack developer with experience in React, Node.js, Python, databases, and APIs. Available for freelance work."
        
        # Get feedback to include in prompt
        feedback = None
        if feedback_list and len(feedback_list) > 0:
            latest_reason = feedback_list[-1].rejection_reason.strip()
            feedback = latest_reason
        
        # Generate post using RAG (with feedback in prompt)
        post_content = self.generate_post_with_rag(
            topic=topic, 
            context=context, 
            max_length=max_length,
            feedback=feedback
        )
        
        return post_content
    
    def generate_replies(self, posts, notion_context=None, tone='professional', max_length=500, use_rag=True, rag_query=None):
        """
        Generate replies to multiple Mastodon posts using structured outputs.
        Uses structured outputs similar to the example with retry logic.
        
        Args:
            posts: List of MastodonPost objects to reply to
            notion_context: Optional context from Notion page (if not using RAG)
            tone: Tone for the replies
            max_length: Maximum character length for replies
            use_rag: If True, use RAG to retrieve context from database (default: True)
            rag_query: Query string for RAG retrieval (default: based on post content)
        """
        posts_text = []
        for post in posts:
            content = post.content if hasattr(post, 'content') else post.get('content', '')
            username = post.account.username if hasattr(post, 'account') else post.get('account', {}).get('username', 'Unknown')
            post_id = post.id if hasattr(post, 'id') else post.get('id', '')
            posts_text.append(f"Post ID: {post_id}\n@{username}: {content}")
        
        posts_context = "\n\n".join(posts_text)
        
        # Use RAG to retrieve context if enabled
        business_context = ""
        if use_rag:
            try:
                from app.services.rag import retrieve_context, db
                # Use provided query or extract keywords from posts
                query = rag_query or " ".join([post.content[:50] for post in posts[:2]]) or "business services"
                rag_context, _ = retrieve_context(db, query, top_k=3)
                if rag_context and rag_context != "No relevant context found.":
                    business_context = f"Business context: {rag_context[:300]}"
            except Exception as e:
                if notion_context:
                    business_context = f"Business context: {notion_context[:300]}"
        elif notion_context:
            business_context = f"Business context: {notion_context[:300]}"
        
        prompt = f"""You are managing social media for a business. Generate professional, engaging replies to these Mastodon posts.

{business_context if business_context else ''}

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
