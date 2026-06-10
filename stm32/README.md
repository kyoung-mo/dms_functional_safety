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

AI 노드(RPi5)가 다운되거나 응답이 끊겨도 **Watchdog Task가 독립적으로 동작**하여  
CAN DTC(`0x7DF`)를 자동 송출한다. AI 연산 부하에 관계없이 안전 기능이 항상 보장된다.

---

## FreeRTOS 4-Task 아키텍처

| 태스크 | 우선순위 | 주기 | 역할 |
|---|---|---|---|
| `Task_Watchdog` | **최상위 (5)** | 100ms | Heartbeat 감시, 500ms 단절 시 Failsafe + DTC `0x7DF` 송출 |
| `Task_CAN_Tx` | 높음 (4) | 100ms | 졸음 상태 CAN `0x100` 송신 (DBC 인코딩) |
| `Task_UART_Rx` | 중간 (3) | 인터럽트 | RPi5 바이너리 프레임 수신 · 상태머신 파싱 · Queue 전달 |
| `Task_Alert` | 중간 (3) | 100ms | LED 상태 표시 (State 0=꺼짐 / 1=500ms 깜빡 / 2=점등) |

---

## 핀맵

| 기능 | 핀 | CubeMX 설정 | 연결 대상 |
|---|---|---|---|
| CAN1_RX / TX | PB8 / PB9 | CAN1, 500kbps | SN65HVD230 트랜시버 |
| UART4_TX / RX | PA0 / PA1 | 115200/8N1, 인터럽트 | RPi5 AI 노드 (크로스 연결) |
| TIM2 | — | 500ms 인터럽트 | Heartbeat 타이머 |
| LED2 | PB14 | GPIO_Output | 졸음 상태 표시 |

> ⚠️ **주의:** B-L475E-IOT01A2 기본 초기화 시 온보드 UART4(PA0/PA1)가 핀을 선점함.  
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

/* UART 프레임 정의 */
#define UART_SYNC_BYTE          0xAA
#define UART_FRAME_SIZE         5         /* [SYNC, State, EAR×100, Seq, CRC] */

/* Heartbeat / Failsafe */
#define HEARTBEAT_TIMEOUT_MS    500       /* AI 노드 단절 판정 임계값 */
#define HEARTBEAT_COUNTER_MAX   5         /* 100ms 주기 × 5 = 500ms */

/* CAN */
#define CAN_TX_PERIOD_MS        100       /* 상태 메시지 송신 주기 */
#define CAN_DMS_STATE_ID        0x100     /* 졸음 상태 메시지 ID */
#define CAN_DTC_ID              0x7DF     /* UDS 표준 진단 요청 ID 차용 */
#define DTC_CODE                0xFF01    /* Heartbeat 단절 DTC */

/* FreeRTOS 우선순위 */
#define PRIORITY_WATCHDOG       5
#define PRIORITY_CAN_TX         4
#define PRIORITY_UART_RX        3
#define PRIORITY_ALERT          3
```

---

## Watchdog / Failsafe 동작 흐름

```
TIM2 인터럽트 (100ms 주기)
    → heartbeat_counter 감소
    → counter == 0 (500ms 경과):
        ├── CAN DTC 0x7DF 송출 (DTC_CODE = 0xFF01)
        ├── LED 소등 (State unknown)
        └── failsafe_flag = 1

UART 프레임 정상 수신 시:
    → heartbeat_counter = HEARTBEAT_COUNTER_MAX (리셋)
    → failsafe_flag = 0 (해제)
    → Queue에 State / EAR 값 전달 → Task_CAN_Tx, Task_Alert 처리
```

---

## UART 프레임 파싱 (상태머신)

```c
/* uart_parser.c — 상태머신 기반 파싱 */
typedef enum {
    WAIT_SYNC,    /* 0xAA 대기 */
    READ_STATE,   /* 졸음 상태 수신 */
    READ_EAR,     /* EAR×100 수신 */
    READ_SEQ,     /* 순서 번호 수신 */
    READ_CRC      /* 체크섬 검증 */
} UartParseState;

/* 체크섬 검증 */
uint8_t expected_crc = frame[1] ^ frame[2] ^ frame[3];
if (received_crc != expected_crc) { /* 프레임 파기 */ }
```

---

## CAN 송신 인코딩

```c
/* can_tx.c — DBC 기반 수동 인코딩 */
void CAN_Tx_DMS_State(uint8_t state, uint8_t ear_scaled, uint8_t seq) {
    uint8_t data[3];
    data[0] = state;       /* DMS_DrowsyState (Byte 0) */
    data[1] = ear_scaled;  /* DMS_EAR_Scaled  (Byte 1) */
    data[2] = seq;         /* DMS_SeqNum      (Byte 2) */

    TxHeader.StdId = 0x100;
    TxHeader.DLC   = 3;
    HAL_CAN_AddTxMessage(&hcan1, &TxHeader, data, &TxMailbox);
}

/* DTC 송출 */
void CAN_Tx_DTC(void) {
    uint8_t data[8] = {0xFF, 0x01, 0x02, 0x01, 0, 0, 0, 0};
    TxHeader.StdId = 0x7DF;
    TxHeader.DLC   = 8;
    HAL_CAN_AddTxMessage(&hcan1, &TxHeader, data, &TxMailbox);
}
```

---

## 빌드 및 플래시

```
1. STM32CubeIDE 실행
2. File → Import → Existing Projects into Workspace → stm32/ 선택
3. Project → Build All (Release 모드 권장)
4. Run → Debug/Flash (ST-Link/V2, 보드 내장 ST-Link 사용)
```

---

## 디렉토리 구조

```
stm32/
├── Core/
│   ├── Inc/
│   │   ├── dms_config.h        # 전역 상수 및 파라미터
│   │   ├── uart_parser.h
│   │   └── can_tx.h
│   └── Src/
│       ├── freertos.c          # 4-Task 정의 및 스케줄링
│       ├── uart_parser.c       # 바이너리 프레임 상태머신 파싱
│       ├── can_tx.c            # CAN 송신 (DBC 인코딩)
│       └── main.c              # HAL 초기화 및 OS 시작
├── Middlewares/
│   └── FreeRTOS/               # FreeRTOS 커널 (CubeMX 자동 생성)
├── dms_stm32.ioc               # CubeMX 프로젝트 파일
└── README.md
```

---

## 개발 환경

| 항목 | 값 |
|---|---|
| MCU | STM32L476RG (B-L475E-IOT01A2) |
| RTOS | FreeRTOS (CMSIS-RTOS v2) |
| IDE | STM32CubeIDE 1.14+ |
| Debugger | ST-Link/V2 (보드 내장) |
| CAN 트랜시버 | SN65HVD230 (3.3V 동작) |
| UART 연결 | PA0/PA1 ↔ RPi5 크로스 연결 (TX↔RX) |
