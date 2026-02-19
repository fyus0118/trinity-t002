from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from notion_client import Client
import openai
import os
from datetime import datetime, timezone, timedelta

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# 環境変数の読み込み (Renderの設定画面で後ほど入力します)
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
TASK_DB_ID = os.getenv("TASK_DB_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

notion = Client(auth=NOTION_TOKEN)
openai.api_key = OPENAI_API_KEY

def check_stagnation():
    """ 
    判定ロジック: 
    ステータスが「In Progress」かつ、最終更新から「2時間(120分)」経過したタスクを1つ抽出。
    """
    now = datetime.now(timezone.utc)
    threshold = (now - timedelta(minutes=120)).isoformat()
    
    try:
        response = notion.databases.query(
            database_id=TASK_DB_ID,
            filter={
                "and": [
                    {"property": "Status", "status": {"equals": "In Progress"}},
                    {"property": "Last Edited Time", "last_edited_time": {"before": threshold}}
                ]
            },
            sorts=[{"property": "Last Edited Time", "direction": "ascending"}], # 最も古いものから
            page_size=1
        )
        if response["results"]:
            return response["results"][0]["properties"]["Name"]["title"][0]["plain_text"]
    except Exception as e:
        print(f"Error checking Notion: {e}")
    return None

def get_tactical_command(task_name):
    """ GPT-4o: 軍事的なマイクロタスク指令を生成 """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": "You are a tactical AI. The user is stuck. Generate a specific, ridiculously easy '5-minute entry action' in Japanese. Tone: Military, Commanding. Max 35 chars."
                },
                {
                    "role": "user", 
                    "content": f"Target: {task_name}"
                }
            ]
        )
        return response.choices[0].message.content
    except:
        return "直ちに着手せよ。"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    stuck_task = check_stagnation()
    
    if stuck_task:
        # 🚨 ALERT MODE
        command = get_tactical_command(stuck_task)
        return templates.TemplateResponse("widget.html", {
            "request": request, 
            "mode": "alert",
            "task_name": stuck_task,
            "command": command
        })
    else:
        # 🟢 NORMAL MODE
        return templates.TemplateResponse("widget.html", {
            "request": request, 
            "mode": "normal",
            "task_name": "No Stagnation",
            "command": "Monitoring..."
        })