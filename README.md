# 기능안전 기반 스마트 DMS (진행 중)

> RPi5 + Hailo-8 NPU + STM32(FreeRTOS) + CAN 기반 졸음 감지 · 실시간 안전 제어 분리형 운전자 모니터링 시스템  
> Intel AI SW Academy 9기 3차 프로젝트 (2026.06)

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.13-3776AB?logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-FreeRTOS-A8B9CC?logo=c&logoColor=black)
![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi%205-Host-A22846?logo=raspberrypi&logoColor=white)
![Hailo-8](https://img.shields.io/badge/Hailo--8-NPU-00B5AD)
![STM32](https://img.shields.io/badge/STM32-L475%20%7C%20F103-03234B?logo=stmicroelectronics&logoColor=white)
![FreeRTOS](https://img.shields.io/badge/FreeRTOS-RTOS-2EA44F)

![HailoRT](https://img.shields.io/badge/HailoRT-4.23.0-00B5AD)
![Dataflow Compiler](https://img.shields.io/badge/Hailo%20DFC-3.33.1-00B5AD)
![Model Zoo](https://img.shields.io/badge/Hailo%20Model%20Zoo-2.18.0-00B5AD)
![YOLOv8-face](https://img.shields.io/badge/YOLOv8--face-detection-512BD4)
![face_landmarks_lite](https://img.shields.io/badge/face__landmarks__lite-468pts-512BD4)
![CAN](https://img.shields.io/badge/Protocol-CAN%20%7C%20UART-FF6F00)
![Vector CANdb++](https://img.shields.io/badge/Vector-CANdb%2B%2B-E2001A)

> **[Intel Edge AI 3차 프로젝트]** AI 추론과 실시간 안전 제어를 **물리적으로 분리**한 기능안전 기반 운전자 모니터링 시스템(DMS)

졸음 감지 AI(비결정적)와 실시간 안전 제어(결정적)를 **서로 다른 하드웨어 노드로 물리적으로 분리**하여, AI의 불안정성(지연·다운)이 차량 안전 기능을 침해하지 못하게 설계한 DMS입니다. 감지 결과는 차량 네트워크(CAN)로 전달되며, 노드 간 통신이 끊기면 즉시 고장 코드(DTC)를 송출합니다.

---

## 핵심 차별점

졸음 감지 프로젝트에 대해서는 공개된 예제가 많습니다. 본 프로젝트의 차별점은 **"무엇을 감지하느냐"가 아니라 "어떤 구조로 설계했느냐"** 에 있습니다.

- **물리적 결함 격리** — AI 추론(RPi5)과 안전 제어(STM32)를 별개 하드웨어로 분리. 단일 장애점 제거.
- **Fail-safe 설계** — 노드 간 Heartbeat가 끊기면 "모니터링 불가" 상태를 침묵하지 않고 CAN으로 명확히 보고.
- **우선순위 기반 실시간성** — AI 연산 부하가 급증해도 안전 기능(CAN 송신·고장 감지)은 RTOS 우선순위로 지연 없이 동작.

---

## 시스템 구조

<img width="1211" height="903" alt="image" src="https://github.com/user-attachments/assets/e4ad2e9a-808c-4e3d-a0f0-a70f13c436e3" />

---

## 처리 파이프라인

```
카메라 → 얼굴 검출(YOLO) → 얼굴 크롭 → 랜드마크 468점 → EAR 연산 → 졸음 판정
                                                          │
                                              UART(상태 + Heartbeat)
                                                          ▼
        STM32: 상태 수신 → 경고 출력 + CAN 송신 / Heartbeat 단절 시 DTC 송출
```

---

## 기술 스택

| 구분 | 기술 |
| --- | --- |
| AI 추론 | RPi5 + Hailo-8 NPU, HailoRT |
| 모델 변환 | Hailo Dataflow Compiler 3.33.1, Model Zoo 2.18.0 |
| AI 모델 | YOLOv8-face (검출), face_landmarks_lite (랜드마크, 468점) |
| 실시간 제어 | STM32 + FreeRTOS (C) |
| 통신 | UART (노드 간), CAN (차량 네트워크) |
| 통신 정의 | Vector CANdb++ (DBC), cantools |

---

## 핵심 기능 (MVP)

| # | 기능 | 설명 |
| --- | --- | --- |
| 1 | AI 졸음 감지 (EAR) | 얼굴 검출 → 랜드마크 → EAR 연산으로 졸음 판정 |
| 2 | 이기종 통신 | 판정 결과를 UART 바이너리 프레임으로 STM32에 전송 |
| 3 | 실시간 경고 · CAN 송출 | 졸음 임계값 초과 시 경고 + CAN 상태 송신 |
| 4 | 기능안전 (Fail-safe) | Heartbeat 단절 감지 시 DTC 송출 + 우선순위 스케줄링 |

**확장 (여유 시):** 운전자 인식(MobileFaceNet) 기반 개인 캘리브레이션, MAR(하품)/Head Pose 지표, UDS 진단 서브셋

---

## 프로젝트 구조

```
dms_functional_safety/
├── rpi5/              # AI 추론 노드 (Python)
│   ├── models/        # HEF 모델
│   ├── inference/     # 검출 · 랜드마크 · EAR
│   └── comm/          # UART 송신 · Heartbeat
├── stm32/             # 실시간 제어 노드 (C, FreeRTOS)
│   ├── tasks/         # Watchdog · CAN Tx · UART Rx · 경고
│   └── can/           # DBC 기반 인코딩
├── dbc/               # CAN 메시지 정의 (DBC)
├── docs/              # 기획 · 설계 문서
└── README.md
```

> ※ 구조는 진행 중 변경될 수 있음.

---

## 일정

| 단계 | 기간 | 내용 |
| --- | --- | --- |
| 0. 인터페이스 | 5/31~6/2 | UART 구조체 + DBC + Heartbeat 규약 확정 |
| 1. AI 추론 | 6/3~6/6 | 모델 변환, EAR 연산, NPU 벤치마크 |
| 2. 펌웨어 골격 | 6/7~6/10 | FreeRTOS 태스크, UART 연동, MVP 완성 |
| 3. CAN/안전 | 6/11~6/13 | CAN Tx, Heartbeat 단절 감지, DTC |
| 4. 마무리 | 6/14~6/15 | 문서화, 시연, 블로그 |

---

## 산출물

- 실행 가능한 프로토타입 (RPi5 추론 + STM32 펌웨어 연동)
- DBC 파일 및 UART 인터페이스 정의서
- CPU vs NPU 벤치마크 결과
- 기술 블로그 ([Velog](https://velog.io/@mommers))

---

## 개발 환경

- **AI 노드:** RPi5, Python 3.13.5, HailoRT 4.23.0
- **모델 변환:** WSL Ubuntu 24.04, Python 3.10, Dataflow Compiler 3.33.1, Model Zoo 2.18.0
- **제어 노드:** STM32 (L475 우선 → F103 이식), FreeRTOS, STM32CubeIDE
