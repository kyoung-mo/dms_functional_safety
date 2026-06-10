import numpy as np
import cv2
import onnxruntime as ort
from pathlib import Path
from sklearn.metrics import precision_recall_fscore_support
import random

MODEL_DIR = Path("../models")
DATASET_PATH = Path("/home/pi/project/dms/dataset/infer_data")

LEFT_EYE_IDX  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

from ultralytics import YOLO
detector = YOLO(str(MODEL_DIR / "yolov8_face.onnx"), task="detect")
sess = ort.InferenceSession(str(MODEL_DIR / "face_landmarks_lite.onnx"), providers=['CPUExecutionProvider'])

def ear(pts):
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    h  = np.linalg.norm(pts[0] - pts[3])
    return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

random.seed(42)
all_files = sorted(DATASET_PATH.glob("*.jpg"))
open_files  = random.sample([f for f in all_files if "_open"  in f.name], 100)
close_files = random.sample([f for f in all_files if "_close" in f.name], 100)

ears, labels = [], []
for fpath, label in [(f, 0) for f in open_files] + [(f, 1) for f in close_files]:
    img = cv2.imread(str(fpath))
    res = detector.predict(source=img, imgsz=320, conf=0.5, verbose=False, device='cpu')[0]
    if not res.boxes or len(res.boxes) == 0: continue
    x1,y1,x2,y2 = map(int, res.boxes.xyxy[0][:4].cpu().numpy())
    w,h = x2-x1, y2-y1
    size = int(max(w,h)*1.2)
    cx,cy = x1+w//2, y1+h//2
    crop = img[max(0,cy-size//2):cy+size//2, max(0,cx-size//2):cx+size//2]
    if crop.size == 0: continue
    img192 = cv2.resize(crop,(192,192))
    inp = np.expand_dims(cv2.cvtColor(img192,cv2.COLOR_BGR2RGB).astype(np.float32)/255.0, 0)
    lm = sess.run(None,{sess.get_inputs()[0].name: inp})[0].flatten().reshape(468,3)
    e = (ear(lm[LEFT_EYE_IDX][:,:2]) + ear(lm[RIGHT_EYE_IDX][:,:2])) / 2.0
    ears.append(e)
    labels.append(label)

print(f"\n{'threshold':>10} {'Precision':>10} {'Recall':>8} {'F1':>8} {'Accuracy':>10}")
print("-" * 50)
for thr in np.arange(0.230, 0.251, 0.001):
    preds = [1 if e < thr else 0 for e in ears]
    p, r, f1, _ = precision_recall_fscore_support(labels, preds, average='binary', pos_label=1, zero_division=0)
    acc = np.mean(np.array(labels) == np.array(preds))
    print(f"  {thr:.3f}     {p*100:>8.1f}%  {r*100:>6.1f}%  {f1*100:>6.1f}%  {acc*100:>8.1f}%")
