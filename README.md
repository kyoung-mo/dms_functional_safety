# 기능안전 기반 스마트 DMS (진행 중)

> RPi5 + Hailo-8 NPU + STM32(FreeRTOS) + CAN + 실시간 네비게이션 기반 졸음 감지 · 안전 제어 · 주행 분석 통합 운전자 모니터링 시스템  
> Intel AI SW Academy 9기 3차 프로젝트 (2026.06)

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.13-3776AB?logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-FreeRTOS-A8B9CC?logo=c&logoColor=black)
![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi%205-x2-A22846?logo=raspberrypi&logoColor=white)
![Hailo-8](https://img.shields.io/badge/Hailo--8-NPU-00B5AD)
![STM32](https://img.shields.io/badge/STM32-L475%20%7C%20F103-03234B?logo=stmicroelectronics&logoColor=white)

![HailoRT](https://img.shields.io/badge/HailoRT-4.23.0-00B5AD)
![Dataflow Compiler](https://img.shields.io/badge/Hailo%20DFC-3.33.1-00B5AD)
![Model Zoo](https://img.shields.io/badge/Hailo%20Model%20Zoo-2.18.0-00B5AD)
![YOLOv8-face](https://img.shields.io/badge/YOLOv8--face-detection-512BD4)
![face_landmarks_lite](https://img.shields.io/badge/face__landmarks__lite-468pts-512BD4)
![Flask](https://img.shields.io/badge/Flask-Web%20Server-000000?logo=flask&logoColor=white)
![Firebase](https://img.shields.io/badge/Firebase-Realtime%20DB-FFCA28?logo=firebase&logoColor=black)
![Kakao Maps](https://img.shields.io/badge/Kakao%20Maps-JS%20SDK-FFCD00)
![CAN](https://img.shields.io/badge/Protocol-CAN%20%7C%20UART-FF6F00)
![Vector CANdb++](https://img.shields.io/badge/Vector-CANdb%2B%2B-E2001A)
![SQLite](https://img.shields.io/badge/SQLite-Local%20DB-003B57?logo=sqlite&logoColor=white)

---

## 핵심 차별점

졸음 감지 프로젝트에 대해서는 공개된 예제가 많습니다. 본 프로젝트의 차별점은 **"무엇을 감지하느냐"가 아니라 "어떤 구조로 설계했느냐"** 에 있습니다.

- **물리적 결함 격리** — AI 추론(RPi5)과 안전 제어(STM32)를 별개 하드웨어로 분리. 단일 장애점 제거.
- **Fail-safe 설계** — 노드 간 Heartbeat가 끊기면 "모니터링 불가" 상태를 침묵하지 않고 CAN으로 명확히 보고.
- **우선순위 기반 실시간성** — AI 연산 부하가 급증해도 안전 기능(CAN 송신·고장 감지)은 RTOS 우선순위로 지연 없이 동작.
- **실시간 네비게이션 연동** — 졸음 이벤트 발생 위치를 GPS 좌표로 실시간 기록하고, 주행 후 분석 대시보드로 확인.

졸음 감지 AI(비결정적)와 실시간 안전 제어(결정적)를 **서로 다른 하드웨어 노드로 물리적으로 분리**하여, AI의 불안정성(지연·다운)이 차량 안전 기능을 침해하지 못하게 설계한 DMS입니다. 감지 결과는 차량 네트워크(CAN)로 전달되며, 노드 간 통신이 끊기면 즉시 고장 코드(DTC)를 송출합니다.

---

## 시스템 구조

<img width="1331" height="995" alt="image" src="https://github.com/user-attachments/assets/df74df34-3d4f-4d19-b3d9-cbcb3fb603bc" />

---

## 처리 파이프라인

```
카메라 → 얼굴 검출(YOLOv8) → 얼굴 크롭 → 랜드마크 468점 → EAR 연산 → 졸음 판정
                                                            │
                                                UART 바이너리 프레임
                                            [0xAA, State, EAR, Seq, Checksum]
                                                            ▼
                        STM32: 상태 수신 → 경고 출력 + CAN 송신 / Heartbeat 단절 시 DTC 송출
                                                            │
                                                       CAN 0x100
                                                            ▼
                                          RPi5 네비 노드 (MCP2515 수신)
                                          → 졸음 이벤트 좌표 기록 (SQLite)
                                          → 카카오맵 JS에 실시간 핀 표시

삼성폰 geolocation → Firebase → RPi5 네비 폴링 → 카카오맵 경로 실시간 표시
```

---

## 기술 스택

| 구분 | 기술 | 선택 이유 |
| --- | --- | --- |
| AI 추론 | RPi5 + Hailo-8 NPU, HailoRT | 엣지 추론, CPU 병목 없음 |
| 모델 변환 | Hailo DFC 3.33.1, Model Zoo 2.18.0 | ONNX → HEF 변환 파이프라인 |
| AI 모델 | YOLOv8-face + face_landmarks_lite (468pt) | 얼굴 검출·랜드마크 분리 구조 |
| 실시간 제어 | STM32 + FreeRTOS (C) | 결정적 실시간성, AI 노드와 물리 분리 |
| 이기종 통신 | UART 바이너리 (RPi5↔STM32) | 고정 길이 프레임, 파싱 단순 |
| 차량 통신 | CAN Bus (bxCAN + SN65HVD230) | 차량 도메인 표준, 다중 노드 지원 |
| CAN 수신 | MCP2515 (SPI-CAN, 네비 노드용) | RPi5에 CAN 내장 없음, SPI 변환 |
| 통신 정의 | Vector CANdb++ DBC, cantools | 자동차 업계 표준 인터페이스 정의 |
| 네비 웹서버 | Flask + 카카오맵 JS SDK | Rerun 없는 실시간 지도 갱신 |
| GPS 중계 | Firebase Realtime DB | HTTPS Mixed Content 우회 |
| 영구 저장 | SQLite (RPi5 로컬) | 네트워크 의존 없는 주행 로그 |
| 사후 분석 | 삼성폰 PWA (HTML + Chart.js) | 설치 앱 없이 브라우저에서 확인 |

---

## CAN 메시지 정의

| CAN ID | 방향 | 내용 | 주기 |
| --- | --- | --- | --- |
| `0x100` | STM32 → RPi5 네비 | 졸음 상태 (State: 0=정상 / 1=주의 / 2=위험) | 100ms |
| `0x101` | RPi5 네비 → STM32 | 수신 ACK | 수신 시마다 |
| `0x7DF` | STM32 → CAN Bus | DTC 송출 (Heartbeat 단절 시) | 이벤트 |

---

## 핵심 기능 (MVP)

| # | 기능 | 설명 |
| --- | --- | --- |
| 1 | AI 졸음 감지 (EAR/PERCLOS) | 얼굴 검출 → 랜드마크 → EAR 연산, 동적 임계값 적용 |
| 2 | 이기종 통신 | 판정 결과를 UART 바이너리 프레임으로 STM32에 전송 |
| 3 | 실시간 경고 · CAN 송출 | 졸음 임계값 초과 시 경고 + CAN 상태 메시지 |
| 4 | 기능안전 (Fail-safe) | Heartbeat 단절 감지 시 DTC 송출 + RTOS 우선순위 스케줄링 |
| 5 | 실시간 네비게이션 | 카카오맵에 주행 경로 표시, 졸음 이벤트 위치 핀 |
| 6 | GPS 연동 | 삼성폰 geolocation → Firebase → RPi5 네비 폴링 |
| 7 | 주행 분석 대시보드 | 주행시간, 졸음 횟수·시각, 이벤트 위치 사후 분석 |

**확장 (여유 시):** 운전자 인식(MobileFaceNet) 기반 개인 캘리브레이션, MAR(하품)/Head Pose 지표, UDS 진단 서브셋

---

## 프로젝트 구조

```
dms_functional_safety/
├── rpi5_ai/           # AI 추론 노드 (Python)
│   ├── models/        # HEF 모델 (YOLOv8-face, face_landmarks_lite)
│   ├── inference/     # 얼굴 검출 · 랜드마크 · EAR 연산
│   └── comm/          # UART 바이너리 송신 · Heartbeat
├── rpi5_navi/         # 네비게이션 노드 (Python/Flask)
│   ├── app.py         # Flask 웹서버 (카카오맵 서빙 + API)
│   ├── can_rx.py      # MCP2515 CAN 수신
│   ├── firebase_poll.py  # Firebase GPS 폴링
│   ├── db.py          # SQLite 주행 로그 저장
│   └── templates/     # 카카오맵 HTML (네비 화면 + 분석 대시보드)
├── stm32/             # 실시간 제어 노드 (C, FreeRTOS)
│   ├── tasks/         # Watchdog · CAN Tx · UART Rx · 경고 출력
│   └── can/           # DBC 기반 인코딩
├── pwa/               # 삼성폰 PWA (HTML + JS)
│   └── index.html     # geolocation → Firebase 업로드 + 분석 UI
├── dbc/               # CAN 메시지 정의 (DBC)
├── docs/              # 기획 · 설계 문서
└── README.md
```

> ※ 구조는 진행 중 변경될 수 있음.

---

## 일정

| 단계 | 기간 | 내용 |
| --- | --- | --- |
| 0. 인터페이스 확정 | 5/31 ~ 6/2 | UART 구조체 + DBC + Heartbeat 규약 확정 |
| 1. AI 추론 | 6/3 ~ 6/6 | 모델 변환, EAR 연산, NPU 벤치마크 |
| 2. 펌웨어 골격 | 6/7 ~ 6/9 | FreeRTOS 태스크, UART 연동, MVP 완성 |
| 3. CAN / 안전 | 6/10 ~ 6/11 | CAN Tx, Heartbeat 단절 감지, DTC |
| 4. 네비 · 분석 | 6/12 ~ 6/13 | Flask 네비, Firebase GPS, 분석 대시보드 |
| 5. 마무리 | 6/14 ~ 6/15 | 문서화, 통합 시연, 블로그 |

---

## 산출물

- 실행 가능한 프로토타입 (RPi5 AI 추론 + STM32 펌웨어 + 네비 웹 연동)
- DBC 파일 및 UART 인터페이스 정의서
- CPU vs NPU 벤치마크 결과
- 실시간 카카오맵 네비게이션 + 주행 분석 대시보드
- 기술 블로그 ([Velog](https://velog.io/@mommers))

---

## 개발 환경

- **AI 노드:** RPi5, Python 3.13.5, HailoRT 4.23.0
- **모델 변환:** WSL Ubuntu 24.04, Python 3.10, Dataflow Compiler 3.33.1, Model Zoo 2.18.0
- **제어 노드:** STM32 L475 (B-L475E-IOT01A2), FreeRTOS, STM32CubeIDE
- **네비 노드:** RPi5, Python 3.13.5, Flask, SQLite, MCP2515
- **PWA:** 삼성 갤럭시 (구형), Chrome 브라우저, Firebase Realtime DB
