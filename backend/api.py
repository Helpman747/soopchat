import requests

def get_current_broadcast_no(bid):
    url = f'https://live.afreecatv.com/afreeca/player_live_api.php'
    data = {
        'bid': bid,
        'type': 'live',
        'player_type': 'html5',
    }
    
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        data = response.json()
        
        print(f"DEBUG: API 응답: {data}")  # 디버그용 출력 추가
        
        if data.get('CHANNEL', {}).get('BNO'):
            return data['CHANNEL']['BNO']
        else:
            print("  DEBUG: 방송 번호를 찾을 수 없습니다")
        return None
        
    except Exception as e:
        print(f"  ERROR: 방송 정보를 가져오는데 실패했습니다: {e}")
        print(f"  DEBUG: 응답 내용: {response.text if 'response' in locals() else '없음'}")
        return None

def get_player_live(bid):
    # 현재 방송 번호 가져오기
    bno = get_current_broadcast_no(bid)
    if not bno:
        print("  ERROR: 현재 방송 중이 아닙니다.")
        return None
        
    url = 'https://live.afreecatv.com/afreeca/player_live_api.php'
    data = {
        'bid': bid,
        'bno': bno,
        'type': 'live',
        'confirm_adult': 'false',
        'player_type': 'html5',
        'mode': 'landing',
        'from_api': '0',
        'pwd': '',
        'stream_type': 'common',
        'quality': 'HD'
    }

    try:
        response = requests.post(f'{url}?bjid={bid}', data=data)
        response.raise_for_status()  # HTTP 요청 에러를 확인하고, 에러가 있을 경우 예외를 발생시킵니다.
        res = response.json()

        CHDOMAIN = res["CHANNEL"]["CHDOMAIN"].lower()
        CHATNO = res["CHANNEL"]["CHATNO"]
        FTK = res["CHANNEL"]["FTK"]
        TITLE = res["CHANNEL"]["TITLE"]
        BJID = res["CHANNEL"]["BJID"]
        CHPT = str(int(res["CHANNEL"]["CHPT"]) + 1)

        return CHDOMAIN, CHATNO, FTK, TITLE, BJID, CHPT

    except requests.RequestException as e:
        print(f"  ERROR: API 요청 중 오류 발생: {e}")
        return None
    except KeyError as e:
        print(f"  ERROR: 응답에서 필요한 데이터를 찾을 수 없습니다: {e}")
        return None