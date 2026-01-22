#!/bin/bash
cd ~/sundai || mkdir -p ~/sundai && cd ~/sundai
python3 -m pip install --user -r requirements.txt
nohup python3 -m uvicorn api_server:app --host 0.0.0.0 --port 8000 > fastapi.log 2>&1 &
echo "FastAPI server started on port 8000"
echo "Check logs with: tail -f ~/sundai/fastapi.log"
