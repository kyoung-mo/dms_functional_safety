# 📄 docs — 설계 문서 및 인터페이스 정의

> 시스템 아키텍처, 인터페이스 규약, 개발 산출물 문서 디렉토리  
> 노드 간 독립 개발이 가능하도록 인터페이스를 동결(freeze)한 기준 문서 보관

---

## 🔧 Tech Stack

![Markdown](https://img.shields.io/badge/Markdown-문서-000000?logo=markdown&logoColor=white)
![Draw.io](https://img.shields.io/badge/Draw.io-아키텍처%20다이어그램-FF7A00)
![Vector CANdb++](https://img.shields.io/badge/Vector-CANdb%2B%2B-E2001A)
![CAN](https://img.shields.io/badge/CAN%20Bus-인터페이스%20정의-FF6F00)
![UART](https://img.shields.io/badge/UART-바이너리%20프레임%20정의-555555)

---

## 개요

DMS 시스템의 설계 문서, 인터페이스 정의, 알고리즘 상세, 벤치마크 결과 등
프로젝트 전반의 기술 문서를 보관하는 디렉토리.

개발 착수 전 UART 프레임 구조 · CAN 메시지 ID · Heartbeat 규약을 동결하여
AI 노드(rpi5)와 안전 제어 노드(stm32)가 독립적으로 개발 가능하도록 기준을 확정했다.

---

## 문서 목록

| 파일 | 내용 |
|---|---|
| `architecture.md` | 시스템 아키텍처 개요 (3-노드 구조, 설계 원칙) |
| `uart_interface.md` | UART 바이너리 프레임 정의 (RPi5 ↔ STM32) |
| `can_interface.md` | CAN 메시지 정의 요약 (DBC 연동, 구현/예정 구분) |
| `freertos_tasks.md` | FreeRTOS 4-Task 구조 및 우선순위 설계 |
| `perclos_algorithm.md` | PERCLOS 졸음 판정 알고리즘 상세 |
| `benchmark.md` | NPU vs CPU 5가지 환경 벤치마크 결과 |
| `schedule.md` | 개발 일정 및 마일스톤 |

---

## UART 인터페이스 정의 (동결 규약)

RPi5 AI 노드 → STM32 단방향 송신 (100ms 주기, Heartbeat 겸용)

### 프레임 구조 — 5 Bytes

| Byte | 필드 | 값 | 설명 |
|---|---|---|---|
| Byte 0 | SYNC | `0xAA` | 프레임 시작 동기 바이트 |
| Byte 1 | State | 0 / 1 / 2 | 졸음 상태 (0=정상, 1=주의, 2=위험) |
| Byte 2 | EAR_Scaled | 0–100 | EAR × 100 정수 변환 (0.35 → 35) |
| Byte 3 | SeqNum | 0–255 | 순서 번호 (롤오버) |
| Byte 4 | Checksum | XOR | Byte 1 XOR Byte 2 XOR Byte 3 |

### Heartbeat 규약

| 조건 | STM32 동작 |
|---|---|
| 정상 수신 | heartbeat_counter 리셋, Failsafe 해제 |
| **500ms 미수신** | Failsafe 진입 → DTC `0x7DF` CAN 송출 → LED 소등 |

---

## CAN 인터페이스 정의

통신 속도: **500 kbps** / Vector CANdb++ DBC 포맷

| CAN ID | 메시지 명 | 방향 | 주기 | 구분 | 설명 |
|---|---|---|---|---|---|
| `0x100` | `DMS_State` | STM32 → RPi5 네비 | 100ms | **구현** | 졸음 상태 + EAR 값 |
| `0x101` | `DMS_ACK` | RPi5 네비 → STM32 | 수신 시마다 | **구현** | 수신 확인 ACK |
| `0x7DF` | `DMS_DTC` | STM32 → CAN Bus | 이벤트 | **구현** | 고장 코드 (Heartbeat 단절) |
| `0x200` | `DMS_ECU_Heartbeat` | STM32 → RPi5 네비 | 500ms | 예정 | STM32 생존 확인 |
| `0x110` | `DMS_SystemStatus` | STM32 → RPi5 네비 | 1000ms | 예정 | 시스템 헬스 상태 |
| `0x120` | `DMS_Session` | STM32 → CAN Bus | 이벤트 | 예정 | 주행 세션 시작·종료 |
| `0x102` | `DMS_Driver_Response` | RPi5 네비 → STM32 | 이벤트 | 예정 | 운전자 경고 확인 여부 |

---

## 시스템 설계 원칙

| 원칙 | 내용 |
|---|---|
| **물리적 결함 격리** | AI 추론(RPi5)과 안전 제어(STM32)를 별개 하드웨어로 분리 |
| **Fail-safe 설계** | Heartbeat 단절 시 침묵하지 않고 DTC로 명시적 보고 |
| **우선순위 기반 실시간성** | AI 부하와 무관하게 RTOS 우선순위로 안전 기능 보장 |
| **표준 인터페이스** | DBC 기반 CAN, UDS 호환 DTC 포맷 사용 |
| **Firebase 통합 저장** | 졸음 이벤트·GPS 경로를 Firebase에 저장하여 관제 웹에서 통합 조회 |

---

## PERCLOS 알고리즘 요약

| 파라미터 | 값 | 설명 |
|---|---|---|
| 동적 임계값 | 상위 10% EAR × 0.75 | 운전 초기 히스토리 기반 개인 적응 |
| 보정 고정 임계값 | **0.223** | 1000장 데이터셋 기반 최적값 탐색 결과 |
| 졸음 판정 지속 | **1.5초** | ~20프레임 @ 13 FPS |
| 출력 상태 | 0 / 1 / 2 | 정상 / 주의 / 위험 |

---

## NPU 벤치마크 결과 요약

> 측정 조건: 1000장 정적 이미지, EAR 임계값 0.223, 카메라 I/O 제외

| 환경 | FPS | Latency | Recall | Accuracy |
|---|---|---|---|---|
| **HEF+HEF** | **59.9** | **16.6ms** | **98.8%** | 70.5% |
| HEF+ONNX | 49.0 | 20.3ms | 99.4% | 69.7% |
| ONNX+HEF | 21.0 | 47.5ms | 96.8% | 69.6% |
| ONNX+ONNX (Hailo) | 14.1 | 70.9ms | 99.0% | 69.7% |
| CPU (ONNX+ONNX) | 14.1 | 70.6ms | 99.0% | 69.7% |

**HEF+HEF 기준 CPU 대비 추론 속도 4.3배 향상** (14.1 → 59.9 FPS)

> 실제 배포 FPS(~13 FPS)는 카메라 캡처 블로킹(~40ms)이 병목. NPU 추론 자체는 16.6ms.

---

## Firebase DB 구조

```
Firebase Realtime DB:

/drivers/{driver_id}/profile
  name, phone, email, photo

/sessions/{driver_id}/{session_id}/
  start_time
  end_time
  gps_path/{index}    → {lat, lon, timestamp}
  events/{index}      → {timestamp, state, lat, lon}

/gps/{driver_id}      → 실시간 현재 위치 (lat, lon, timestamp)
```

---

## 디렉토리 구조

```
docs/
├── architecture.md
├── uart_interface.md
├── can_interface.md
├── freertos_tasks.md
├── perclos_algorithm.md
├── benchmark.md
├── schedule.md
├── assets/
│   ├── system_architecture.svg
│   └── freertos_task_diagram.png
└── README.md
```
