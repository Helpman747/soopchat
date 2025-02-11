import asyncio
from api import get_player_live
import websockets
import ssl
import certifi

class ChatWorker:
    def __init__(self, bj_id, callback):
        self.bj_id = bj_id
        self.callback = callback
        self.running = False

    async def start(self):
        self.running = True
        ssl_context = ssl.create_default_context()
        ssl_context.load_verify_locations(certifi.where())
        
        result = get_player_live(self.bj_id)
        if not result:
            return
            
        CHDOMAIN, CHATNO, FTK, TITLE, BJID, CHPT = result
        
        # 웹소켓 연결 및 채팅 수집
        async with websockets.connect(
            f"wss://{CHDOMAIN}:{CHPT}/Websocket/{BJID}",
            ssl=ssl_context
        ) as websocket:
            while self.running:
                data = await websocket.recv()
                chat = self.parse_chat(data)
                if chat:
                    await self.callback({
                        "type": "chat",
                        "nickname": chat["nickname"],
                        "message": chat["message"]
                    })

    def parse_chat(self, data):
        # 기존 채팅 파싱 로직
        pass 