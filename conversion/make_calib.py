#!/usr/bin/env python3
"""
face_landmarks_lite Hailo 변환용 calibration 이미지 생성 (YOLOv8-face 검출).
WIDER_val 원본 → YOLOv8-face로 얼굴 검출 → 192x192 크롭 저장.
Haar Cascade 대비 오검출이 적어 calibration 품질이 높음.
실제 추론 파이프라인(YOLO 검출 → 크롭 → landmark)과 동일 분포.
"""
import cv2, glob, random
from pathlib import Path
from ultralytics import YOLO

ONNX_PATH = "models/yolov8_face.onnx"
WIDER_DIR = Path("data/WIDER_val/images")
OUT_DIR = Path("calib_face_192")
TARGET_COUNT = 300
CONF_TH = 0.5          # 검출 신뢰도 임계값 (오검출 배제)
MIN_FACE_PX = 80       # 너무 작은 얼굴 스킵
CROP_SIZE = 192
MARGIN = 0.2

print(f"[Detector] Loading {ONNX_PATH}")
model = YOLO(ONNX_PATH, task="detect")

images = glob.glob(str(WIDER_DIR / "**" / "*.jpg"), recursive=True)
random.seed(42)
random.shuffle(images)
print(f"전체 후보 이미지: {len(images)}장")

OUT_DIR.mkdir(parents=True, exist_ok=True)
count = 0
for img_path in images:
    if count >= TARGET_COUNT:
        break
    frame = cv2.imread(img_path)
    if frame is None:
        continue

    res = model.predict(source=frame, imgsz=320, conf=CONF_TH, verbose=False, device='cpu')[0]
    boxes = res.boxes
    if boxes is None or len(boxes) == 0:
        continue

    xyxy = boxes.xyxy.cpu().numpy()
    # 가장 큰 얼굴 1개
    x1, y1, x2, y2 = max(xyxy, key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
    w, h = x2 - x1, y2 - y1
    if w < MIN_FACE_PX or h < MIN_FACE_PX:
        continue

    # 여백 추가
    mx, my = int(w * MARGIN), int(h * MARGIN)
    cx1 = max(0, int(x1 - mx))
    cy1 = max(0, int(y1 - my))
    cx2 = min(frame.shape[1], int(x2 + mx))
    cy2 = min(frame.shape[0], int(y2 + my))

    crop = frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        continue

    crop = cv2.resize(crop, (CROP_SIZE, CROP_SIZE))
    cv2.imwrite(str(OUT_DIR / f"calib_{count:04d}.jpg"), crop)
    count += 1
    if count % 50 == 0:
        print(f"  {count}장 생성...")

print(f"완료: {count}장 → {OUT_DIR}/")
