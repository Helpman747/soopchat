from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import ssl
import certifi
from backend.api import get_player_live
import websockets
import time

app = FastAPI()

# 정적 파일 서비스 설정
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 전역 변수로 현재 접속자 수 관리
connected_clients = set()

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
    connected_clients.add(websocket)
    
    # 모든 클라이언트에게 현재 접속자 수 전송
    await broadcast_message({
        "type": "viewers",
        "count": len(connected_clients)
    })
    
    try:
        while True:
            data = await websocket.receive_text()
            if data.startswith("start:"):
                bid = data.split(":")[1]
                await start_chat(bid, websocket)
    except:
        connected_clients.remove(websocket)
        # 접속 종료시에도 접속자 수 업데이트
        await broadcast_message({
            "type": "viewers",
            "count": len(connected_clients)
        })

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
        while True:  # 메인 루프
            try:
                async with websockets.connect(
                    f"wss://{CHDOMAIN}:{CHPT}/Websocket/{BJID}",
                    ssl=ssl_context,
                    subprotocols=['chat'],
                    ping_interval=30,
                    ping_timeout=10
                ) as ws:
                    # 연결 패킷 전송
                    await ws.send(f'\x1b\t000100000600\x0c\x0c\x0c16\x0c')
                    await asyncio.sleep(2)
                    await ws.send(f'\x1b\t0002{len(CHATNO.encode("utf-8"))+6:06}00\x0c{CHATNO}\x0c\x0c\x0c\x0c\x0c')

                    # 채팅 수신 루프
                    while True:
                        try:
                            data = await ws.recv()
                            parts = data.split(b'\x0c')
                            messages = [part.decode('utf-8') for part in parts]
                            
                            # 채팅 메시지 처리 부분 수정
                            if len(messages) > 5:
                                # 시청자 수 업데이트 메시지
                                if messages[1] == '0':
                                    viewer_count = int(messages[2])
                                    await websocket.send_json({
                                        "type": "stats",
                                        "data": {
                                            "viewers": viewer_count
                                        }
                                    })
                                
                                # 후원 메시지
                                elif '별풍선' in messages[1]:
                                    try:
                                        amount = int(''.join(filter(str.isdigit, messages[1])))
                                        await websocket.send_json({
                                            "type": "chat",
                                            "is_donation": True,
                                            "nickname": messages[6],
                                            "message": messages[1],
                                            "amount": amount
                                        })
                                    except:
                                        pass
                                
                                # 일반 채팅 메시지
                                elif not any(msg.startswith(('fw=', 'w=')) for msg in messages):
                                    if len(messages) > 6 and messages[1] != '1':  # 시스템 메시지 필터링
                                        nickname = messages[6]
                                        message = messages[1]
                                        
                                        # 시스템 메시지 필터링 (숫자|숫자 형태만 필터링)
                                        if not ('|' in message and all(part.isdigit() for part in message.split('|'))):
                                            # 후원 메시지 감지 (채팅으로 오는 후원 메시지)
                                            if any(keyword in message for keyword in ['별풍선', '스타풍선', '받았습니다', '선물받았습니다']):
                                                try:
                                                    # 숫자 추출 시도
                                                    amount = int(''.join(filter(str.isdigit, message)))
                                                    await websocket.send_json({
                                                        "type": "chat",
                                                        "is_donation": True,
                                                        "nickname": nickname,
                                                        "message": message,
                                                        "amount": amount
                                                    })
                                                except:
                                                    # 숫자를 추출할 수 없으면 일반 메시지로 처리
                                                    await websocket.send_json({
                                                        "type": "chat",
                                                        "is_donation": False,
                                                        "nickname": nickname,
                                                        "message": message
                                                    })
                                            else:
                                                # 일반 채팅 메시지
                                                await websocket.send_json({
                                                    "type": "chat",
                                                    "is_donation": False,
                                                    "nickname": nickname,
                                                    "message": message
                                                })

                            # 60초마다 ping 전송
                            if not hasattr(start_chat, 'last_ping') or \
                               time.time() - start_chat.last_ping > 30:
                                await ws.send('\x1b\t000000000100\x0c')
                                start_chat.last_ping = time.time()

                        except Exception as e:
                            print(f"Chat receive error: {e}")
                            break

            except Exception as e:
                print(f"Connection error: {e}")
                await asyncio.sleep(5)
                continue

    except Exception as e:
        await websocket.send_json({"error": str(e)})

async def broadcast_message(message: dict):
    # 리스트로 복사해서 순회하면서 set 수정
    disconnected_clients = set()
    
    for client in list(connected_clients):  # set을 리스트로 변환하여 순회
        try:
            await client.send_json(message)
        except:
            disconnected_clients.add(client)
    
    # 연결이 끊긴 클라이언트들 제거
    connected_clients.difference_update(disconnected_clients) 