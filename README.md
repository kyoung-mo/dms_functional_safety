# Edge-AI 기반 대형 트럭 졸음운전 감지 · 주행 분석 플랫폼

> RPi5(Hailo-8 NPU) + STM32(FreeRTOS) + CAN Bus + Firebase 기반  
> 상용차 운전자 피로도 실시간 감지 · 기능안전 제어 · 주행 이벤트 분석 시스템  
> Intel AI SW Academy 9기 3차 프로젝트 (2026.06)

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

대형 트럭·버스 등 상용차의 졸음운전 사고는 일반 승용차 대비 사망 사고 비율이 현저히 높다.
장거리·야간 운행이 잦은 상용차 특성상 운전자 피로 누적은 구조적인 안전 문제다.

기존 단일 장치 기반 졸음 감지 솔루션은 **단일 장애점(SPOF)** 문제를 갖는다.
감지 장치 자체가 다운되면 경고 출력도 함께 멈추기 때문이다.

본 프로젝트는 이 문제를 구조 설계로 해결한다.

👉 **AI 추론 노드(비결정적)와 안전 제어 노드(결정적)를 물리적으로 분리**하여,
AI가 다운돼도 STM32는 독립적으로 Heartbeat를 감시하고 CAN DTC를 송출한다.
졸음 이벤트와 GPS 위치는 Firebase에 실시간 저장되고, 관제 센터 웹 대시보드에서 다수 운전자의 주행 이력을 통합 조회할 수 있다.

> "단순히 감지하는 시스템이 아니라, 감지 시스템 자체가 고장 나도 안전한 구조"

---

## 📌 Key Features

- **Edge-AI 실시간 추론** — Hailo-8 NPU (HEF+HEF), CPU 대비 **4.3배** 향상, 59.9 FPS (AI 파이프라인 기준)
- **기능안전 (Fail-safe)** — AI·안전 노드 물리 분리, Heartbeat 감시, FreeRTOS 우선순위 스케줄링, DTC 자동 송출
- **차량 도메인 통신** — CAN Bus 500kbps, DBC 기반 메시지 정의, SN65HVD230 트랜시버
- **Firebase 관제 대시보드** — 운전자별 주행 세션·GPS 경로·졸음 이벤트 Firebase 저장, 웹 관제 센터 조회

---

## 🏗️ Architecture

<img width="1089" height="893" alt="image" src="https://github.com/user-attachments/assets/8c185ec4-411a-42d2-86a1-8812afad9142" />


| 노드 | 보드 | 역할 | 설계 원칙 |
|---|---|---|---|
| RPi5 졸음 인식 노드 | Raspberry Pi 5 + Hailo-8 NPU | AI 추론 — YOLOv8-face / face_landmarks_lite / PERCLOS 판정 / UART 송신 | AI는 추론만. 안전 판단·경고 출력은 STM32가 전담 |
| STM32 안전 제어 노드 | B-L475E-IOT01A2 (STM32L475) | FreeRTOS — UART Rx / CAN Tx / Heartbeat 감시 / DTC 송출 | AI 노드 다운과 무관하게 독립 동작. 결정적 실시간성 보장 |
| RPi5 네비 노드 | Raspberry Pi 5 + MCP2515 | 네비게이션 — CAN 수신 / Kakao Maps / Firebase GPS·이벤트 저장 / SQLite 로그 | 졸음 이벤트·GPS를 Firebase에 업로드 → 관제 센터 웹에서 통합 조회 |

---

## 📡 CAN 메시지 정의

통신 속도: **500 kbps** / DBC 파일 기반 (Vector CANdb++) / SN65HVD230 트랜시버

| CAN ID | 메시지 명 | 방향 | 주기 | 구분 | 설명 |
|---|---|---|---|---|---|
| `0x100` | `DMS_State` | STM32 → RPi5 네비 | 100ms | **구현** | 졸음 상태 (0=정상/1=주의/2=위험) + AI 생존 + EAR 값 |
| `0x101` | `DMS_ACK` | RPi5 네비 → STM32 | 수신 시마다 | **구현** | 수신 확인 ACK (핑퐁 검증 완료) |
| `0x200` | `DMS_ECU_Heartbeat` | STM32 → RPi5 네비 | 500ms | **구현** | STM32 생존 카운터 (역방향 Heartbeat) |
| `0x7DF` | `DMS_DTC` | STM32 → CAN Bus | 이벤트 | **구현** | 고장 코드 (Heartbeat 단절 감지 시, UDS ID 차용) |
| `0x110` | `DMS_SystemStatus` | STM32 → RPi5 네비 | 1000ms | 예정 | 시스템 헬스 (AI 노드 연결·카메라·Failsafe) |
| `0x120` | `DMS_Session` | STM32 → CAN Bus | 이벤트 | 예정 | 주행 세션 시작·종료 |
| `0x102` | `DMS_Driver_Response` | RPi5 네비 → STM32 | 이벤트 | 예정 | 운전자 경고 확인 — STM32 수신 콜백은 준비 완료, 네비 송신·알림 완화 로직 예정 |

> `0x7DF`: UDS(ISO 14229) 표준 진단 요청 ID 차용 → 실차 진단 장비 호환.

---

## ⚙️ 핵심 기능

**Edge-AI 추론 파이프라인**
- Hailo-8 NPU에서 YOLOv8-face + face_landmarks_lite 듀얼 모델 동시 실행 (VDevice 공유)
- ONNX → HAR → HEF 변환 파이프라인 직접 구축 (Hailo DFC 3.33.1, Model Zoo 2.18.0)
- PERCLOS: 동적 임계값 (상위 10% EAR × 0.75), 1.5초 지속 시 졸음 판정 (3단계)
- **졸음 모드 임계값 동결 (is_drowsy)**: 졸음 중 EAR 누적 중단 + 진입 시점 임계값 동결 → 캘리브레이션 오염 방지, 10프레임 연속 눈뜸 확인 후 복귀
- EAR 고정 임계값 0.223 (1000장 데이터셋 기반 최적 임계값 탐색, 졸음 모드 fallback으로 사용)

**FreeRTOS 기반 기능안전 (구현·검증 완료)**
- 4-Task 우선순위 스케줄링 — AI 연산 부하와 무관하게 안전 기능 지연 없이 동작
- Heartbeat 감시: AI 노드 UART 프레임 500ms 미수신 → Failsafe → DTC `0x7DF` 송출
- **단절 → DTC 반응 시간: 베어메탈 ~1.5초 → FreeRTOS ~0.6초 (2.5배 개선, candump 실측)**
- UART 바이너리 프레임: 고정 5바이트 [0xAA, State, EAR×100, Seq, Checksum], 100ms 주기

**Firebase 기반 관제 대시보드**
- 졸음 이벤트·GPS 경로를 Firebase Realtime DB에 저장 (driver_id / session_id 계층 구조)
- 삼성폰 PWA geolocation → Firebase `/gps/{driver_id}` → RPi5 네비 2초 폴링
- 관제 센터 웹: 다수 운전자 주행 세션 이력 / GPS 경로 / 졸음 이벤트 위치 통합 조회

---

## 🔬 NPU 벤치마크

> 측정 조건: 1000장 정적 이미지 (open=500, close=500), EAR 임계값 0.223  
> **카메라 캡처 시간·UART 송신 미포함** (AI 추론 파이프라인 기준)

### FPS / Latency

| 환경 | FPS | 평균 Latency | YOLO | LM |
|---|---|---|---|---|
| **HEF+HEF** | **59.9** | **16.6ms** | 12.0ms | 4.6ms |
| HEF+ONNX | 49.0 | 20.3ms | 16.2ms | 4.1ms |
| ONNX+HEF | 21.0 | 47.5ms | 38.2ms | 9.3ms |
| ONNX+ONNX (Hailo) | 14.1 | 70.9ms | 65.4ms | 5.5ms |
| CPU (ONNX+ONNX) | 14.1 | 70.6ms | 65.2ms | 5.4ms |

### 정확도 (EAR 임계값 0.223)

| 환경 | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| **HEF+HEF** | 63.1% | **98.8%** | 77.0% | 70.5% |
| HEF+ONNX | 62.4% | 99.4% | 76.6% | 69.7% |
| ONNX+HEF | 62.7% | 96.8% | 76.1% | 69.6% |
| ONNX+ONNX (Hailo) | 62.4% | 99.0% | 76.6% | 69.7% |
| CPU (ONNX+ONNX) | 62.4% | 99.0% | 76.6% | 69.7% |

### 핵심 결론

```
HEF+HEF 기준 CPU 대비 추론 속도 4.3배 향상 (14.1 → 59.9 FPS)
정확도(Recall 98.8%)는 CPU 환경과 동등 수준 유지
실시간 DMS 요구사항 15 FPS를 NPU 환경에서 충분히 달성
```

> **실제 배포 FPS (~13 FPS)** 와 벤치마크 FPS(59.9)의 차이는 카메라 캡처 블로킹(~40ms)이 병목.  
> NPU 추론 자체 속도는 16.6ms 이며, 카메라 I/O를 제외하면 60 FPS 달성 가능.

### 벤치마크 한계

```
- 카메라 캡처 시간 미포함 (정적 이미지 기준)
- PERCLOS 누적 계산 미포함
- 단일 인물 데이터셋 (일반화 제한)
- 밝은 환경 / 정면 얼굴만 포함
```

---

## 📁 프로젝트 구조

```
dms_functional_safety/
├── conversion/            # ONNX → HEF 모델 변환 파이프라인
├── dataset/               # 캘리브레이션·벤치마크 이미지
│   └── infer_data/        # 라벨 이미지 1000장 (*_open.jpg / *_close.jpg)
├── dbc/                   # CAN 메시지 정의 (DBC, Vector CANdb++)
├── docs/                  # 설계 문서 · 인터페이스 정의서
├── rpi5_ai/               # 졸음 인식 노드 (Python, HailoRT)
│   ├── models/            # HEF 모델 (YOLOv8-face, face_landmarks_lite)
│   └── inference/         # 추론 루프 (perclos_uart.py), 벤치마크 스크립트
├── rpi5_navi/             # 네비 노드 (Python/Flask)
│   ├── flask_server/      # Flask + SocketIO + CAN 수신/ACK
│   │   └── templates/     # 카카오맵 네비 + 관제 센터 웹
│   ├── gps/               # Firebase GPS·이벤트 저장
│   └── db/                # SQLite 로컬 백업
└── stm32/                 # 안전 제어 노드 (C)
    ├── DMS_init/          #   공통 베이스 (핀맵·클럭)
    ├── DMS_baremetal/     #   베어메탈 구현 (검증 완료 보존)
    └── DMS_FreeRTOS/      #   FreeRTOS 4-Task 구현 (최종 채택)
```

---

## 🚀 빠른 시작

**RPi5 졸음 인식 노드**
```bash
source ~/dms_env/bin/activate
cd rpi5_ai && python inference/perclos_uart.py
```

**RPi5 네비 노드**
```bash
sudo ip link set can0 up type can bitrate 500000
cd rpi5_navi && PYTHONPATH=. python flask_server/app.py
```

**STM32 안전 제어 노드**
```
STM32CubeIDE: DMS_FreeRTOS import → Build → Flash (ST-Link)
```

---

## 🛠️ 개발 환경

| 항목 | 내용 |
|---|---|
| 졸음 인식 노드 | Raspberry Pi 5, Python 3.13.5, HailoRT 4.23.0 |
| 모델 변환 | WSL Ubuntu 24.04, Python 3.10, Hailo DFC 3.33.1 |
| 안전 제어 노드 | STM32L475 (B-L475E-IOT01A2), FreeRTOS (CMSIS-V2), STM32CubeIDE |
| 네비 노드 | Raspberry Pi 5, Python 3.13.5, Flask + SocketIO, MCP2515 |
| GPS / 관제 | 삼성 갤럭시 PWA, Chrome, Firebase Realtime DB |

---

## 🎯 산출물

- 실행 가능한 3-노드 프로토타입 (RPi5 AI 추론 + STM32 FreeRTOS 안전 제어 + 네비 연동)
- 베어메탈·FreeRTOS 이중 구현 및 DTC 반응 속도 실측 비교 (1.5초 → 0.6초)
- DBC 파일 및 UART 인터페이스 정의서 (구현 4개 + 예정 3개 메시지)
- 5가지 환경 NPU 벤치마크 결과 (HEF+HEF CPU 대비 4.3배 향상)
- 실시간 카카오맵 네비게이션 + Firebase 기반 관제 센터 웹 대시보드
- 기술 블로그 ([Velog](https://velog.io/@mommers))
