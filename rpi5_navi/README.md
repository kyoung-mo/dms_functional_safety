# 🗺️ rpi_navi — 네비게이션 · 관제 연동 노드

> RPi5 기반 Flask 웹서버 + 카카오맵 JS + Firebase GPS + SQLite 이벤트 로그  
> CAN 0x100 수신(MCP2515) → 졸음 이벤트 위치 기록 → 중앙 관제 서버 릴레이

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.13.5-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-SocketIO-000000?logo=flask&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Realtime%20DB-FFCA28?logo=firebase&logoColor=black)
![Kakao Maps](https://img.shields.io/badge/Kakao%20Maps-JS%20SDK-FFCD00)
![SQLite](https://img.shields.io/badge/SQLite-Local%20DB-003B57?logo=sqlite&logoColor=white)
![MCP2515](https://img.shields.io/badge/MCP2515-SPI--CAN-FF6F00)
![cantools](https://img.shields.io/badge/Python-cantools-3776AB?logo=python&logoColor=white)
![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi%205-네비%20노드-A22846?logo=raspberrypi&logoColor=white)

---

## 개요

CAN Bus에서 STM32의 졸음 상태(CAN `0x100`)를 MCP2515로 수신하고,  
Firebase Realtime DB에서 GPS 좌표를 폴링하여 카카오맵에 실시간으로 표시한다.  
졸음 이벤트(State=2) 발생 시 위치·시각을 SQLite에 기록하고  
중앙 관제 서버(Fleet Management)로 이벤트를 릴레이한다.

---

## 데이터 흐름

```
STM32 CAN 0x100 (100ms 주기)
    → MCP2515 (SPI-CAN)
    → SocketCAN (can0)
    → Flask can_reader_thread
    → Flask-SocketIO 이벤트 → 카카오맵 핀 표시
    → SQLite 이벤트 로그 기록 (State=2 시만)
    → 중앙 관제 서버 HTTP POST 릴레이

삼성폰 PWA geolocation
    → Firebase Realtime DB
    → firebase_poll.py (2초 간격 폴링)
    → Flask-SocketIO → 카카오맵 실시간 경로 표시
```

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| **실시간 네비게이션** | 카카오맵 JS SDK로 GPS 경로 실시간 표시 |
| **졸음 이벤트 핀** | State=2 발생 위치에 빨간 마커 표시 |
| **졸음 세션 관리** | 마지막 State=2 이후 5초 쿨다운으로 1 에피소드 집계 |
| **연결 상태 표시** | AI 노드 Heartbeat 단절 시 연결 끊김 배너 표시 |
| **CAN 로그 팝업** | 수신된 CAN 메시지 실시간 로그 확인 |
| **SQLite 로깅** | 졸음 이벤트 GPS 좌표 · 시각 영구 저장 |
| **Fleet 릴레이** | 이벤트를 중앙 관제 서버로 HTTP POST |

---

## 실행 방법

```bash
# MCP2515 CAN 인터페이스 활성화
# /boot/firmware/config.txt 에 추가 후 재부팅:
# dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
# dtparam=spi=on

sudo ip link set can0 up type can bitrate 500000
sudo ip link set can0 txqueuelen 1000

# Flask 서버 실행
cd rpi_navi
PYTHONPATH=. python flask_server/app.py

# 쉘 앨리어스 (선택)
alias dms='PYTHONPATH=. python ~/dms/rpi_navi/flask_server/app.py'

# Chromium 전체화면 (5인치 디스플레이)
chromium-browser --kiosk http://localhost:5000
```

---

## MCP2515 하드웨어 설정

| 항목 | 값 |
|---|---|
| 오실레이터 | **8 MHz** |
| SPI 버스 | SPI0 (기본) |
| 인터럽트 핀 | GPIO25 |
| CAN 속도 | 500 kbps |
| 점퍼 위치 | **J1** (레벨시프터 없이 RPi5 직결) |

```bash
# /boot/firmware/config.txt
dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
dtparam=spi=on
```

---

## 환경 변수 설정

```bash
# .env
FIREBASE_URL=https://your-project-default-rtdb.firebaseio.com
KAKAO_MAP_KEY=your_kakao_js_api_key
FLEET_SERVER_URL=http://your-fleet-server/api/events
VEHICLE_ID=truck-001
```

---

## 주요 파라미터

```python
# config.py
CAN_INTERFACE     = "can0"
CAN_BITRATE       = 500000
FIREBASE_POLL_S   = 2           # GPS 폴링 간격 (초)
DROWSY_COOLDOWN_S = 5           # 졸음 세션 쿨다운 (초)
SAVE_STATE        = 2           # SQLite 저장 기준 State
```

---

## 디렉토리 구조

```
rpi_navi/
├── flask_server/
│   ├── app.py                  # Flask + SocketIO 메인 서버
│   ├── can_reader.py           # MCP2515 CAN 수신 스레드 (cantools 디코딩)
│   └── templates/
│       ├── navi.html           # 카카오맵 네비게이션 화면
│       └── dashboard.html      # 주행 분석 대시보드
├── firebase_poll.py            # Firebase GPS 폴링 (2초 간격)
├── db.py                       # SQLite 이벤트 로그 저장/조회
├── fleet_relay.py              # 중앙 관제 서버 HTTP POST 릴레이
├── config.py                   # 환경 변수 로드
└── README.md
```

---

## 의존성 설치

```bash
pip install flask flask-socketio python-can cantools \
            requests firebase-admin python-dotenv
```

---

## 개발 환경

| 항목 | 값 |
|---|---|
| Board | Raspberry Pi 5 |
| Python | 3.13.5 |
| CAN 모듈 | MCP2515 (SPI0, 8MHz 오실레이터, GPIO25 인터럽트) |
| 디스플레이 | 5인치 DSI / HDMI (Chromium kiosk 전체화면) |
| OS | Raspberry Pi OS Bookworm (64-bit) |

---

## 주의 사항

- MCP2515 모듈: 점퍼를 J3/C3 → **J1** 위치로 이동 (레벨시프터 없이 직결)
- Firebase HTTPS Mixed Content 우회: 삼성폰 geolocation → Firebase → RPi5 폴링 구조로 우회
- 졸음 이벤트 마커 저장은 **State=2 시에만** 수행 (State=1은 화면 표시만)
