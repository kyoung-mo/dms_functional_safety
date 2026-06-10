# 📡 dbc — CAN 메시지 정의 (DBC)

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

Vector CANdb++ 표준 포맷으로 작성되어 CANoe, CANalyzer, cantools, CANdb++ 등  
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

## CAN 메시지 정의

| CAN ID | 메시지 명 | 방향 | DLC | 주기 | 설명 |
|---|---|---|---|---|---|
| `0x100` | `DMS_State` | STM32 → RPi5 네비 | 3 bytes | 100ms | 졸음 상태 + EAR 값 |
| `0x101` | `DMS_ACK` | RPi5 네비 → STM32 | 1 byte | 수신 시마다 | 수신 확인 ACK |
| `0x7DF` | `DMS_DTC` | STM32 → CAN Bus | 8 bytes | 이벤트 | 고장 코드 (Heartbeat 단절 시) |

---

## 시그널 정의

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

> `0x7DF` — UDS(ISO 14229) 표준 진단 요청 ID 차용. 실차 진단 장비(CANalyzer, PCAN)와 호환.

---

## 사용 방법

### cantools로 디코딩 (Python)

```python
import cantools
import can

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

- DBC 수정 시 `../stm32/Core/Src/can_tx.c`의 인코딩 로직과 반드시 동기화
- DBC 수정 시 `../rpi_navi/flask_server/can_reader.py`의 디코딩 로직도 업데이트
- cantools 설치: `pip install cantools python-can`
