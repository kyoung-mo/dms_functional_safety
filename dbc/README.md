# 📡 dbc — CAN 메시지 정의 (DBC) (예정)

> 차량 CAN 네트워크 메시지 규약 정의 파일  
> Vector CANdb++ 표준 포맷, cantools / CANalyzer 호환

---

## 🔧 Tech Stack

![CAN](https://img.shields.io/badge/CAN%20Bus-500kbps-FF6F00)
![Vector CANdb++](https://img.shields.io/badge/Vector-CANdb%2B%2B-E2001A)
![cantools](https://img.shields.io/badge/Python-cantools-3776AB?logo=python&logoColor=white)
![python-can](https://img.shields.io/badge/Python-python--can-3776AB?logo=python&logoColor=white)
![SocketCAN](https://img.shields.io/badge/Linux-SocketCAN-FCC624?logo=linux&logoColor=black)

---

## 개요

DMS 시스템에서 STM32 안전 제어 노드와 RPi5 네비 노드 간의  
CAN 통신 메시지를 정의한 DBC 파일.

Vector CANdb++ 표준 포맷으로 작성되어 CANoe, CANalyzer, cantools 등  
자동차 업계 표준 툴과 완전히 호환된다.

---

## CAN 버스 사양

| 항목 | 값 |
|---|---|
| 통신 속도 | **500 kbps** |
| 트랜시버 | SN65HVD230 |
| 버스 구조 | 선형(데이지체인) |
| 종단 저항 | 120Ω × 2개 (버스 양단) |
| 노드 구성 | STM32 (bxCAN) · RPi5 네비 (MCP2515) |

---

## CAN 메시지 전체 목록

| CAN ID | 메시지 명 | 방향 | DLC | 주기 | 구분 | 설명 |
|---|---|---|---|---|---|---|
| `0x100` | `DMS_State` | STM32 → RPi5 네비 | 3 bytes | 100ms | **구현** | 졸음 상태 + EAR 값 |
| `0x101` | `DMS_ACK` | RPi5 네비 → STM32 | 1 byte | 수신 시마다 | **구현** | 수신 확인 ACK |
| `0x7DF` | `DMS_DTC` | STM32 → CAN Bus | 8 bytes | 이벤트 | **구현** | 고장 코드 (Heartbeat 단절) |
| `0x200` | `DMS_ECU_Heartbeat` | STM32 → RPi5 네비 | 1 byte | 500ms | 예정 | STM32 생존 확인 |
| `0x110` | `DMS_SystemStatus` | STM32 → RPi5 네비 | 3 bytes | 1000ms | 예정 | 시스템 헬스 상태 |
| `0x120` | `DMS_Session` | STM32 → CAN Bus | 2 bytes | 이벤트 | 예정 | 주행 세션 시작·종료 |
| `0x102` | `DMS_Driver_Response` | RPi5 네비 → STM32 | 1 byte | 이벤트 | 예정 | 운전자 경고 확인 여부 |

---

## 시그널 정의 — 구현

### 0x100 — DMS_State

| 시그널명 | 위치 | 길이 | 범위 | 단위 | 설명 |
|---|---|---|---|---|---|
| `DMS_DrowsyState` | Byte 0 | 8bit | 0–2 | — | 0=정상 / 1=주의 / 2=위험 |
| `DMS_EAR_Scaled` | Byte 1 | 8bit | 0–100 | EAR×100 | EAR 값 (0.35 → 35) |
| `DMS_SeqNum` | Byte 2 | 8bit | 0–255 | — | 프레임 순서 번호 (롤오버) |

### 0x101 — DMS_ACK

| 시그널명 | 위치 | 길이 | 값 | 설명 |
|---|---|---|---|---|
| `DMS_ACK_Flag` | Byte 0 | 8bit | `0x01` | 수신 확인 |

### 0x7DF — DMS_DTC

| 시그널명 | 위치 | 길이 | 값 | 설명 |
|---|---|---|---|---|
| `DTC_Code` | Byte 0–1 | 16bit | `0xFF01` | Heartbeat 단절 DTC |
| `DTC_Severity` | Byte 2 | 8bit | `0x02` | 심각도 (중간) |
| `DTC_NodeID` | Byte 3 | 8bit | `0x01` | 발생 노드 ID |

> `0x7DF` — UDS(ISO 14229) 표준 진단 요청 ID 차용. 실차 진단 장비와 호환.

---

## 시그널 정의 — 예정

### 0x200 — DMS_ECU_Heartbeat

**추가 이유:** 현재 구조는 RPi5가 UART로 STM32에 Heartbeat를 보내 AI 노드 생존을 감시하지만,
역방향이 없다. 네비 노드는 STM32가 다운됐는지 알 방법이 없어 0x100이 끊겼을 때
"State=0 정상"인지 "STM32 다운"인지 구분할 수 없다. 0x200으로 대칭 감시를 완성한다.

| 시그널명 | 위치 | 길이 | 범위 | 설명 |
|---|---|---|---|---|
| `STM32_HB_Count` | Byte 0 | 8bit | 0–255 | 롤오버 카운터 (500ms 주기 증가) |

- 네비 노드가 1500ms 이상 미수신 시 → Firebase에 "STM32 이상" 이벤트 업로드
- SQLite에 노드 단절 로그 기록

---

### 0x110 — DMS_SystemStatus

**추가 이유:** 0x100은 감지 결과(State)만 전달한다. 카메라 케이블 이탈이나 RPi5 재부팅 중에도
State=0이 계속 오므로, 네비 노드와 Firebase 대시보드에서 "운전자 정상"인지
"카메라 고장"인지 구분할 수 없다. 감지 결과(State)와 시스템 헬스(Health)는 분리해야 한다.

| 시그널명 | 위치 | 길이 | 값 | 설명 |
|---|---|---|---|---|
| `AI_Node_Connected` | Byte 0 | 8bit | 0=단절 / 1=정상 | RPi5 UART 연결 상태 |
| `Camera_Status` | Byte 1 | 8bit | 0=이상 / 1=정상 | 카메라 프레임 수신 여부 |
| `Failsafe_Active` | Byte 2 | 8bit | 0=정상 / 1=진입 | Failsafe 진입 여부 |

---

### 0x120 — DMS_Session

**추가 이유:** 네비 노드의 SQLite와 Firebase에 이벤트가 쌓일 때, 시작·종료가 명시되지 않으면
"이번 주행"과 "다음 주행"의 경계를 타임스탬프만으로 추정해야 한다.
세션 ID가 있으면 Firebase 대시보드에서 "오늘 3회 운행, 각 졸음 횟수" 집계가 명확해진다.

| 시그널명 | 위치 | 길이 | 값 | 설명 |
|---|---|---|---|---|
| `Session_Type` | Byte 0 | 8bit | `0x01`=시작 / `0x02`=종료 | 주행 세션 이벤트 종류 |
| `Session_ID` | Byte 1 | 8bit | 0–255 | 세션 일련번호 (롤오버) |

- 세션 시작·종료 시 SQLite `sessions` 테이블에 기록
- Firebase Realtime DB에 세션 이벤트 업로드 → 대시보드 집계에 활용

---

### 0x102 — DMS_Driver_Response

**추가 이유:** 현재는 경고(LED/부저)를 발생시켜도 운전자가 인지했는지 확인할 방법이 없다.
네비 노드 5인치 터치스크린에서 운전자가 확인 버튼을 누르면 이를 STM32에 전달해
알림을 리셋할 수 있다. 미반응 시 부저 강도 에스컬레이션, Firebase에 "무응답 이벤트" 기록도 가능해진다.

| 시그널명 | 위치 | 길이 | 값 | 설명 |
|---|---|---|---|---|
| `Response_Type` | Byte 0 | 8bit | `0x01`=확인 / `0x02`=무응답 | 운전자 반응 여부 |

---

## 사용 방법

### cantools로 디코딩 (Python)

```python
import cantools

db = cantools.database.load_file('dbc/dms.dbc')

# 메시지 인코딩
msg = db.get_message_by_name('DMS_State')
data = msg.encode({
    'DMS_DrowsyState': 2,
    'DMS_EAR_Scaled': 32,
    'DMS_SeqNum': 17
})

# 메시지 디코딩
decoded = msg.decode(data)
print(decoded)
# {'DMS_DrowsyState': 2.0, 'DMS_EAR_Scaled': 32.0, 'DMS_SeqNum': 17.0}
```

### SocketCAN으로 실시간 모니터링

```bash
# CAN 인터페이스 활성화
sudo ip link set can0 up type can bitrate 500000

# DBC 기반 메시지 디코딩 모니터링
candump can0 | cantools decode dbc/dms.dbc

# 특정 ID만 필터링
candump can0,100:7FF
```

---

## 디렉토리 구조

```
dbc/
├── dms.dbc           # 메인 DBC 파일 (Vector CANdb++ 포맷)
├── dms_symbols.sym   # CANalyzer 심볼 파일 (선택)
└── README.md
```

---

## 개발 참고 사항

- DBC 수정 시 `../stm32/Core/Src/can_tx.c` 인코딩 로직과 반드시 동기화
- DBC 수정 시 `../rpi_navi/flask_server/can_reader.py` 디코딩 로직도 업데이트
- 예정 메시지는 DBC에 정의만 해두고 미구현 상태로 유지 가능
- cantools 설치: `pip install cantools python-can`
