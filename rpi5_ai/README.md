# 🤖 rpi5 — AI 추론 노드 (졸음 인식)

> RPi5 + Hailo-8 NPU 기반 실시간 얼굴 검출 · 랜드마크 · PERCLOS 졸음 판정  
> YOLOv8-face + face_landmarks_lite 듀얼 NPU 파이프라인, UART 바이너리 송신

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.13.5-3776AB?logo=python&logoColor=white)
![HailoRT](https://img.shields.io/badge/HailoRT-4.23.0-00B5AD)
![Hailo-8](https://img.shields.io/badge/Hailo--8-NPU-00B5AD)
![YOLOv8-face](https://img.shields.io/badge/YOLOv8--face-detection-512BD4)
![face_landmarks_lite](https://img.shields.io/badge/face__landmarks__lite-468pts-512BD4)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![Raspberry Pi 5](https://img.shields.io/badge/Raspberry%20Pi%205-AI%20HAT%2B-A22846?logo=raspberrypi&logoColor=white)
![UART](https://img.shields.io/badge/Protocol-UART%20Serial-555555)

---

## 개요

RPi5와 Hailo-8 NPU를 사용하여 카메라 영상에서 운전자 얼굴을 실시간으로 검출하고,  
랜드마크 468점을 추출하여 PERCLOS 기반 졸음 판정을 수행한다.  
판정 결과는 **100ms 주기 UART 바이너리 프레임**으로 STM32 안전 제어 노드에 전송된다.

---

## 처리 파이프라인

```
PiCamera2 (카메라 입력)
    ↓
YOLOv8-face (Hailo-8 NPU)  ── 얼굴 Bounding Box 검출
    ↓
얼굴 크롭 + 192×192 리사이즈
    ↓
face_landmarks_lite (Hailo-8 NPU)  ── 468pts 추출 (0–192px 좌표계)
    ↓
EAR 계산 (양쪽 눈 각 6점 → Eye Aspect Ratio)
    ↓
PERCLOS 졸음 판정 (동적 임계값, 1.5초 지속)
    ↓
UART 바이너리 송신  [0xAA | State | EAR×100 | SeqNum | CRC]
    ↓ (100ms 주기)
STM32 안전 제어 노드
```

---

## PERCLOS 알고리즘

| 파라미터 | 값 | 설명 |
|---|---|---|
| 동적 임계값 | `상위 10% EAR × EAR_RATIO` | 개인 특성 자동 반영 |
| `EAR_RATIO` | `0.75` | 임계값 민감도 조정 계수 |
| 졸음 판정 지속 | **1.5초** | ~20프레임 @ 13.4 FPS |
| 출력 상태 | 0 / 1 / 2 | 정상 / 주의 / 위험 |

---

## 성능 지표

| 항목 | 결과 |
|---|---|
| 추론 FPS (Headless) | **13.4 FPS** |
| NPU vs CPU 속도 | **2.96배 향상** |
| 주요 병목 구간 | `capture_array()` 블로킹 ~40ms |
| Python 후처리 | ~9ms |
| X11 모드 FPS | ~12–13 FPS (SSH X11 오버헤드, 실배포 무관) |

---

## 실행 방법

```bash
# 가상환경 활성화 (HailoRT 4.23.0 포함)
source ~/dms_env/bin/activate

# Headless 모드 (실배포)
python inference/perclos_uart.py

# 디버그 모드 (X11 디스플레이 출력)
DISPLAY=:0 python inference/perclos_uart.py --debug

# 쉘 앨리어스 (선택)
alias dms_ai='source ~/dms_env/bin/activate && python ~/dms/rpi5/inference/perclos_uart.py'
```

---

## 주요 파라미터

```python
# config.py
UART_PORT        = "/dev/ttyAMA0"   # UART4 (PA0/PA1, 크로스 연결)
UART_BAUDRATE    = 115200
FRAME_SYNC       = 0xAA
EAR_RATIO        = 0.75             # 동적 임계값 비율
PERCLOS_WINDOW_S = 1.5              # 졸음 판정 지속 시간 (초)
UART_PERIOD_MS   = 100              # 송신 주기

# 모델 경로
YOLO_HEF = "models/yolov8n_face.hef"
LM_HEF   = "models/face_landmarks_lite.hef"
```

---

## face_landmarks_lite 출력 주의 사항

| 출력 레이어 | 내용 | 주의 |
|---|---|---|
| `conv22` | 1404값 (468pts × 3, x/y/z in 0–192px 공간) | 좌표 정규화 필요 |
| `conv25` | Confidence (sigmoid **내장**) | **sigmoid 재적용 금지** |

---

## 디렉토리 구조

```
rpi5/
├── models/
│   ├── yolov8n_face.hef           # 얼굴 검출 모델 (HEF)
│   └── face_landmarks_lite.hef    # 랜드마크 모델 (HEF)
├── inference/
│   ├── perclos_uart.py            # 메인 추론 루프
│   ├── hailo_pipeline.py          # NPU VDevice 관리 (듀얼 모델 공유)
│   ├── ear_calc.py                # EAR 계산 (468pts → 눈 6점)
│   └── perclos.py                 # 동적 임계값 PERCLOS 판정
├── comm/
│   ├── uart_sender.py             # UART 바이너리 프레임 송신
│   └── frame_def.py               # 프레임 구조 상수 정의
├── config.py
└── README.md
```

---

## 개발 환경

| 항목 | 값 |
|---|---|
| Board | Raspberry Pi 5 (8GB) |
| NPU | Hailo-8 AI HAT+ |
| Python | 3.13.5 |
| HailoRT | 4.23.0 |
| OS | Raspberry Pi OS Bookworm (64-bit) |

---

## 주의 사항

- Hailo-8 **VDevice 공유**: 두 모델이 같은 VDevice 사용 → `activate()` 를 번갈아 호출
- UART TX/RX는 RPi5와 STM32 사이 **크로스 연결** (RPi TX → STM32 RX, RPi RX → STM32 TX)
- Headless 모드에서 13.4 FPS, X11 SSH 연결 시 12–13 FPS (X11 오버헤드로 감소하나 실배포 무관)
