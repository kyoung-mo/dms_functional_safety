# ⚙️ stm32 — 실시간 안전 제어 노드 (FreeRTOS)

> STM32L476 + FreeRTOS 기반 4-Task 아키텍처 안전 제어 노드  
> UART Rx · CAN Tx · Watchdog/Failsafe · 경고 출력 우선순위 스케줄링

---

## 🔧 Tech Stack

![C](https://img.shields.io/badge/C-FreeRTOS-A8B9CC?logo=c&logoColor=black)
![STM32](https://img.shields.io/badge/STM32-L475%20IoT01A2-03234B?logo=stmicroelectronics&logoColor=white)
![FreeRTOS](https://img.shields.io/badge/FreeRTOS-CMSIS--RTOS%20v2-8CC84B)
![bxCAN](https://img.shields.io/badge/bxCAN-500kbps-FF6F00)
![SN65HVD230](https://img.shields.io/badge/Transceiver-SN65HVD230-FF8C00)
![STM32CubeIDE](https://img.shields.io/badge/IDE-STM32CubeIDE-03234B?logo=stmicroelectronics&logoColor=white)

---

## 개요

STM32L476 마이크로컨트롤러에 FreeRTOS를 올려 **4개의 우선순위 태스크**로 안전 제어를 담당한다.

AI 노드(RPi5)가 다운되거나 응답이 끊겨도 **Watchdog Task가 독립적으로 동작**하며
CAN DTC(`0x7DF`)를 자동 송출한다. AI 연산 부하에 관계없이 안전 기능이 항상 보장된다.

---

## FreeRTOS 4-Task 아키텍처

| 태스크 | 우선순위 | 주기 | 역할 |
|---|---|---|---|
| `Task_Watchdog` | **최상위 (5)** | 100ms | Heartbeat 감시, 500ms 단절 시 Failsafe + DTC `0x7DF` 송출 |
| `Task_CAN_Tx` | 높음 (4) | 100ms | 졸음 상태 CAN `0x100` 송신, ECU Heartbeat `0x200` 송신 (예정) |
| `Task_UART_Rx` | 중간 (3) | 인터럽트 | RPi5 바이너리 프레임 수신 · 상태머신 파싱 · Queue 전달 |
| `Task_Alert` | 중간 (3) | 100ms | LED 상태 표시 (State 0=꺼짐 / 1=500ms 깜빡 / 2=점등) |

---

## CAN 송신 메시지

### 구현

| CAN ID | 메시지 명 | 주기 | 설명 |
|---|---|---|---|
| `0x100` | `DMS_State` | 100ms | 졸음 상태 (0/1/2) + EAR×100 + SeqNum |
| `0x7DF` | `DMS_DTC` | 이벤트 | Heartbeat 단절 시 고장 코드 자동 송출 |

### 예정

| CAN ID | 메시지 명 | 주기 | 설명 |
|---|---|---|---|
| `0x200` | `DMS_ECU_Heartbeat` | 500ms | STM32 생존 확인용 역방향 Heartbeat. 네비 노드가 STM32 단절을 감지할 수 있게 함 |
| `0x110` | `DMS_SystemStatus` | 1000ms | AI 노드 연결 상태 · 카메라 상태 · Failsafe 진입 여부를 별도 메시지로 송신. 감지 결과(0x100)와 시스템 헬스를 분리 |
| `0x120` | `DMS_Session` | 이벤트 | 시동 ON/OFF 시 주행 세션 시작·종료 이벤트 송출. 네비 노드 SQLite에서 세션 단위 집계 가능 |

## CAN 수신 메시지

### 구현

| CAN ID | 메시지 명 | 설명 |
|---|---|---|
| `0x101` | `DMS_ACK` | 네비 노드 수신 확인 |

### 예정

| CAN ID | 메시지 명 | 설명 |
|---|---|---|
| `0x102` | `DMS_Driver_Response` | 네비 노드 터치스크린에서 운전자가 경고 확인 버튼 누름 → STM32 알림 리셋 및 에스컬레이션 중단 |

---

## 핀맵

| 기능 | 핀 | CubeMX 설정 | 연결 대상 |
|---|---|---|---|
| CAN1_RX / TX | PB8 / PB9 | CAN1, 500kbps | SN65HVD230 트랜시버 |
| UART4_TX / RX | PA0 / PA1 | 115200/8N1, 인터럽트 | RPi5 AI 노드 (크로스 연결) |
| TIM2 | — | 500ms 인터럽트 | Heartbeat 타이머 |
| LED2 | PB14 | GPIO_Output | 졸음 상태 표시 |

> ⚠️ B-L475E-IOT01A2 기본 초기화 시 온보드 UART4(PA0/PA1)가 핀을 선점함.  
> 반드시 온보드 주변장치를 비활성화한 `base.ioc`에서 프로젝트를 시작할 것.

---

## CubeMX 설정

```
CAN1:    Prescaler=10, BS1=13TQ, BS2=2TQ  →  500 kbps (SYSCLK 80MHz)
UART4:   115200/8N1, HAL_UART_Receive_IT (인터럽트 수신)
TIM2:    Prescaler=8000-1, Period=5000-1  →  500ms @ 80MHz
Clock:   HSI 16MHz → PLL → SYSCLK 80MHz
FreeRTOS: CMSIS-RTOS v2, configTICK_RATE_HZ=1000
```

---

## 주요 파라미터

```c
/* Core/Inc/dms_config.h */

/* UART 프레임 */
#define UART_SYNC_BYTE          0xAA
#define UART_FRAME_SIZE         5

/* Heartbeat / Failsafe */
#define HEARTBEAT_TIMEOUT_MS    500
#define HEARTBEAT_COUNTER_MAX   5       /* 100ms × 5 = 500ms */

/* CAN ID — 구현 */
#define CAN_DMS_STATE_ID        0x100
#define CAN_DMS_ACK_ID          0x101
#define CAN_DTC_ID              0x7DF
#define DTC_CODE                0xFF01  /* Heartbeat 단절 DTC */

/* CAN ID — 예정 */
#define CAN_ECU_HB_ID           0x200
#define CAN_SYS_STATUS_ID       0x110
#define CAN_SESSION_ID          0x120
#define CAN_DRIVER_RESP_ID      0x102

/* FreeRTOS 우선순위 */
#define PRIORITY_WATCHDOG       5
#define PRIORITY_CAN_TX         4
#define PRIORITY_UART_RX        3
#define PRIORITY_ALERT          3
```

---

## Watchdog / Failsafe 동작 흐름

```
TIM2 인터럽트 (100ms)
    → heartbeat_counter 감소
    → counter == 0 (500ms 경과):
        ├── CAN DTC 0x7DF 송출 (DTC_CODE = 0xFF01)
        ├── LED 소등
        └── failsafe_flag = 1

UART 프레임 정상 수신:
    → heartbeat_counter = HEARTBEAT_COUNTER_MAX
    → failsafe_flag = 0
    → Queue → Task_CAN_Tx, Task_Alert 처리
```

---

## CAN 송신 코드 (구현)

```c
/* can_tx.c */
void CAN_Tx_DMS_State(uint8_t state, uint8_t ear_scaled, uint8_t seq) {
    uint8_t data[3];
    data[0] = state;
    data[1] = ear_scaled;
    data[2] = seq;
    TxHeader.StdId = CAN_DMS_STATE_ID;
    TxHeader.DLC   = 3;
    HAL_CAN_AddTxMessage(&hcan1, &TxHeader, data, &TxMailbox);
}

void CAN_Tx_DTC(void) {
    uint8_t data[8] = {0xFF, 0x01, 0x02, 0x01, 0, 0, 0, 0};
    TxHeader.StdId = CAN_DTC_ID;
    TxHeader.DLC   = 8;
    HAL_CAN_AddTxMessage(&hcan1, &TxHeader, data, &TxMailbox);
}

/* 예정 */
void CAN_Tx_ECU_Heartbeat(uint8_t count) { /* 0x200 */ }
void CAN_Tx_SystemStatus(uint8_t ai_conn, uint8_t cam, uint8_t failsafe) { /* 0x110 */ }
void CAN_Tx_Session(uint8_t type, uint8_t session_id) { /* 0x120 */ }
```

---

## UART 프레임 파싱 (상태머신)

```c
/* uart_parser.c */
typedef enum {
    WAIT_SYNC, READ_STATE, READ_EAR, READ_SEQ, READ_CRC
} UartParseState;

/* 체크섬: Byte1 XOR Byte2 XOR Byte3 */
uint8_t expected = frame[1] ^ frame[2] ^ frame[3];
if (received_crc != expected) { /* 프레임 파기 */ }
```

---

## 빌드 및 플래시

```
1. STM32CubeIDE → stm32/ 프로젝트 열기
2. Project → Build All (Release 모드)
3. Run → Flash (ST-Link/V2, 보드 내장)
```

---

## 디렉토리 구조

```
stm32/
├── Core/
│   ├── Inc/
│   │   ├── dms_config.h        # 전역 상수 (CAN ID, Timeout, 우선순위)
│   │   ├── uart_parser.h
│   │   └── can_tx.h
│   └── Src/
│       ├── freertos.c          # 4-Task 정의 및 스케줄링
│       ├── uart_parser.c       # 바이너리 프레임 상태머신 파싱
│       ├── can_tx.c            # CAN 송신 (구현 + 예정 stub)
│       └── main.c
├── Middlewares/FreeRTOS/
├── dms_stm32.ioc
└── README.md
```

---

## 개발 환경

| 항목 | 값 |
|---|---|
| MCU | STM32L476RG (B-L475E-IOT01A2) |
| RTOS | FreeRTOS (CMSIS-RTOS v2) |
| IDE | STM32CubeIDE 1.14+ |
| CAN 트랜시버 | SN65HVD230 (3.3V 동작) |
| UART 연결 | PA0/PA1 ↔ RPi5 크로스 연결 (TX↔RX) |
