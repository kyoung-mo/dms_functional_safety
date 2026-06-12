# ⚙️ stm32 — 실시간 안전 제어 노드 (Bare-metal → FreeRTOS)

> STM32L475 기반 안전 제어 노드 — 베어메탈/FreeRTOS 두 가지 구현을 모두 포함  
> UART Rx · CAN Tx/Rx · Watchdog/Failsafe · DTC 송출, 전 기능 candump/cangaroo 실측 검증 완료

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

STM32L475 마이크로컨트롤러가 시스템의 **안전 제어**를 전담한다.

AI 노드(RPi5)가 다운되거나 응답이 끊겨도 STM32는 **독립적으로 Heartbeat를 감시**하며
CAN DTC(`0x7DF`)를 자동 송출한다. AI 연산 부하·다운과 무관하게 안전 기능이 항상 보장된다.

같은 기능을 **베어메탈과 FreeRTOS 두 방식으로 구현**하여,
RTOS 도입이 안전 기능 반응 속도에 주는 효과를 실측으로 비교했다.

```
DMS_init       → 핀맵·클럭만 잡힌 공통 베이스 (온보드 주변장치 비활성화)
DMS_baremetal  → while 루프 + TIM2 인터럽트 구조 (검증 완료)
DMS_FreeRTOS   → 4-Task 우선순위 스케줄링 구조 (검증 완료, 최종 채택)
```

---

## Flow Chart (Watchdog/Failsafe)

<img width="993" height="800" alt="image" src="https://github.com/user-attachments/assets/2a8072df-01e4-4655-b3b4-ca2c19dd2772" />

---

## 베어메탈 vs FreeRTOS — 실측 비교

| 항목 | DMS_baremetal | DMS_FreeRTOS |
|---|---|---|
| 구조 | while(1) 순차 처리 + TIM2 500ms 인터럽트 | 4-Task 우선순위 선점 스케줄링 |
| Heartbeat 감시 주체 | TIM2 콜백 (500ms 해상도) | Task_Watchdog (100ms 해상도) |
| **AI 단절 → DTC 송출** | **~1.5초** | **~0.6초 (2.5배 개선)** |
| 안전 기능 보장 | 다른 처리에 밀릴 수 있음 | 최상위 우선순위로 항상 보장 |
| 태스크 간 데이터 전달 | 전역 변수 | 메시지 큐 (`q_dms_state`) + volatile |

> DTC 반응 시간은 `candump -t a` 타임스탬프 실측 기준 (AI 노드 Ctrl+C → `0x7DF` 등장까지).

---

## FreeRTOS 4-Task 아키텍처 (구현·검증 완료)

| 태스크 | 우선순위 | 스택 | 역할 |
|---|---|---|---|
| `Task_Watchdog` | **osPriorityRealtime** | 256 | 100ms 주기 Seq 비교 — 5회 연속 무변화(500ms) 시 `rpi_alive=0` + DTC `0x7DF` 송출 (1회, 복구 시 리셋) |
| `Task_CAN_Tx` | osPriorityHigh | 256 | `0x100` 100ms 송신 (state/alive/EAR), 5회마다 `0x200` Heartbeat 송신 |
| `Task_UART_Rx` | osPriorityNormal | 256 | (파싱은 UART 콜백에서 수행 — 확장용 예약 태스크) |
| `Task_Alert` | osPriorityNormal | 128 | 큐 `q_dms_state` 수신 대기 → LED 표시 (0=꺼짐 / 1=깜빡 / 2=점등, 단절 시 깜빡) |

```
데이터 흐름
UART 콜백(ISR) ── 5바이트 프레임 파싱 + 체크섬 검증
   ├─ volatile 전역 갱신 (driver_state / curr_ear / curr_seq)  → Task_CAN_Tx가 주기 참조
   └─ osMessageQueuePut(q_dms_state, (state<<8)|ear, timeout=0) → Task_Alert 즉시 깨움
                                                       └ ISR에서 블로킹 금지 (timeout=0 필수)
```

설계 포인트:
- **DTC 송출이 Watchdog 태스크에 있는 이유** — Failsafe의 일부이므로 최상위 우선순위에서 실행. CAN_Tx가 밀려도 DTC만은 보장
- **큐 + volatile 혼용** — Alert은 이벤트 대기(큐), CAN_Tx는 주기 스냅샷(volatile)이 각각 더 단순
- 판정 기준은 베어메탈과 동일(500ms)하되 감시 해상도만 100ms로 정밀화

---

## CAN 메시지

### 구현 (실측 검증 완료)

| CAN ID | 메시지 명 | 방향 | 주기 | 설명 |
|---|---|---|---|---|
| `0x100` | `DMS_State` | 송신 | 100ms | [state, rpi_alive, EAR×100] — 실측 주기 99.2~99.4ms |
| `0x200` | `DMS_ECU_Heartbeat` | 송신 | 500ms | STM32 생존 카운터 (롤오버), 0x100과 정확히 5:1 비율 |
| `0x7DF` | `DMS_DTC` | 송신 | 이벤트 | Heartbeat 단절 시 [FF 01 02 01 …] 1회 송출, 복구 후 재단절 시 재송출 |
| `0x101` | `DMS_ACK` | 수신 | — | 네비 노드 ACK (수신 콜백 처리) |
| `0x102` | `DMS_Driver_Response` | 수신 | — | 수신 콜백 준비 완료 (cangaroo 주입으로 콜백 진입 검증) — 알림 완화 로직은 예정 |

### 예정 (송신)

| CAN ID | 메시지 명 | 주기 | 설명 |
|---|---|---|---|
| `0x110` | `DMS_SystemStatus` | 1000ms | AI 노드 연결·카메라·Failsafe 상태 — 감지 결과와 시스템 헬스 분리 |
| `0x120` | `DMS_Session` | 이벤트 | 주행 세션 시작·종료 송출 |

> `0x7DF`: UDS(ISO 14229) 표준 진단 요청 ID 차용 → 실차 진단 장비 호환.

---

## UART 프레임 (RPi5 → STM32)

```
[0xAA | State | EAR×100 | Seq | Checksum]   5바이트 고정, 100ms 주기, 115200 8N1

Checksum = (0xAA + State + EAR + Seq) & 0xFF   ← 가산 체크섬
```

콜백 내 2-상태 머신(SYNC 대기 → 4바이트 수집)으로 파싱하고,
체크섬 불일치 프레임은 폐기한다.

---

## 핀맵

| 기능 | 핀 | 설정 | 연결 대상 |
|---|---|---|---|
| CAN1_RX / TX | PB8 / PB9 | 500kbps | SN65HVD230 트랜시버 |
| UART4_TX / RX | PA0 / PA1 | 115200/8N1, 인터럽트 | RPi5 AI 노드 (TX↔RX 크로스) |
| LED2 | PB14 | GPIO_Output | 졸음 상태 표시 |
| TIM2 | — | 500ms 인터럽트 | **베어메탈 전용** — FreeRTOS는 osDelay로 대체 |

> ⚠️ B-L475E-IOT01A2는 "Initialize all peripherals → Yes"로 생성 시 온보드 주변장치가
> PA0/PA1·PB8/PB9를 선점한다. **Clear Pinouts 후 필요한 핀만 직접 설정**할 것 (DMS_init이 그 결과물).

---

## CubeMX 설정 (DMS_FreeRTOS)

```
CAN1:     Prescaler=10, BS1=13TQ, BS2=2TQ → 500 kbps @ 80MHz
          NVIC: CAN1 RX0 interrupt ✓        ← 누락 시 수신 콜백 미동작 (아래 트러블슈팅)
UART4:    115200/8N1, NVIC: UART4 global interrupt ✓
GPIO:     PB14 Output
FREERTOS: CMSIS_V2, TOTAL_HEAP_SIZE=8192 (4-Task 스택 합산 대응)
SYS:      Timebase Source = TIM6            ← FreeRTOS가 SysTick 점유하므로 HAL용 분리
Clock:    MSI → PLL → SYSCLK 80MHz
```

USE_NEWLIB_REENTRANT 경고는 태스크에서 newlib(printf/malloc)을 쓰지 않으므로 무시 가능.

---

## 🔥 트러블슈팅 — CAN 수신 콜백 미동작 (NVIC RX0)

```
증상: HAL_CAN_ActivateNotification(CAN_IT_RX_FIFO0_MSG_PENDING) 호출했는데
      HAL_CAN_RxFifo0MsgPendingCallback이 전혀 불리지 않음

원인: CubeMX → CAN1 → NVIC Settings → "CAN1 RX0 interrupt" 미체크
      → 벡터테이블에 ISR이 연결되지 않아 HAL 알림 활성화가 무의미

해결: NVIC RX0 체크 → 코드 재생성 → 즉시 정상 동작

교훈: "콜백이 안 불리면 NVIC부터 확인"
      HAL 알림 활성화(소프트웨어)와 NVIC 인터럽트 허용(하드웨어)은 별개 계층이다.
참고: RX0/RX1은 bxCAN의 FIFO 2개에 대응 (FilterFIFOAssignment로 분배) — 본 프로젝트는 FIFO0만 사용
```

---

## 검증 결과 (candump / cangaroo 실측)

```
✅ 0x100 주기 99.2~99.4ms / 0x200 정확히 5:1 비율 유지 (흔들림 없음)
✅ 상태 전이 00→01→02→00 + EAR 값(byte2) 실시간 전파
✅ AI 노드 Ctrl+C → ~0.6초 내 0x7DF 송출 → data[1]=00 전환
✅ AI 재시작 → data[1]=01 복귀 → 재단절 시 0x7DF 재송출 (dtc_sent 리셋 동작)
✅ cangaroo로 0x102 주입 → 수신 콜백 진입 확인
```

---

## 빌드 및 플래시

```
1. STM32CubeIDE → stm32/DMS_FreeRTOS (또는 DMS_baremetal) import
2. .ioc 열기 → Generate Code (Drivers/ 재생성)
3. Project → Build → Run → Flash (ST-Link, 보드 내장)
4. 디버그 모드 진입 시 Resume(F8) 후 동작 시작
```

> 저장소에는 `Core/ · Middlewares/ · .ioc · .project · .cproject · *.ld`만 포함.
> `Drivers/`(HAL)와 `Debug/`(빌드 산출물)는 Generate/Build로 재생성된다.

---

## 디렉토리 구조

```
stm32/
├── DMS_init/                   # 공통 베이스 (핀맵·클럭만, 온보드 주변장치 비활성화)
├── DMS_baremetal/              # 베어메탈 구현 (검증 완료 보존)
│   └── Core/Src/main.c         #   while 루프 + TIM2 콜백 + UART/CAN 콜백
└── DMS_FreeRTOS/               # FreeRTOS 구현 (최종 채택)
    ├── Core/
    │   ├── Inc/                #   FreeRTOSConfig.h, can.h, usart.h, gpio.h ...
    │   └── Src/
    │       ├── freertos.c      #   ★ 4-Task 본문 + UART/CAN 수신 콜백 + 큐
    │       ├── main.c          #   초기화 (Receive_IT, CAN 필터/Start/Notification)
    │       └── stm32l4xx_hal_timebase_tim.c   # TIM6 HAL timebase
    ├── Middlewares/Third_Party/FreeRTOS/      # FreeRTOS 커널 (heap_4)
    └── DMS_FreeRTOS.ioc
```

---

## 개발 환경

| 항목 | 값 |
|---|---|
| MCU | STM32L475VGT6 (B-L475E-IOT01A2, Cortex-M4 80MHz) |
| RTOS | FreeRTOS (CMSIS-RTOS v2), heap_4, TOTAL_HEAP_SIZE 8192 |
| IDE | STM32CubeIDE |
| CAN 트랜시버 | SN65HVD230 (3.3V) |
| 검증 도구 | candump (SocketCAN) · cangaroo (CANable Pro) |
