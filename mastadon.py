import os
import re
import requests
from dotenv import load_dotenv
from models import MastodonPost, MastodonAccount

load_dotenv()


class MastodonClient:
    def __init__(self):
        self.instance_url = os.getenv('MASTODON_INSTANCE_URL', '').rstrip('/')
        self.access_token = os.getenv('MASTODON_ACCESS_TOKEN')
        if not self.access_token:
            raise ValueError("MASTODON_ACCESS_TOKEN not found in environment variables")
        
        self.base_url = f'{self.instance_url}/api/v1'
        self.headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
    
    def post_status(self, status, visibility='public', in_reply_to_id=None):
        """
        POST /api/v1/statuses
        Posts a status to Mastodon.
        If in_reply_to_id is provided, this becomes a reply to that post.
        Note: This is separate from searching - use get_recent_posts_by_keyword to search.
        """
        url = f'{self.base_url}/statuses'
        data = {
            'status': status,
            'visibility': visibility
        }
        
        if in_reply_to_id:
            data['in_reply_to_id'] = str(in_reply_to_id)
            print(f"Posting reply to post {in_reply_to_id}: {status[:100]}...")
        else:
            print(f"Posting new status: {status[:100]}...")
        
        response = requests.post(url, headers=self.headers, data=data)
        response.raise_for_status()
        return response.json()
    
    def get_recent_posts_by_keyword(self, keyword, limit=5):
        """
        GET /api/v2/search
        Search for posts containing a keyword.
        Returns validated MastodonPost objects.
        Note: This is separate from posting - posting uses POST /api/v1/statuses.
        """
        # Use v2 search endpoint (v1 is deprecated/disabled on many instances)
        search_url = f'{self.instance_url}/api/v2/search'
        params = {
            'q': keyword,
            'type': 'statuses',
            'resolve': False,
            'limit': limit
        }
        
        print(f"Searching Mastodon: {search_url} with params: {params}")
        response = requests.get(search_url, headers=self.headers, params=params)
        response.raise_for_status()
        
        search_data = response.json()
        statuses = search_data.get('statuses', [])
        
        validated_posts = []
        for status in statuses:
            try:
                account_data = status.get('account', {})
                account = MastodonAccount(
                    id=str(account_data.get('id', '')),
                    username=account_data.get('username', ''),
                    display_name=account_data.get('display_name', ''),
                    url=account_data.get('url')
                )
                
                post = MastodonPost(
                    id=str(status.get('id', '')),
                    content=status.get('content', ''),
                    created_at=status.get('created_at', ''),
                    account=account,
                    url=status.get('url'),
                    in_reply_to_id=str(status.get('in_reply_to_id')) if status.get('in_reply_to_id') else None
                )
                validated_posts.append(post)
            except Exception as e:
                continue
        
        sorted_posts = sorted(
            validated_posts,
            key=lambda x: x.created_at,
            reverse=True
        )[:limit]
        
        return sorted_posts
    
    def format_post_info(self, post):
        """Format a MastodonPost object into a readable string."""
        content = re.sub('<[^<]+?>', '', post.content)
        return f"@{post.account.username} ({post.account.display_name})\n{post.created_at}\n{content[:200]}..."
