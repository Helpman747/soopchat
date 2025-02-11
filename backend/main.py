from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import ssl
import certifi
from backend.api import get_player_live
import websockets

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

        ssl_context = create_ssl_context()
        while True:  # 연결이 끊어지면 재연결 시도
            try:
                async with websockets.connect(
                    f"wss://{CHDOMAIN}:{CHPT}/Websocket/{BJID}",
                    ssl=ssl_context,
                    subprotocols=['chat'],
                    ping_interval=30,  # 30초마다 ping
                    ping_timeout=10    # 10초 동안 응답 없으면 timeout
                ) as ws:
                    # 최초 연결시 전달하는 패킷
                    CONNECT_PACKET = f'\x1b\t000100000600\x0c\x0c\x0c16\x0c'
                    # 메세지를 내려받기 위해 보내는 패킷
                    JOIN_PACKET = f'\x1b\t0002{len(CHATNO.encode("utf-8"))+6:06}00\x0c{CHATNO}\x0c\x0c\x0c\x0c\x0c'
                    # 주기적으로 핑을 보내서 메세지를 계속 수신하는 패킷
                    PING_PACKET = f'\x1b\t000000000100\x0c'

                    await ws.send(CONNECT_PACKET)
                    await asyncio.sleep(2)
                    await ws.send(JOIN_PACKET)

                    async def ping():
                        while True:
                            try:
                                await asyncio.sleep(30)  # 30초마다
                                await ws.send(PING_PACKET)
                            except Exception as e:
                                print(f"Ping error: {e}")
                                return

                    async def receive_messages():
                        while True:
                            try:
                                data = await ws.recv()
                                parts = data.split(b'\x0c')
                                messages = [part.decode('utf-8') for part in parts]
                                if len(messages) > 5 and messages[1] not in ['-1', '1'] and '|' not in messages[1]:
                                    user_id, comment, user_nickname = messages[2], messages[1], messages[6]
                                    await websocket.send_json({
                                        "type": "chat",
                                        "nickname": user_nickname,
                                        "message": comment
                                    })
                            except Exception as e:
                                print(f"Error processing message: {e}")
                                return

                    await asyncio.gather(
                        receive_messages(),
                        ping()
                    )

            except Exception as e:
                print(f"Connection error: {e}")
                await asyncio.sleep(5)  # 5초 후 재연결 시도
                continue

    except Exception as e:
        await websocket.send_json({"error": str(e)})

async def broadcast_message(message: dict):
    # 모든 클라이언트에게 메시지 전송
    for client in clients:
        try:
            await client.send_json(message)
        except:
            clients.remove(client) 