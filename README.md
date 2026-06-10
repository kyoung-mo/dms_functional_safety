# 대형 트럭 졸음운전 감지 · 중앙 관제 플랫폼

> RPi5(Hailo-8 NPU) + STM32(FreeRTOS) + CAN Bus + 중앙 관제 서버  
> 상용차 운전자 피로도 실시간 감지 · 기능안전 제어 · 통합 모니터링 시스템  
> Intel AI SW Academy 9기 3차 프로젝트 (2026.05.31. ~ 2026.06.15.)

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-FreeRTOS-A8B9CC?logo=c&logoColor=black)
![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi%205-×2-A22846?logo=raspberrypi&logoColor=white)
![Hailo-8](https://img.shields.io/badge/Hailo--8-NPU-00B5AD)
![STM32](https://img.shields.io/badge/STM32-L475-03234B?logo=stmicroelectronics&logoColor=white)
![FreeRTOS](https://img.shields.io/badge/FreeRTOS-Real--Time-8CC84B)

![HailoRT](https://img.shields.io/badge/HailoRT-4.23.0-00B5AD)
![Dataflow Compiler](https://img.shields.io/badge/Hailo%20DFC-3.33.1-00B5AD)
![Model Zoo](https://img.shields.io/badge/Hailo%20Model%20Zoo-2.18.0-00B5AD)
![YOLOv8-face](https://img.shields.io/badge/YOLOv8--face-detection-512BD4)
![face_landmarks_lite](https://img.shields.io/badge/face__landmarks__lite-468pts-512BD4)
![Flask](https://img.shields.io/badge/Flask-SocketIO-000000?logo=flask&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Realtime%20DB-FFCA28?logo=firebase&logoColor=black)
![Kakao Maps](https://img.shields.io/badge/Kakao%20Maps-JS%20SDK-FFCD00)
![CAN](https://img.shields.io/badge/CAN%20Bus-500kbps-FF6F00)
![Vector CANdb++](https://img.shields.io/badge/Vector-CANdb%2B%2B-E2001A)
![SQLite](https://img.shields.io/badge/SQLite-Local%20DB-003B57?logo=sqlite&logoColor=white)

---

## 💡 Motivation

대형 트럭·버스 등 상용차의 졸음운전 사고는 일반 승용차 대비 사망 사고 비율이 현저히 높다. 장거리 운행, 야간 운행이 잦은 상용차 특성상 운전자 피로 누적은 구조적인 안전 문제다.

기존 단일 장치 기반 졸음 감지 솔루션은 두 가지 핵심 한계를 가진다.

- **단일 장애점(SPOF)** — 감지 장치 자체가 다운되면 경고 출력도 함께 멈춘다
- **데이터 고립** — 차량별 이벤트가 분산되어 Fleet 전체의 위험 패턴을 통합 분석할 수 없다

본 프로젝트는 이 두 문제를 구조 설계로 해결한다.

👉 **AI 추론(비결정적) 노드와 안전 제어(결정적) 노드를 물리적으로 분리**하여, AI가 다운되어도 안전 기능은 독립 동작한다. 차량 단 엣지 처리 결과는 CAN을 통해 관제 노드로 전달되고, 관제 서버가 Fleet 전체 이벤트를 수집·분석한다.

> "단순히 감지하는 시스템이 아니라, 감지 시스템 자체가 고장 나도 안전한 구조"

---

## 📌 Key Features

- **Edge-AI 실시간 추론** — Hailo-8 NPU, YOLOv8-face + face_landmarks_lite 듀얼 모델, 13.4 FPS (CPU 대비 2.96배)
- **기능안전 (Fail-safe)** — AI·안전 노드 물리 분리, Heartbeat 감시, FreeRTOS 우선순위 스케줄링, DTC 자동 송출
- **차량 도메인 통신** — CAN Bus 500kbps, DBC 기반 메시지 정의, SN65HVD230 트랜시버
- **Fleet 중앙 관제** — 다수 차량 졸음 이벤트 실시간 수집 · GPS 위치 기록 · 통합 대시보드

---

## 🏗️ Architecture

<!-- 시스템 아키텍처 이미지 -->

| 노드 | 보드 | 역할 | 설계 원칙 |
|---|---|---|---|
| RPi5 졸음 인식 노드 | Raspberry Pi 5 + Hailo-8 NPU | AI 추론 — YOLOv8-face / face_landmarks_lite / PERCLOS 판정 / UART 송신 | AI는 추론만. 안전 판단·경고 출력은 STM32가 전담 |
| STM32 안전 제어 노드 | B-L475E-IOT01A2 (STM32L476) | FreeRTOS — UART Rx / CAN Tx / Heartbeat 감시 / DTC 송출 | AI 노드 다운과 무관하게 독립 동작. 결정적 실시간성 보장 |
| RPi5 네비 노드 | Raspberry Pi 5 + MCP2515 | 관제 연동 — CAN 수신 / Kakao Maps / Firebase GPS / SQLite 이벤트 로그 | 엣지 처리 결과를 관제 서버로 릴레이. 위치 기반 분석 |
| 중앙 관제 서버 | Flask + Firebase + SQLite | Fleet 대시보드 — 다수 차량 통합 모니터링 / 졸음 이벤트 · 위험 구간 분석 | 차량별 엣지 처리 결과 수집·집계. 패턴 분석 |

---

## 🔄 System Flow

<img width="1089" height="893" alt="image" src="https://github.com/user-attachments/assets/f562aa69-d833-4da4-83cd-2e3356f0bf6a" />

---

## 📡 CAN Protocol

통신 속도: **500 kbps** / DBC 파일 기반 메시지 정의 (Vector CANdb++) / SN65HVD230 트랜시버

| CAN ID | 내용 | 송신 | 수신 | 주기 |
|---|---|---|---|---|
| **0x100** | 졸음 상태 (State: 0=정상 / 1=주의 / 2=위험) + EAR 값 | STM32 | RPi5 네비 | 100ms |
| **0x101** | 수신 ACK | RPi5 네비 | STM32 | 수신 시마다 |
| **0x7DF** | DTC 송출 — Heartbeat 단절 (AI 노드 다운 감지) | STM32 | CAN Bus | 이벤트 |

> **0x7DF 선택 이유**: UDS(ISO 14229) 표준 진단 요청 ID를 차용. 실차 진단 장비와 호환되는 고장 코드 포맷으로 설계하여 확장성 확보.

---

## ⚙️ 핵심 기능

**Edge-AI 추론 파이프라인**
- Hailo-8 NPU에서 YOLOv8-face + face_landmarks_lite 듀얼 모델 동시 실행 (VDevice 공유, 번갈아 activate)
- ONNX → HAR → HEF 변환 파이프라인 직접 구축 (Hailo DFC 3.33.1, Model Zoo 2.18.0)
- PERCLOS: 동적 임계값 (상위 10% EAR × 0.75, 히스테리시스 적용), 1.5초 지속 시 졸음 판정 (3단계: 0/1/2)
- NPU 추론 속도: CPU 대비 **2.96배 향상**, Headless 모드 **13.4 FPS**
- 보정 데이터: WIDER_val 얼굴 크롭 300장 → Haar Cascade 대비 오탐 30% 감소

**FreeRTOS 기반 기능안전**
- 4개 태스크 우선순위 스케줄링 — AI 연산 부하가 급증해도 안전 기능(CAN 송신 · DTC 송출)은 지연 없이 동작
- Heartbeat 감시: AI 노드 UART 프레임 500ms 미수신 → Failsafe 진입 → DTC CAN 0x7DF 송출
- UART 바이너리 프레임: 고정 5바이트 [0xAA, State, EAR×100, Seq, Checksum], 100ms 주기

**Fleet 중앙 관제 연동**
- 졸음 이벤트 발생 GPS 좌표를 SQLite에 기록 → 카카오맵에 실시간 핀 표시, 5초 쿨다운 기반 세션 집계
- 삼성폰 PWA geolocation → Firebase Realtime DB → RPi5 네비 폴링 (HTTPS Mixed Content 우회)
- 중앙 관제 서버: 다수 차량 이벤트 수집 · 위험 구간 통계 · 운전자별 피로도 이력 관리

**확장 (여유 시):** MobileFaceNet 기반 운전자 인식 + 개인 캘리브레이션, MAR(하품) / Head Pose 지표, UDS 진단 서브셋

---

## 🛠️ STM32 안전 제어 노드 상세

### FreeRTOS 태스크 구조

| 태스크 | 우선순위 | 주기 | 역할 |
|---|---|---|---|
| `Task_Watchdog` | 최상위 | 100ms | Heartbeat 감시, 500ms 단절 시 Failsafe 진입 + DTC CAN 송출 |
| `Task_CAN_Tx` | 높음 | 100ms | 졸음 상태 CAN 0x100 송신 (DBC 인코딩) |
| `Task_UART_Rx` | 보통 | 인터럽트 기반 | RPi5 바이너리 프레임 수신 · 상태머신 파싱 · Queue 전달 |
| `Task_Alert` | 보통 | 100ms | LED 상태 표시 (State 0=꺼짐 / 1=500ms 깜빡 / 2=점등) |

### 핀맵

| 기능 | 핀 | CubeMX 설정 | 연결 대상 |
|---|---|---|---|
| CAN1_RX/TX | PB8/PB9 | CAN1 500kbps | SN65HVD230 트랜시버 |
| UART4_TX/RX | PA0/PA1 | 115200/8N1 인터럽트 | RPi5 졸음 인식 노드 (크로스 연결) |
| TIM2 | — | 500ms 인터럽트 | Heartbeat 타이머 |
| LED2 | PB14 | GPIO_Output | 졸음 상태 표시 |

> ⚠️ B-L475E-IOT01A2 기본 초기화 시 온보드 UART4(PA0/PA1), SPI1이 핀을 선점함.  
> 반드시 온보드 주변장치를 비활성화한 상태(`base.ioc`)에서 프로젝트를 시작할 것.

### CubeMX 설정

```
CAN1:  Prescaler=10, BS1=13TQ, BS2=2TQ  → 500 kbps (SYSCLK 80MHz)
UART4: 115200/8N1, HAL_UART_Receive_IT (인터럽트 수신)
TIM2:  Prescaler=8000-1, Period=5000-1  → 500ms @ 80MHz
Clock: HSI 16MHz → PLL → SYSCLK 80MHz
FreeRTOS: CMSIS-RTOS v2, configTICK_RATE_HZ=1000
```

### 주요 파라미터

```c
#define UART_SYNC_BYTE          0xAA
#define UART_FRAME_SIZE         5       // [SYNC, State, EAR×100, Seq, Checksum]
#define HEARTBEAT_TIMEOUT_MS    500     // AI 노드 단절 판정 임계값
#define CAN_TX_PERIOD_MS        100     // CAN 상태 메시지 송신 주기
#define EAR_SCALE               100     // EAR 소수점 → 정수 변환 (0.35 → 35)
#define DTC_ID                  0x7DF   // UDS 표준 진단 요청 ID 차용
```

---

## 🔬 NPU 벤치마크

| 항목 | 결과 |
|---|---|
| 추론 FPS (Headless 모드) | **13.4 FPS** |
| NPU vs CPU 속도 비율 | **2.96배 향상** |
| 주요 병목 구간 | 카메라 `capture_array()` 블로킹 ~40ms, Python 후처리 ~9ms |
| 모델 변환 파이프라인 | ONNX → HAR → HEF (DFC 3.33.1, Model Zoo 2.18.0) |
| 캘리브레이션 데이터 | WIDER_val 얼굴 크롭 300장 (Haar 대비 오탐 30% 감소) |
| face_landmarks_lite 출력 | conv22: 1404값 (468pts × 3, 0–192px 공간) / conv25: confidence (sigmoid 내장) |

---

## 🚀 빌드 및 실행

**RPi5 졸음 인식 노드**

```bash
# HailoRT 가상환경 활성화 (Python 3.13.5 + HailoRT 4.23.0)
source ~/dms_env/bin/activate

# 추론 메인 루프 실행
cd rpi5_ai && python inference/perclos_uart.py
```

**RPi5 네비 노드**

```bash
# MCP2515 CAN 인터페이스 활성화
# /boot/firmware/config.txt 에 아래 추가 후 재부팅:
# dtoverlay=mcp2515-can0,oscillator=8000000,interrupt=25
# dtparam=spi=on

sudo ip link set can0 up type can bitrate 500000

# Flask + SocketIO 서버 실행
cd rpi5_navi && PYTHONPATH=. python flask_server/app.py
```

**STM32 안전 제어 노드**

```
STM32CubeIDE: 프로젝트 열기 → Build (Release) → Flash (ST-Link/V2)
```

---

## 📁 프로젝트 구조

```
dms_functional_safety/
├── rpi5_ai/                      # 졸음 인식 노드 (Python)
│   ├── models/                   # HEF 모델 (YOLOv8-face, face_landmarks_lite)
│   ├── inference/
│   │   └── perclos_uart.py       # 추론 메인 루프 (NPU 파이프라인 + UART 송신)
│   └── comm/                     # UART 바이너리 프레임 정의
├── rpi5_navi/                    # 네비 · 관제 노드 (Python/Flask)
│   ├── flask_server/
│   │   ├── app.py                # Flask + SocketIO + CAN 수신 스레드
│   │   └── templates/            # 카카오맵 HTML (네비 화면 + 관제 대시보드)
│   ├── firebase_poll.py          # Firebase GPS 폴링
│   └── db.py                     # SQLite 이벤트 로그
├── stm32/                        # 안전 제어 노드 (C, FreeRTOS)
│   ├── Core/Src/
│   │   ├── freertos.c            # 4-Task 정의 (Watchdog / CAN Tx / UART Rx / Alert)
│   │   ├── can.c                 # CAN 송신 (DBC 기반 인코딩)
│   │   └── uart_parser.c         # 바이너리 프레임 상태머신 파싱
│   └── dbc/                      # DBC 메시지 정의 (Vector CANdb++)
├── pwa/                          # GPS 송신 PWA (삼성폰, HTML + JS)
│   └── index.html                # geolocation → Firebase 업로드
├── docs/                         # 설계 문서 · 인터페이스 정의서
└── README.md
```

---

## 🛠️ 개발 환경

- **졸음 인식 노드:** Raspberry Pi 5, Python 3.13.5, HailoRT 4.23.0
- **모델 변환:** WSL Ubuntu 24.04, Python 3.10, Hailo DFC 3.33.1, Model Zoo 2.18.0
- **안전 제어 노드:** STM32L476 (B-L475E-IOT01A2), FreeRTOS, STM32CubeIDE
- **네비 노드:** Raspberry Pi 5, Python 3.13.5, Flask + SocketIO, SQLite, MCP2515 (SPI0, 8MHz)
- **GPS PWA:** 삼성 갤럭시, Chrome, Firebase Realtime DB

---

## 🎯 산출물

- 실행 가능한 3-노드 프로토타입 (RPi5 AI 추론 + STM32 FreeRTOS 안전 제어 + 네비/관제 연동)
- DBC 파일 및 UART 인터페이스 정의서
- NPU vs CPU 벤치마크 결과 (2.96배 향상, 13.4 FPS, Headless)
- 실시간 카카오맵 네비게이션 + Fleet 중앙 관제 대시보드
- 기술 블로그 ([Velog](https://velog.io/@mommers))
