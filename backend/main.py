from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
from chat_worker import ChatWorker

app = FastAPI()
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 연결된 웹소켓 클라이언트들
clients = set()

# 채팅 워커
chat_worker = None

@app.get("/")
async def get():
    with open('frontend/index.html') as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            if data.startswith("start:"):
                # 채팅 수집 시작
                bj_id = data.split(":")[1]
                if not chat_worker:
                    chat_worker = ChatWorker(bj_id, broadcast_message)
                    await chat_worker.start()
    except:
        clients.remove(websocket)

async def broadcast_message(message: dict):
    # 모든 클라이언트에게 메시지 전송
    for client in clients:
        try:
            await client.send_json(message)
        except:
            clients.remove(client) 