# Sundai

Social media automation built around Notion, Mastodon, and an LLM workflow.

## Setup

1) Create a virtual environment and install dependencies.

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2) Create a `.env` file at the repo root with the required keys:

```
NOTION_API_KEY=...
MASTODON_INSTANCE_URL=...
MASTODON_ACCESS_TOKEN=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
REPLICATE_API_TOKEN=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
NOTION_PAGE_URL=https://www.notion.so/Your-Page-URL
NOTION_POLL_INTERVAL=60
```

## Run the workflow (CLI)

From the repo root:

```bash
python app/main.py
```

This starts the workflow and the Notion listener (if enabled in your `.env`).

The FastAPI backend is currently running on a GCP VM and exposes auto-generated API documentation at:
http://104.196.214.118:8000/docs