from fastapi import FastAPI, Depends, HTTPException, Query, Body, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.clients.mastadon import MastodonClient
from app.clients.llm_client import LLMClient
from app.clients.notion import NotionClient
from app.services.feedback_storage import FeedbackStorage
from app.models.schemas import MastodonPost, PostFeedback, ReplyBatch
from typing import Optional, List
from pydantic import BaseModel
import os
import tempfile
import sqlite3

# Initialize FastAPI app
app = FastAPI(
    title="Sundai API",
    description="API for Sundai social media automation",
    version="1.0.0"
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global listener instance (will be set by startup)
listener_instance = None

# Initialize database and listener on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    
    # Start Notion listener in background
    try:
        from app.services.notion_listener import NotionListener
        notion_page_url = os.getenv(
            "NOTION_PAGE_URL",
            "https://www.notion.so/Sundai-Workshop-fd5a5674d6dc46fba81e9049b53ae410"
        )
        poll_interval = int(os.getenv("NOTION_POLL_INTERVAL", "60"))  # 1 minute
        global listener_instance
        listener_instance = NotionListener(notion_page_url, poll_interval)
        listener_instance.start_listening_background(auto_post=False)
    except Exception as e:
        pass


@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "Sundai API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "sundai-api"}


@app.get("/api/status")
async def api_status(db: Session = Depends(get_db)):
    """Get API status with database connection check."""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "service": "sundai-api"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


# Mastodon API Endpoints

class PostCreateRequest(BaseModel):
    """Request model for creating a new post."""
    status: str
    visibility: str = "public"
    in_reply_to_id: Optional[str] = None
    media_ids: Optional[List[str]] = None


class PostReplyRequest(BaseModel):
    """Request model for replying to a post."""
    status: str
    visibility: str = "public"


@app.get("/api/posts", response_model=List[MastodonPost])
async def search_posts(
    keyword: str = Query(..., description="Keyword to search for in posts"),
    limit: int = Query(5, ge=1, le=50, description="Maximum number of posts to return")
):
    """
    Search for Mastodon posts by keyword.
    
    Returns a list of posts matching the keyword.
    """
    try:
        mastodon_client = MastodonClient()
        posts = mastodon_client.get_recent_posts_by_keyword(keyword, limit=limit)
        return posts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching posts: {str(e)}")


@app.post("/api/posts")
async def create_post(post_data: PostCreateRequest):
    """
    Create a new Mastodon post.
    
    - **status**: The text content of the post
    - **visibility**: Post visibility (public, unlisted, private, direct)
    - **in_reply_to_id**: Optional ID of post to reply to
    - **media_ids**: Optional list of media IDs to attach
    """
    try:
        mastodon_client = MastodonClient()
        result = mastodon_client.post_status(
            status=post_data.status,
            visibility=post_data.visibility,
            in_reply_to_id=post_data.in_reply_to_id,
            media_ids=post_data.media_ids
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating post: {str(e)}")


@app.post("/api/posts/{post_id}/reply")
async def reply_to_post(post_id: str, reply_data: PostReplyRequest):
    """
    Reply to a specific Mastodon post.
    
    - **post_id**: The ID of the post to reply to
    - **status**: The reply text content
    - **visibility**: Reply visibility (public, unlisted, private, direct)
    """
    try:
        mastodon_client = MastodonClient()
        result = mastodon_client.post_status(
            status=reply_data.status,
            visibility=reply_data.visibility,
            in_reply_to_id=post_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error replying to post: {str(e)}")


@app.post("/api/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    description: Optional[str] = None
):
    """
    Upload media to Mastodon.
    
    Returns the media_id that can be used when creating posts.
    """
    try:
        mastodon_client = MastodonClient()
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            media_id = mastodon_client.upload_media(tmp_path, description=description)
            return {"media_id": media_id, "message": "Media uploaded successfully"}
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading media: {str(e)}")


# LLM API Endpoints

class GeneratePostRequest(BaseModel):
    """Request model for generating a social media post."""
    content: str
    platform: str = "Mastodon"
    tone: str = "professional"
    max_length: int = 500


class GeneratePromotionalPostRequest(BaseModel):
    """Request model for generating a promotional post."""
    notion_context: Optional[str] = None
    max_length: int = 500


class GenerateRepliesRequest(BaseModel):
    """Request model for generating replies to posts."""
    posts: List[MastodonPost]
    notion_context: Optional[str] = None
    tone: str = "professional"
    max_length: int = 500


@app.post("/api/llm/generate-post")
async def generate_post(request: GeneratePostRequest):
    """
    Generate a social media post from content using LLM.
    
    - **content**: Source content to base the post on
    - **platform**: Target platform (default: Mastodon)
    - **tone**: Tone of the post (default: professional)
    - **max_length**: Maximum character length
    """
    try:
        llm_client = LLMClient()
        post = llm_client.generate_social_media_post(
            content=request.content,
            platform=request.platform,
            tone=request.tone,
            max_length=request.max_length
        )
        return {"post": post, "length": len(post)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating post: {str(e)}")


@app.post("/api/llm/generate-promotional-post")
async def generate_promotional_post(request: GeneratePromotionalPostRequest):
    """
    Generate a promotional post advertising fullstack abilities.
    
    - **notion_context**: Optional context from Notion page
    - **max_length**: Maximum character length
    """
    try:
        llm_client = LLMClient()
        feedback_storage = FeedbackStorage()
        past_feedback = feedback_storage.get_all_feedback()
        
        post = llm_client.generate_promotional_post(
            notion_context=request.notion_context,
            feedback_list=past_feedback,
            max_length=request.max_length
        )
        return {"post": post, "length": len(post)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating promotional post: {str(e)}")


@app.post("/api/llm/generate-replies", response_model=ReplyBatch)
async def generate_replies(request: GenerateRepliesRequest):
    """
    Generate replies to multiple Mastodon posts using LLM.
    
    - **posts**: List of MastodonPost objects to reply to
    - **notion_context**: Optional business context from Notion
    - **tone**: Tone for replies (default: professional)
    - **max_length**: Maximum character length per reply
    """
    try:
        llm_client = LLMClient()
        reply_batch = llm_client.generate_replies(
            posts=request.posts,
            notion_context=request.notion_context,
            tone=request.tone,
            max_length=request.max_length
        )
        return reply_batch
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating replies: {str(e)}")


# Notion API Endpoints

@app.get("/api/notion/page/{page_id}")
async def get_notion_page(page_id: str):
    """
    Get Notion page content (metadata).
    
    - **page_id**: Notion page ID or URL
    """
    try:
        notion_client = NotionClient()
        page_data = notion_client.get_page_content(page_id)
        return page_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Notion page: {str(e)}")


@app.get("/api/notion/page/{page_id}/text")
async def get_notion_page_text(page_id: str):
    """
    Get Notion page as plain text.
    
    - **page_id**: Notion page ID or URL
    """
    try:
        notion_client = NotionClient()
        text_content = notion_client.get_page_as_text(page_id)
        return {"text": text_content, "length": len(text_content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Notion page text: {str(e)}")


@app.get("/api/notion/page/{page_id}/blocks")
async def get_notion_page_blocks(page_id: str):
    """
    Get all content blocks from a Notion page.
    
    - **page_id**: Notion page ID or URL
    """
    try:
        notion_client = NotionClient()
        blocks = notion_client.get_page_blocks(page_id)
        return {"blocks": blocks, "count": len(blocks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Notion page blocks: {str(e)}")


# Feedback API Endpoints

class StoreFeedbackRequest(BaseModel):
    """Request model for storing feedback."""
    post_content: str
    rejection_reason: str


@app.get("/api/feedback", response_model=List[PostFeedback])
async def get_all_feedback():
    """
    Get all stored feedback for rejected posts.
    """
    try:
        feedback_storage = FeedbackStorage()
        feedback_list = feedback_storage.get_all_feedback()
        return feedback_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching feedback: {str(e)}")


@app.post("/api/feedback")
async def store_feedback(request: StoreFeedbackRequest):
    """
    Store feedback for a rejected post.
    
    - **post_content**: The post content that was rejected
    - **rejection_reason**: The reason for rejection
    """
    try:
        feedback_storage = FeedbackStorage()
        feedback_storage.store_feedback(
            post_content=request.post_content,
            rejection_reason=request.rejection_reason
        )
        return {"message": "Feedback stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing feedback: {str(e)}")


# Notion Listener API Endpoints

@app.get("/api/listener/status")
async def get_listener_status():
    """
    Get the status of the Notion listener.
    
    Returns information about:
    - Whether listener is running
    - Last check time
    - Change count
    - Poll interval
    """
    global listener_instance
    if not listener_instance:
        return {
            "running": False,
            "message": "Listener not initialized"
        }
    
    return {
        "running": True,
        "notion_page_url": listener_instance.notion_page_url,
        "poll_interval": listener_instance.poll_interval,
        "change_count": listener_instance.change_count,
        "last_change_time": listener_instance.last_change_time,
        "last_content_hash": listener_instance.last_content_hash[:8] + "..." if listener_instance.last_content_hash else None
    }


@app.get("/api/listener/logs")
async def get_listener_logs(limit: int = Query(50, ge=1, le=100)):
    """
    Get recent log entries from the Notion listener.
    
    - **limit**: Maximum number of log entries to return (1-100)
    """
    global listener_instance
    if not listener_instance:
        return {"logs": [], "message": "Listener not initialized"}
    
    logs = listener_instance.log_history[-limit:] if listener_instance.log_history else []
    return {
        "logs": logs,
        "total_logs": len(listener_instance.log_history),
        "returned": len(logs)
    }


@app.post("/api/listener/check-now")
async def trigger_listener_check():
    """
    Manually trigger a check for Notion changes (doesn't wait for poll interval).
    """
    global listener_instance
    if not listener_instance:
        raise HTTPException(status_code=503, detail="Listener not initialized")
    
    try:
        changed = listener_instance.check_for_changes()
        if changed:
            # Handle the update
            post = listener_instance.handle_page_update()
            return {
                "changed": True,
                "post_generated": post is not None,
                "post": post if post else None
            }
        else:
            return {
                "changed": False,
                "message": "No changes detected"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking for changes: {str(e)}")


# RAG Database API Endpoints

@app.get("/api/rag/status")
async def get_rag_status():
    """
    Get status of the RAG database.
    
    Returns information about:
    - Database file location
    - Number of chunks stored
    - Database size
    """
    try:
        from app.services.rag import db, DATABASE_PATH
        
        db_path = str(DATABASE_PATH)
        
        # Count chunks
        chunk_count = 0
        try:
            if hasattr(db, 'execute'):
                result = db.execute("SELECT COUNT(*) FROM embeddings_meta").fetchone()
                chunk_count = result[0] if result else 0
            else:
                # Try to connect directly
                conn = sqlite3.connect(db_path)
                result = conn.execute("SELECT COUNT(*) FROM embeddings_meta").fetchone()
                chunk_count = result[0] if result else 0
                conn.close()
        except Exception as e:
            # Table might not exist yet
            chunk_count = 0
        
        # Get database size
        db_size = 0
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)
        
        return {
            "database_path": db_path,
            "chunk_count": chunk_count,
            "database_size_bytes": db_size,
            "database_size_mb": round(db_size / (1024 * 1024), 2) if db_size > 0 else 0,
            "database_exists": os.path.exists(db_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting RAG status: {str(e)}")


@app.get("/api/rag/search")
async def search_rag(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=20, description="Number of results to return")
):
    """
    Search the RAG database for relevant context.
    
    - **query**: Search query text
    - **top_k**: Number of top results to return
    """
    try:
        from app.services.rag import retrieve_context, db
        context, metadata = retrieve_context(db, query, top_k=top_k)
        return {
            "query": query,
            "context": context,
            "metadata": metadata,
            "top_k": top_k
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching RAG: {str(e)}")


# System/API Keys Status Endpoints

@app.get("/api/system/status")
async def get_system_status():
    """
    Get system status including API key configuration.
    
    Returns which API keys are configured (without exposing values).
    """
    api_keys_status = {
        "notion_api_key": bool(os.getenv("NOTION_API_KEY")),
        "mastodon_instance_url": bool(os.getenv("MASTODON_INSTANCE_URL")),
        "mastodon_access_token": bool(os.getenv("MASTODON_ACCESS_TOKEN")),
        "open_api_key": bool(os.getenv("OPEN_API_KEY") or os.getenv("OPENROUTER_API_KEY")),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free"),
        "replicate_api_token": bool(os.getenv("REPLICATE_API_TOKEN")),
        "telegram_bot_token": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "telegram_chat_id": bool(os.getenv("TELEGRAM_CHAT_ID")),
    }
    
    # Check database connection
    db_status = "unknown"
    try:
        db = get_db()
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "api_keys_configured": api_keys_status,
        "database_status": db_status,
        "listener_running": listener_instance is not None,
        "environment": os.getenv("ENVIRONMENT", "development")
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
