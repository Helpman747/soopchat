from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import ssl
import certifi
from api import get_player_live

app = FastAPI()

# 정적 파일 서비스 설정
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 연결된 웹소켓 클라이언트들
clients = set()

# SSL 컨텍스트 생성
def create_ssl_context():
    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(certifi.where())
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

# 메인 페이지
@app.get("/")
async def get():
    with open('frontend/index.html') as f:
        return HTMLResponse(f.read())

# 웹소켓 연결
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("start:"):
                bid = data.split(":")[1]
                await start_chat(bid, websocket)
    except:
        clients.remove(websocket)

async def start_chat(bid: str, websocket: WebSocket):
    try:
        result = get_player_live(bid)
        if not result:
            await websocket.send_json({"error": "방송 정보를 찾을 수 없습니다."})
            return

        CHDOMAIN, CHATNO, FTK, TITLE, BJID, CHPT = result
        await websocket.send_json({
            "type": "info",
            "data": {
                "title": TITLE,
                "bjid": BJID
            }
        })

        # 채팅 수집 로직...
        # (이전 코드의 websocket 연결 부분을 여기에 구현)

    except Exception as e:
        await websocket.send_json({"error": str(e)})

async def broadcast_message(message: dict):
    # 모든 클라이언트에게 메시지 전송
    for client in clients:
        try:
            await client.send_json(message)
        except:
            clients.remove(client) 