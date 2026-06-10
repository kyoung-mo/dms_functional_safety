# 📦 dataset — 모델 캘리브레이션 데이터셋

> Hailo DFC INT8 양자화 캘리브레이션용 얼굴 이미지 데이터셋  
> WIDER Face val set 기반 전처리 이미지 300장

---

## 🔧 Tech Stack

![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)
![Hailo DFC](https://img.shields.io/badge/Hailo%20DFC-3.33.1-00B5AD)
![YOLOv8-face](https://img.shields.io/badge/YOLOv8--face-crop%20tool-512BD4)
![WIDER Face](https://img.shields.io/badge/Dataset-WIDER__val-lightgrey)

---

## 개요

Hailo DFC가 INT8 양자화를 수행할 때 사용하는 캘리브레이션 이미지 데이터.  
WIDER Face validation set에서 YOLOv8-face로 얼굴 영역을 검출·크롭한 이미지 **300장**을 사용한다.

기존 Haar Cascade 기반 캘리브레이션 대비 오탐(false positive)을 **30% 감소**시킨 방식이다.

---

## 데이터 구성

| 항목 | 내용 |
|---|---|
| 원본 출처 | WIDER Face Validation Set |
| 이미지 수 | **300장** |
| 전처리 방법 | YOLOv8-face 얼굴 검출 → 크롭 → 192×192px 리사이즈 |
| 파일 형식 | `.jpg` |
| 입력 해상도 | 192×192 (face_landmarks_lite 요구 해상도) |
| 사용 목적 | face_landmarks_lite NPU 양자화 캘리브레이션 |

---

## 전처리 파이프라인

```
WIDER_val 이미지 (raw/)
    → YOLOv8-face 얼굴 검출 (Bounding Box)
    → 바운딩박스 크롭 (margin 10%)
    → 192×192px 리사이즈
    → calib_images/ 저장 (.jpg)
```

---

## 사용 방법

```bash
# 1. WIDER_val 다운로드 후 raw/ 에 배치
#    http://shuoyang1213.me/WIDERFACE/

# 2. 얼굴 크롭 스크립트 실행
python scripts/crop_faces.py \
  --input raw/ \
  --output calib_images/ \
  --count 300 \
  --size 192

# 3. DFC 캘리브레이션에서 자동 참조
#    ../conversion/scripts/compile_landmarks.sh 내에서 경로 지정됨
```

---

## 스크립트 상세

```python
# scripts/crop_faces.py 주요 로직
model = YOLO("yolov8n_face.pt")  # 크롭 용도

for img_path in image_list[:count]:
    results = model(img_path)
    for box in results[0].boxes:
        x1, y1, x2, y2 = box.xyxy[0]
        face_crop = img[y1:y2, x1:x2]
        face_resized = cv2.resize(face_crop, (192, 192))
        cv2.imwrite(output_path, face_resized)
```

---

## 디렉토리 구조

```
dataset/
├── raw/                  # WIDER_val 원본 (Git 미포함 — .gitignore 처리)
├── calib_images/         # 전처리 완료 이미지 300장 (.jpg)
│   ├── calib_000.jpg
│   ├── calib_001.jpg
│   └── ...
├── scripts/
│   └── crop_faces.py     # YOLOv8-face 기반 전처리 스크립트
└── README.md
```

---

## 주요 참고 사항

- `raw/` 디렉토리는 `.gitignore` 처리 (용량 문제)
- `calib_images/` 300장은 레포에 포함 (장당 ~10KB, 총 ~3MB)
- 입력 해상도 **192×192px** 엄수 (DFC 최적화 기준 해상도)
- 캘리브레이션 이미지 품질이 NPU 양자화 정확도에 직결됨
- 300장 미만이면 양자화 오차 증가 가능성 있음
