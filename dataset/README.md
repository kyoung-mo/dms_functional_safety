# 📦 dataset — 캘리브레이션 · 벤치마크 데이터셋

> Hailo DFC 양자화 캘리브레이션 + EAR 임계값 탐색 + 5가지 환경 벤치마크용 이미지 데이터셋  
> WIDER Face val set 기반 캘리브레이션 300장 + 직접 촬영 라벨 이미지 1000장

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.13-3776AB?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3.2-F7931E?logo=scikitlearn&logoColor=white)
![Hailo DFC](https://img.shields.io/badge/Hailo%20DFC-3.33.1-00B5AD)
![YOLOv8-face](https://img.shields.io/badge/YOLOv8--face-crop%20tool-512BD4)
![WIDER Face](https://img.shields.io/badge/Dataset-WIDER__val-lightgrey)

---

## 개요

두 가지 목적의 이미지 데이터를 포함한다.

| 용도 | 디렉토리 | 이미지 수 | 설명 |
|---|---|---|---|
| NPU 양자화 캘리브레이션 | `calib_images/` | 300장 | WIDER_val 기반 얼굴 크롭, DFC INT8 변환 시 사용 |
| EAR 임계값 탐색 · 벤치마크 | `infer_data/` | 1000장 | 직접 촬영, `*_open.jpg` / `*_close.jpg` 라벨링 |

---

## 1. 캘리브레이션 데이터 (`calib_images/`)

### 구성

| 항목 | 내용 |
|---|---|
| 원본 출처 | WIDER Face Validation Set |
| 이미지 수 | **300장** |
| 전처리 | YOLOv8-face 얼굴 검출 → 크롭 → 192×192px 리사이즈 |
| 파일 형식 | `.jpg` |
| 입력 해상도 | 192×192 (face_landmarks_lite 요구 해상도) |

### 사용 방법

```bash
# WIDER_val 다운로드 후 raw/ 에 배치 → 크롭 스크립트 실행
python scripts/crop_faces.py --input raw/ --output calib_images/ --count 300 --size 192

# DFC 캘리브레이션에서 참조
# → ../conversion/scripts/compile_landmarks.sh 내에서 calib_images/ 경로 지정
```

---

## 2. 벤치마크 · 임계값 탐색 데이터 (`infer_data/`)

### 구성

| 항목 | 내용 |
|---|---|
| 이미지 수 | **1000장** (open=500 / close=500) |
| 라벨링 방법 | 파일명 기반 (`*_open.jpg` / `*_close.jpg`) |
| 촬영 대상 | 단일 인물 (본인) |
| 해상도 | 640×480 (실제 카메라와 동일) |
| 밝기 조건 | 밝은 환경만 |

### 파일명 규칙

```
YYYYMMDD_HHMMSS_open.jpg    # 눈 뜬 상태 (정상)
YYYYMMDD_HHMMSS_close.jpg   # 눈 감은 상태 (졸음)
```

---

## EAR 임계값 탐색 (`best_threshold.py`)

`infer_data/` 의 1000장을 기반으로 최적 EAR 임계값을 탐색한다.

### 탐색 방법

```python
# 0.001 단위로 0.20 ~ 0.26 범위 탐색
for thr in np.arange(0.20, 0.32, 0.01):
    preds = [1 if e < thr else 0 for e in ears]
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, ...)
    acc = np.mean(np.array(labels) == np.array(preds))
```

### 탐색 결과 요약

| 임계값 | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| 0.220 | 66.2% | 97.2% | 78.8% | 73.8% |
| 0.221 | 66.4% | 97.8% | 79.1% | 74.1% |
| 0.222 | 66.4% | 98.2% | 79.3% | 74.3% |
| **0.223** | **66.5%** | **98.6%** | **79.5%** | **74.5%** ← 최고 F1 |
| 0.224 | 66.4% | 98.8% | 79.4% | 74.2% |
| 0.231 | 65.7% | 100.0% | 79.3% | 73.9% |

> **최적 임계값: 0.223** (F1 79.5%, Accuracy 74.5%)  
> 0.231부터 Recall 100%이지만 Precision·Accuracy 하락 → 0.223 선택

### 설치

```bash
pip install "scikit-learn==1.3.2"
```

### 실행

```bash
# 0.01 단위 1차 탐색
python inference/best_threshold.py

# 0.001 단위 세밀 탐색 (0.223 근방)
python inference/best_threshold_001.py
```

---

## 데이터 한계

```
✅ 신뢰할 수 있는 부분
  - 1000장 균형 데이터 (open 500 + close 500)
  - 파일명 기반 명확한 라벨
  - 실제 카메라와 동일한 해상도 (640×480)
  - 동일한 추론 파이프라인 통과 (YOLO → crop → LM → EAR)

❌ 한계
  - 단일 인물 → 다른 사람에게는 임계값 다를 수 있음
  - 정적 이미지 → 실제 졸음(서서히 눈 감기는 과정) 미반영
  - 밝은 환경만 → 야간·역광·측면 얼굴 미포함
  - 안경·마스크 착용 없음
```

---

## 디렉토리 구조

```
dataset/
├── raw/                        # WIDER_val 원본 (Git 미포함 — .gitignore)
├── calib_images/               # 캘리브레이션 이미지 300장 (.jpg)
│   ├── calib_000.jpg
│   └── ...
├── infer_data/                 # 벤치마크·임계값 탐색 이미지 1000장
│   ├── 20260601_090000_open.jpg
│   ├── 20260601_090001_close.jpg
│   └── ...
├── scripts/
│   └── crop_faces.py           # WIDER_val 기반 캘리브레이션 이미지 생성
└── README.md
```
