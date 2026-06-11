# 🗺️ rpi5_navi — 네비게이션 · 관제 연동 노드

> RPi5 기반 Flask 웹서버 + 카카오맵 JS + Firebase GPS·이벤트 저장 + 관제 센터 웹  
> CAN 0x100 수신(MCP2515) → 졸음 이벤트·GPS 경로 Firebase 저장 → 관제 센터에서 통합 조회

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

CAN Bus에서 STM32의 졸음 상태(`0x100`)·DTC(`0x7DF`)를 MCP2515로 수신하고,
`0x100` 수신 시마다 ACK(`0x101`)를 응답한다.
Firebase Realtime DB에서 GPS 좌표를 폴링하여 카카오맵에 실시간으로 표시한다.

졸음 이벤트(State=2) 발생 시 GPS 좌표·시각을 **Firebase에 저장**하고,
운전자별 / 세션별 주행 이력을 관제 센터 웹 대시보드에서 통합 조회할 수 있다.

---

## 데이터 흐름

```
STM32 CAN 0x100 (100ms 주기)
    → MCP2515 (SPI-CAN) → SocketCAN (can0)
    → Flask can_reader_thread (cantools 디코딩)
    → Flask-SocketIO → 카카오맵 JS → 졸음 이벤트 마커 실시간 표시
    → Firebase /sessions/{driver_id}/{session_id}/events/ → 졸음 이벤트 저장 (State=2)
    → SQLite → 로컬 이벤트 로그 백업

삼성폰 PWA geolocation
    → Firebase /gps/{driver_id}  (실시간 현재 위치 업데이트)
    → RPi5 네비 2초 폴링 → 카카오맵 실시간 경로 표시
    → Firebase /sessions/{driver_id}/{session_id}/gps_path/ → GPS 경로 저장

[관제 센터 웹]
    Firebase /drivers, /sessions, /gps 직접 조회
    → 운전자별 프로필 / 주행 세션 이력 / GPS 경로 / 졸음 이벤트 위치
```

---

## Firebase DB 구조

```
/drivers/{driver_id}/profile
  name:    "구영모"
  phone:   "010-0000-0000"
  email:   "kym@example.com"
  photo:   "url"

/sessions/{driver_id}/{session_id}/
  start_time:  "2026-06-10T09:00:00"
  end_time:    "2026-06-10T09:20:00"
  gps_path/
    0: {lat: 37.53, lon: 126.85, timestamp: "..."}
    1: {lat: 37.54, lon: 126.86, timestamp: "..."}
  events/
    0: {timestamp: "...", state: 2, lat: 37.53, lon: 126.85}

/gps/{driver_id}
  lat: 37.53074
  lon: 126.85268
  timestamp: "..."
```

---

## 주요 기능

| 기능 | 설명 | 상태 |
|---|---|---|
| **실시간 네비게이션** | 카카오맵 JS SDK로 GPS 경로 실시간 표시 | 구현 |
| **졸음 이벤트 핀** | State=2 발생 위치에 빨간 마커 표시 | 구현 |
| **Firebase 이벤트 저장** | 졸음 이벤트·GPS 경로를 Firebase에 업로드 | 구현 |
| **관제 센터 웹** | 운전자별 주행 세션·GPS 경로·이벤트 통합 조회 | 구현 |
| **졸음 세션 관리** | 마지막 State=2 이후 5초 쿨다운으로 1 에피소드 집계 | 구현 |
| **연결 상태 배너** | AI 노드 Heartbeat 단절 시 화면에 경고 배너 표시 | 구현 |
| **CAN 로그 팝업** | 수신된 CAN 메시지 실시간 로그 확인 | 구현 |
| **DTC 알림 수신** | `0x7DF` 수신 시 SocketIO `dtc_alert` 이벤트 발행 | 구현 |
| **SQLite 로컬 백업** | 이벤트 로컬 저장 (네트워크 단절 대비) | 구현 |
| **STM32 Heartbeat 감시** | `0x200` 미수신 시 화면 배너 + Firebase 이상 이벤트 | 예정 |
| **시스템 헬스 표시** | `0x110` 수신하여 카메라·AI 노드 상태 상단 표시 | 예정 |
| **세션 경계 기록** | `0x120` 수신 시 Firebase 세션 시작·종료 자동 기록 | 예정 |
| **운전자 경고 확인** | 터치 버튼 → `0x102` 송신 → STM32 알림 리셋 | 예정 |

---

## CAN 수신/송신 메시지

### 구현

| CAN ID | 방향 | 처리 내용 |
|---|---|---|
| `0x100` | STM32 → 수신 | ID 필터링 후 졸음 상태 파싱 → 카카오맵 핀 표시 + Firebase 이벤트 저장 |
| `0x101` | 송신 → STM32 | `0x100` 수신 시마다 ACK 송신 (try/except로 송신 실패가 수신 루프에 영향 없도록 처리) |
| `0x7DF` | STM32 → 수신 | DTC 수신 → 콘솔 로그 + SocketIO `dtc_alert` 이벤트 발행 |

### 예정

| CAN ID | 방향 | 처리 내용 |
|---|---|---|
| `0x200` | STM32 → 수신 | STM32 생존 감시 — STM32 측 송신은 구현 완료, 네비 측 타임아웃 감시 로직 예정 |
| `0x110` | STM32 → 수신 | AI 노드·카메라·Failsafe 상태를 상단 상태바에 표시 |
| `0x120` | STM32 → 수신 | 세션 시작(0x01)/종료(0x02) → Firebase 세션 경계 기록 |
| `0x102` | 송신 → STM32 | 터치스크린 확인 버튼 → STM32 알림 리셋 |

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
cd rpi5_navi
PYTHONPATH=. python flask_server/app.py

# 관제 센터 웹 접속
# http://localhost:5000/fleet  (관제 센터)
# http://localhost:5000        (네비게이션 화면)

# Chromium 전체화면 (5인치 디스플레이)
chromium-browser --kiosk http://localhost:5000

alias dms='PYTHONPATH=. python ~/projects/dms/rpi5_navi/flask_server/app.py'
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

---

## 환경 변수

```bash
# .env
FIREBASE_URL=https://your-project-default-rtdb.firebaseio.com
KAKAO_MAP_KEY=your_kakao_js_api_key
DRIVER_ID=kym
```

---

## 주요 파라미터

```python
# config.py
CAN_INTERFACE     = "can0"
CAN_BITRATE       = 500000
FIREBASE_POLL_S   = 2           # GPS 폴링 간격 (초)
DROWSY_COOLDOWN_S = 5           # 졸음 세션 쿨다운 (초)
SAVE_STATE        = 2           # Firebase/SQLite 저장 기준 State
STM32_HB_TIMEOUT  = 1.5         # 0x200 미수신 판정 임계 (초, 예정)
```

---

## 디렉토리 구조

```
rpi5_navi/
├── flask_server/
│   ├── app.py                  # Flask + SocketIO + can_reader_thread (0x100/0x7DF 분기, 0x101 ACK)
│   └── templates/              # 카카오맵 네비 · 관제 센터 웹
├── gps/
│   └── firebase_gps.py         # Firebase GPS 폴링·이벤트 저장 (MIN_DIST_M 거리 필터)
├── db/
│   └── log.py                  # SQLite 로컬 백업
└── README.md
```

---

## 의존성 설치

```bash
pip install flask flask-socketio python-can cantools \
            firebase-admin python-dotenv
```

---

## 개발 환경

| 항목 | 값 |
|---|---|
| Board | Raspberry Pi 5 |
| Python | 3.13.5 |
| CAN 모듈 | MCP2515 (SPI0, 8MHz, GPIO25 인터럽트) |
| 디스플레이 | 5인치 DSI/HDMI (Chromium kiosk) |

---

## 주의 사항

- MCP2515 점퍼: J3/C3 → **J1** 위치 이동 (레벨시프터 없이 직결)
- Firebase Mixed Content 우회: 삼성폰 geolocation → Firebase → RPi5 2초 폴링 구조
- 졸음 이벤트는 **State=2 시에만** Firebase/SQLite 저장 (State=1은 화면 표시만)
- driver_id는 `.env` 파일로 차량별 구분 → 관제 센터에서 운전자 식별
- CAN 수신 루프는 반드시 `arbitration_id`로 분기할 것 — 필터 없이 `data[0]`을 state로 읽으면 `0x7DF`의 `0xFF`를 졸음 상태로 오인하는 버그 발생 (수정 완료)
