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

## Run the local website (backend + frontend)

1) Start the FastAPI backend (repo root):

```bash
python -m uvicorn app.api.server:app --host 0.0.0.0 --port 8000 --reload
```

If you see `No module named uvicorn`, install dependencies first:

```bash
pip install -r requirements.txt
```

(`unicorn` is a typo; the module name is `uvicorn`.)

API docs will be available at:
`http://localhost:8000/docs`

2) In a second terminal, start the frontend:

```bash
cd client
npm install
npm run dev
```

Frontend URL:
`http://localhost:5173`

The frontend connects to:
`ws://localhost:8000/ws/chat`

## Optional: run backend with Gunicorn

For Linux/macOS production-style serving (instead of `uvicorn --reload`):

```bash
gunicorn app.api.server:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```
