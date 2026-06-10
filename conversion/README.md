# 🔄 conversion — Hailo NPU 모델 변환 파이프라인

> ONNX 모델을 Hailo Execution Format(HEF)으로 변환하는 파이프라인  
> YOLOv8-face + face_landmarks_lite 양자화 및 컴파일 스크립트

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![Hailo DFC](https://img.shields.io/badge/Hailo%20DFC-3.33.1-00B5AD)
![Model Zoo](https://img.shields.io/badge/Hailo%20Model%20Zoo-2.18.0-00B5AD)
![ONNX](https://img.shields.io/badge/ONNX-Runtime-005CED)
![WSL](https://img.shields.io/badge/WSL-Ubuntu%2024.04-E95420?logo=ubuntu&logoColor=white)

---

## 개요

Hailo-8 NPU에서 실행 가능한 `.hef` 파일을 생성하기 위한 모델 변환 파이프라인.  
ONNX 포맷의 모델을 Hailo Dataflow Compiler(DFC)를 통해 HAR → HEF로 변환한다.

```
ONNX  →  (parsing)  →  HAR  →  (optimization + quantization)  →  HAR  →  (compilation)  →  HEF
```

---

## 변환 대상 모델

| 모델 | 입력 포맷 | 출력 포맷 | 용도 |
|---|---|---|---|
| `yolov8n_face.onnx` | ONNX | HEF | 얼굴 검출 (YOLOv8-face) |
| `face_landmarks_lite.onnx` | ONNX | HEF | 랜드마크 추출 (468pts) |

---

## 변환 단계

### 1. 환경 설정

```bash
# WSL Ubuntu 24.04, Python 3.10 필수 (3.11+ 미지원)
conda create -n dfc_env python=3.10
conda activate dfc_env
pip install hailo-dataflow-compiler==3.33.1
pip install hailo-model-zoo==2.18.0
```

### 2. YOLOv8-face (Model Zoo CLI)

```bash
hailomz compile yolov8n_face \
  --ckpt models/yolov8n_face.onnx \
  --calib-path ../dataset/calib_images/ \
  --classes 1 \
  --hw-arch hailo8
```

### 3. face_landmarks_lite (DFC 직접 변환)

```bash
# Parsing
hailo parser onnx models/face_landmarks_lite.onnx \
  --net-name face_landmarks_lite \
  --hw-arch hailo8

# Optimization + Quantization (캘리브레이션 데이터 사용)
hailo optimize models/face_landmarks_lite.har \
  --calib-set-path ../dataset/calib_images/ \
  --hw-arch hailo8

# Compilation
hailo compiler models/face_landmarks_lite_optimized.har \
  --hw-arch hailo8
```

### 4. 변환 검증

```bash
# 프로파일 확인
hailo profiler models/face_landmarks_lite.hef

# 출력 레이어 확인
hailo inspect models/face_landmarks_lite.hef
```

---

## 디렉토리 구조

```
conversion/
├── models/
│   ├── yolov8n_face.onnx
│   ├── face_landmarks_lite.onnx
│   ├── yolov8n_face.har              # 중간 산출물
│   ├── face_landmarks_lite.har       # 중간 산출물
│   ├── yolov8n_face.hef              # 최종 산출물 ✓
│   └── face_landmarks_lite.hef       # 최종 산출물 ✓
├── scripts/
│   ├── compile_yolov8face.sh
│   ├── compile_landmarks.sh
│   └── verify_hef.py
└── README.md
```

---

## 주요 참고 사항

- DFC 3.33.1은 **Python 3.10** 환경에서만 정상 동작 (Native Linux / WSL)
- `face_landmarks_lite` 변환 시 캘리브레이션 데이터는 `../dataset/calib_images/` 참조
- 변환된 HEF 파일은 `../rpi5/models/`로 복사하여 사용
- `conv22` 출력: 1404값 (468pts × 3, x/y/z in 0–192px 공간)
- `conv25` 출력: confidence (sigmoid 내장 → 재적용 금지)

---

## 개발 환경

| 항목 | 버전 |
|---|---|
| OS | WSL Ubuntu 24.04 |
| Python | 3.10.x |
| Hailo DFC | 3.33.1 |
| Hailo Model Zoo | 2.18.0 |
| 컴파일 타깃 | Hailo-8 (`hw-arch hailo8`) |
