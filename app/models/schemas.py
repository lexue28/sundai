from typing import Optional
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
import re


class MastodonAccount(BaseModel):
    id: str
    username: str
    display_name: str
    url: Optional[str] = None


class MastodonPost(BaseModel):
    id: str
    content: str
    created_at: str
    account: MastodonAccount
    url: Optional[str] = None
    in_reply_to_id: Optional[str] = None


class Reply(BaseModel):
    post_id: str = Field(description="The ID of the post to reply to")
    status: str = Field(min_length=1, max_length=500, description="The reply text content")
    visibility: str = Field(default="public", description="Visibility: public, unlisted, private, or direct")
    
    @field_validator("status")
    @classmethod
    def validate_status_length(cls, v):
        if len(v) > 500:
            raise ValueError("status must be 500 characters or less")
        if not v.strip():
            raise ValueError("status cannot be empty or whitespace only")
        return v.strip()
    
    @field_validator("post_id")
    @classmethod
    def validate_post_id_format(cls, v):
        if not v or not v.strip():
            raise ValueError("post_id cannot be empty")
        if not re.match(r'^\d+$', str(v)):
            raise ValueError("post_id must be a valid numeric ID")
        return str(v).strip()
    
    @model_validator(mode="after")
    def validate_visibility(self):
        valid_visibilities = ["public", "unlisted", "private", "direct"]
        if self.visibility not in valid_visibilities:
            raise ValueError(f"visibility must be one of {valid_visibilities}")
        return self


class ReplyBatch(BaseModel):
    replies: list[Reply] = Field(min_length=1, description="List of replies to generate")
    
    @field_validator("replies")
    @classmethod
    def must_have_replies(cls, v):
        if len(v) < 1:
            raise ValueError("replies must have at least 1 reply")
        return v
    
    @model_validator(mode="after")
    def validate_unique_post_ids(self):
        post_ids = [reply.post_id for reply in self.replies]
        if len(post_ids) != len(set(post_ids)):
            raise ValueError("Each post_id should only have one reply")
        return self


class PostFeedback(BaseModel):
    """Model for storing feedback on rejected posts."""
    post_content: str = Field(description="The post content that was rejected")
    rejection_reason: str = Field(description="The reason for rejection")
    timestamp: str = Field(description="ISO format timestamp of when feedback was recorded")
