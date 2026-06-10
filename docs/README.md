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
AI 노드(rpi5)와 안전 제어 노드(stm32)가 독립적으로 개발 가능하도록 설계 기준을 확정했다.

---

## 문서 목록

| 파일 | 내용 |
|---|---|
| `architecture.md` | 시스템 아키텍처 개요 (3-노드 구조, 설계 원칙) |
| `uart_interface.md` | UART 바이너리 프레임 정의 (RPi5 ↔ STM32) |
| `can_interface.md` | CAN 메시지 정의 요약 (DBC 연동) |
| `freertos_tasks.md` | FreeRTOS 4-Task 구조 및 우선순위 설계 |
| `perclos_algorithm.md` | PERCLOS 졸음 판정 알고리즘 상세 |
| `benchmark.md` | NPU vs CPU 추론 벤치마크 결과 |
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

| 조건 | 동작 |
|---|---|
| 정상 수신 | STM32 heartbeat_counter 리셋, Failsafe 해제 |
| **500ms 미수신** | Failsafe 진입 → DTC `0x7DF` CAN 송출 → LED 소등 |

---

## 시스템 설계 원칙

| 원칙 | 내용 |
|---|---|
| **물리적 결함 격리** | AI 추론(RPi5)과 안전 제어(STM32)를 별개 하드웨어로 분리 |
| **Fail-safe 설계** | Heartbeat 단절 시 침묵하지 않고 DTC로 명시적 보고 |
| **우선순위 기반 실시간성** | AI 부하와 무관하게 RTOS 우선순위로 안전 기능 보장 |
| **표준 인터페이스** | DBC 기반 CAN, UDS 호환 DTC 포맷 사용 |
| **엣지-클라우드 분리** | 차량 단 실시간 판정 + 관제 서버 집계 분리 |

---

## PERCLOS 알고리즘 요약

| 파라미터 | 값 | 설명 |
|---|---|---|
| 동적 임계값 | 상위 10% EAR × 0.75 | 개인 특성 자동 반영 |
| 졸음 판정 지속 | **1.5초** | ~20프레임 @ 13.4 FPS |
| 출력 상태 | 0 / 1 / 2 | 정상 / 주의 / 위험 |
| 히스테리시스 | 적용 | State 0↔2 직접 전환 방지 |

---

## NPU 벤치마크 결과 요약

| 항목 | NPU (Hailo-8) | CPU (RPi5) | 비율 |
|---|---|---|---|
| 추론 FPS | **13.4 FPS** (Headless) | ~4.5 FPS | **2.96배** |
| 주요 병목 | `capture_array()` ~40ms | 추론 ~70ms | — |
| X11 FPS | ~12–13 FPS (SSH X11 오버헤드) | — | — |

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
│   ├── system_architecture.svg   # 시스템 구조도
│   └── freertos_task_diagram.png
└── README.md
```
