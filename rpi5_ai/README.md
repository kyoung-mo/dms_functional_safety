# 🤖 rpi5_ai — AI 추론 노드 (졸음 인식)

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
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3.2-F7931E?logo=scikitlearn&logoColor=white)
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
face_landmarks_lite (Hailo-8 NPU)  ── 468pts (0–192px 좌표계)
    ↓
EAR 계산 (양쪽 눈 각 6점 → Eye Aspect Ratio)
    ↓
PERCLOS 졸음 판정 (동적 임계값)
    ↓
UART 바이너리 송신  [0xAA | State | EAR×100 | Seq | CRC]  (100ms 주기)
    ↓
STM32 안전 제어 노드
```

---

## PERCLOS 알고리즘

| 파라미터 | 값 | 설명 |
|---|---|---|
| 동적 임계값 기준 | 상위 10% EAR × 0.75 | 운전 초기 EAR 히스토리 기반 개인 적응 |
| 보정 고정 임계값 | **0.223** | 데이터셋 1000장 기반 최적 임계값 (졸음 모드 fallback) |
| 졸음 판정 지속 | **1.5초** | ~20프레임 @ 13 FPS (카메라 포함 기준) |
| 복귀 조건 | 눈뜸 **10프레임 연속** | ~0.7초 @ 13 FPS |
| 출력 상태 | 0 / 1 / 2 | 정상 / 주의 / 위험 |

### 졸음 모드 임계값 동결 (is_drowsy)

동적 임계값의 구조적 결함을 발견하고 해결했다:

```
[문제] 눈을 오래 감으면 낮은 EAR이 히스토리에 누적
       → 동적 임계값이 함께 하락 → 감은 눈도 '정상'으로 오판
       → 졸음이 지속될수록 경고가 풀리는 치명적 결함

[해결] 정상/졸음 2-모드 분리
  정상 모드  : EAR 히스토리 누적 + 동적 임계값 (상위 10% × 0.75)
  졸음 모드  : 누적 중단 + 진입 시점 임계값 동결 (frozen_threshold)
              동결값 없으면 검증된 고정값 0.223 fallback
  복귀       : frozen_threshold 초과 EAR 10프레임 연속 → 정상 모드 전환
  안전 처리  : 졸음 중 얼굴 미검출(고개 떨굼 가능성) 시 경고 상태 유지
```

> 고정 임계값 0.223은 `dataset/` 1000장 기반 Recall 98.8% — 졸음 모드 고정 임계값의 유효성 검증.

---

## 🔬 NPU 벤치마크

> 측정 조건: 1000장 정적 이미지 (open=500 / close=500), EAR 임계값 0.223  
> **카메라 캡처 시간 · UART 송신 미포함** (AI 추론 파이프라인 단독 기준)

### FPS / Latency

| 환경 | FPS | 평균 Latency | YOLO | LM | P95 |
|---|---|---|---|---|---|
| **HEF+HEF** | **59.9** | **16.6ms** | 12.0ms | 4.6ms | 17.9ms |
| HEF+ONNX | 49.0 | 20.3ms | 16.2ms | 4.1ms | 23.9ms |
| ONNX+HEF | 21.0 | 47.5ms | 38.2ms | 9.3ms | 52.9ms |
| ONNX+ONNX (Hailo) | 14.1 | 70.9ms | 65.4ms | 5.5ms | 77.7ms |
| CPU (ONNX+ONNX) | 14.1 | 70.6ms | 65.2ms | 5.4ms | 77.5ms |

### 정확도

| 환경 | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| **HEF+HEF** | 63.1% | **98.8%** | 77.0% | 70.5% |
| HEF+ONNX | 62.4% | 99.4% | 76.6% | 69.7% |
| ONNX+HEF | 62.7% | 96.8% | 76.1% | 69.6% |
| ONNX+ONNX (Hailo) | 62.4% | 99.0% | 76.6% | 69.7% |
| CPU (ONNX+ONNX) | 62.4% | 99.0% | 76.6% | 69.7% |

### 핵심 결론

```
HEF+HEF 기준 CPU 대비 4.3배 향상 (14.1 → 59.9 FPS)
정확도(Recall 98.8%)는 CPU 환경과 동등 수준 유지
실시간 DMS 요구사항 15 FPS를 NPU 환경에서 충분히 달성
```

### 실제 배포 FPS와의 차이

| 기준 | FPS | 설명 |
|---|---|---|
| 벤치마크 (AI 파이프라인만) | 59.9 | 정적 이미지, 카메라 I/O 제외 |
| 실제 배포 (카메라 포함, Headless) | ~13 | 카메라 `capture_array()` ~40ms 블로킹 |

> 병목은 NPU가 아닌 카메라 캡처 I/O. NPU 추론 자체(16.6ms)는 실시간 요건 충족.

### 벤치마크 한계

```
- 카메라 캡처 시간 미포함 (정적 이미지 기준)
- 연속 스트리밍 아닌 정적 이미지 → PERCLOS 누적 계산 미포함
- 단일 인물 (본인만) → 개인 편향, 다른 사람에게 threshold 다를 수 있음
- 밝은 환경 / 정면 얼굴만 포함 (측면·안경·마스크 없음)
```

---

## 성능 지표 (실제 배포 기준)

| 항목 | 결과 |
|---|---|
| 추론 FPS (Headless, 카메라 포함) | **~13 FPS** |
| 추론 FPS (AI 파이프라인 기준) | **59.9 FPS** |
| NPU vs CPU (AI 파이프라인) | **4.3배 향상** |
| 주요 병목 구간 | `capture_array()` 블로킹 ~40ms |
| Python 후처리 | ~9ms |

---

## 실행 방법

```bash
# 가상환경 활성화 (HailoRT 4.23.0 포함)
source ~/dms_env/bin/activate

# Headless 모드 (실배포)
python inference/perclos_uart.py

# 벤치마크 실행
python inference/perclos_benchmark.py

# 임계값 탐색
python inference/best_threshold.py
```

---

## 주요 파라미터

```python
# config.py
UART_PORT        = "/dev/ttyAMA0"
UART_BAUDRATE    = 115200
FRAME_SYNC       = 0xAA
EAR_RATIO        = 0.75             # 동적 임계값 비율 (상위 10% EAR × 0.75)
FIXED_THRESHOLD  = 0.223            # 졸음 모드 fallback 고정 임계값 (Recall 98.8%)
DROWSINESS_TIME  = 1.5              # 졸음 판정 지속 시간 (초)
RECOVERY_FRAMES  = 10               # 졸음 → 정상 복귀 연속 눈뜸 프레임 수
UART_PERIOD_MS   = 100

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
rpi5_ai/
├── models/
│   ├── yolov8n_face.hef
│   └── face_landmarks_lite.hef
├── inference/
│   ├── perclos_uart.py           # 메인 추론 루프
│   ├── hailo_pipeline.py         # NPU VDevice 관리 (듀얼 모델 공유)
│   ├── ear_calc.py               # EAR 계산 (468pts → 눈 6점)
│   ├── perclos.py                # 동적 임계값 PERCLOS 판정
│   ├── perclos_benchmark.py      # 5가지 환경 벤치마크
│   ├── best_threshold.py         # 0.001 단위 임계값 탐색
│   └── best_threshold_001.py     # 0.001 단위 세밀 탐색
├── comm/
│   ├── uart_sender.py
│   └── frame_def.py
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
| scikit-learn | 1.3.2 (임계값 탐색) |
| OS | Raspberry Pi OS Bookworm (64-bit) |

---

## 주의 사항

- Hailo-8 VDevice 공유: 두 모델이 같은 VDevice 사용 → `activate()` 번갈아 호출
- UART TX/RX는 RPi5와 STM32 사이 **크로스 연결** (RPi TX → STM32 RX)
- ONNX+HEF 환경에서 LM 정확도가 미세하게 다를 수 있음 → CPU·NPU 간 타이밍 차이
