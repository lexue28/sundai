# Setup Instructions

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# Notion API Configuration
# Get your API key from: https://www.notion.so/my-integrations
NOTION_API_KEY=your_notion_api_key_here

# Mastodon API Configuration
# You'll need to create an application at your Mastodon instance
# and get an access token. You can use OAuth or create a token manually.
MASTODON_INSTANCE_URL=https://yourinstance.social
MASTODON_ACCESS_TOKEN=your_mastodon_access_token_here

# OpenAI API Configuration (for LLM)
# Get your API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Business keyword for searching Mastodon posts
BUSINESS_KEYWORD=your_keyword_here
```

## Getting API Keys

### Notion API
1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Give it a name and select your workspace
4. Copy the "Internal Integration Token" - this is your `NOTION_API_KEY`
5. Make sure to share your Notion page with this integration (click "..." on the page → "Connections" → Select your integration)

### Mastodon API
1. Go to your Mastodon instance (e.g., https://mastodon.social)
2. Go to Settings → Development → New Application
3. Give it a name, set scopes to `read` and `write`
4. Create the application
5. Copy the "Your access token" - this is your `MASTODON_ACCESS_TOKEN`
6. Your instance URL is your `MASTODON_INSTANCE_URL` (e.g., https://mastodon.social)

### OpenAI API
1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create a new API key
4. Copy it - this is your `OPENAI_API_KEY`

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create your `.env` file with the credentials above

3. Run the script:
```bash
python main.py
```

## Usage

The `main.py` script will:
1. Fetch content from your Notion page
2. Generate a social media post using OpenAI
3. Post it to Mastodon
4. Search for and display 5 recent posts with your business keyword
