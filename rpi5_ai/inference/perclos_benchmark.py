"""
DMS 성능 벤치마크
사용법:
  python perclos_benchmark.py --cpu
  python perclos_benchmark.py --hailo hef hef
  python perclos_benchmark.py --hailo onnx hef
  python perclos_benchmark.py --hailo hef onnx
  python perclos_benchmark.py --hailo onnx onnx
"""

import argparse
import sys
import time
import random
import numpy as np
import cv2
from pathlib import Path
from sklearn.metrics import classification_report, precision_recall_fscore_support

# ── 고정 설정 ──────────────────────────────
LEFT_EYE_IDX  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

MODEL_DIR    = Path(__file__).resolve().parent.parent / "models"
DATASET_PATH = Path("/home/pi/project/dms/dataset/infer_data")
EAR_THR      = 0.223   # open 평균 0.312, close 평균 0.182 기준 중간값
WARMUP       = 10
SAMPLES_PER_CLASS = 500   # open 500장 + close 500장 = 총 1000장
CAM_W, CAM_H = 640, 480   # 실제 DMS 카메라 입력 사이즈

YOLO_ONNX = str(MODEL_DIR / "yolov8_face.onnx")
YOLO_HEF  = str(MODEL_DIR / "yolov8_face_zoo.hef")
LM_ONNX   = str(MODEL_DIR / "face_landmarks_lite.onnx")
LM_HEF    = str(MODEL_DIR / "face_landmarks_lite.hef")

# ── EAR ────────────────────────────────────
def ear(pts):
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    h  = np.linalg.norm(pts[0] - pts[3])
    return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

# ── 데이터셋 로드 ───────────────────────────
def load_dataset():
    all_files = sorted(DATASET_PATH.glob("*.jpg"))
    open_files  = [f for f in all_files if "_open"  in f.name]
    close_files = [f for f in all_files if "_close" in f.name]

    # 각 클래스에서 SAMPLES_PER_CLASS장 랜덤 샘플
    random.seed(42)
    open_sampled  = random.sample(open_files,  min(SAMPLES_PER_CLASS, len(open_files)))
    close_sampled = random.sample(close_files, min(SAMPLES_PER_CLASS, len(close_files)))

    print(f"[데이터셋] open {len(open_sampled)}장 + close {len(close_sampled)}장 선택")
    print(f"[데이터셋] {CAM_W}×{CAM_H}로 리사이즈 후 메모리 로드 중...")

    items = []
    for fpath in open_sampled:
        img = cv2.imread(str(fpath))
        if img is not None:
            items.append((img, 0))
    for fpath in close_sampled:
        img = cv2.imread(str(fpath))
        if img is not None:
            items.append((img, 1))

    random.shuffle(items)
    mem_mb = len(items) * 640 * 480 * 3 / 1024 / 1024
    open_cnt  = sum(1 for _, l in items if l == 0)
    close_cnt = sum(1 for _, l in items if l == 1)
    print(f"[데이터셋] 로드 완료: 총 {len(items)}장 (open={open_cnt}, close={close_cnt}, 메모리={mem_mb:.0f}MB)")
    return items

# ── YOLO ONNX ──────────────────────────────
def load_yolo_onnx():
    from ultralytics import YOLO
    print("[YOLO] ONNX (CPU) 로드...")
    return YOLO(YOLO_ONNX, task="detect")

def detect_onnx(det, frame):
    res = det.predict(source=frame, imgsz=320, conf=0.5, verbose=False, device='cpu')[0]
    if not res.boxes or len(res.boxes) == 0: return None
    xyxy = res.boxes.xyxy.cpu().numpy()
    return max(xyxy, key=lambda b: (b[2]-b[0])*(b[3]-b[1]))

# ── YOLO HEF ───────────────────────────────
def load_yolo_hef(vdev):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from detection_hef import Detector
    print("[YOLO] HEF (NPU) 로드...")
    return Detector(conf_threshold=0.5, vdevice=vdev)

def detect_hef(det, frame):
    dets = det.detect_faces(frame, with_conf=True)
    return dets[0] if dets else None

# ── LM ONNX ────────────────────────────────
def load_lm_onnx():
    import onnxruntime as ort
    print("[LM] ONNX (CPU) 로드...")
    return ort.InferenceSession(LM_ONNX, providers=['CPUExecutionProvider'])

def infer_lm_onnx(sess, img):
    inp = np.expand_dims(img.astype(np.float32) / 255.0, 0)
    out = sess.run(None, {sess.get_inputs()[0].name: inp})
    return out[0].flatten().reshape(468, 3)

# ── LM HEF ─────────────────────────────────
def load_lm_hef(vdev):
    from hailo_platform import (HEF, HailoStreamInterface, ConfigureParams,
                                InputVStreamParams, OutputVStreamParams, FormatType)
    print("[LM] HEF (NPU) 로드...")
    hef = HEF(LM_HEF)
    cfg = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    ng  = vdev.configure(hef, cfg)[0]
    ngp = ng.create_params()
    ii  = hef.get_input_vstream_infos()[0]
    ivp = InputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)
    ovp = OutputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)
    return (ng, ngp, ii, ivp, ovp)

def infer_lm_hef(lm_obj, img):
    from hailo_platform import InferVStreams
    ng, ngp, ii, ivp, ovp = lm_obj
    inp = np.expand_dims(img.astype(np.float32), 0)
    with InferVStreams(ng, ivp, ovp) as pipe:
        with ng.activate(ngp):
            out = pipe.infer({ii.name: inp})
    return out["face_landmarks_lite/conv22"][0].flatten().reshape(468, 3)

# ── 크롭 ───────────────────────────────────
def crop_face(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox[:4])
    w, h = x2-x1, y2-y1
    size = int(max(w, h) * 1.2)
    cx, cy = x1 + w//2, y1 + h//2
    nx1 = max(0, cx - size//2)
    ny1 = max(0, cy - size//2)
    crop = frame[ny1:min(frame.shape[0], ny1+size),
                 nx1:min(frame.shape[1], nx1+size)]
    return cv2.resize(crop, (192, 192)) if crop.size > 0 else None

# ── 프레임 추론 ────────────────────────────
def run_frame(frame, ym, lm, yobj, lobj):
    t0 = time.time()
    bbox = detect_onnx(yobj, frame) if ym == "onnx" else detect_hef(yobj, frame)
    t1 = time.time()
    if bbox is None:
        return None, None, (t1-t0)*1000, 0.0, 0.0
    crop = crop_face(frame, bbox)
    if crop is None:
        return None, None, (t1-t0)*1000, 0.0, 0.0
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    lm_pts = infer_lm_onnx(lobj, rgb) if lm == "onnx" else infer_lm_hef(lobj, rgb)
    t2 = time.time()
    avg_ear = (ear(lm_pts[LEFT_EYE_IDX][:,:2]) + ear(lm_pts[RIGHT_EYE_IDX][:,:2])) / 2.0
    pred = 1 if avg_ear < EAR_THR else 0
    return pred, avg_ear, (t1-t0)*1000, (t2-t1)*1000, (t2-t0)*1000

# ── 메인 ───────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--cpu", action="store_true")
    grp.add_argument("--hailo", nargs=2, metavar=("YOLO","LM"), choices=["hef","onnx"])
    args = parser.parse_args()

    if args.cpu:
        ym, lm, label = "onnx", "onnx", "CPU (ONNX+ONNX)"
    else:
        ym, lm = args.hailo
        label = f"Hailo ({ym.upper()}+{lm.upper()})"

    print("=" * 55)
    print(f"  DMS 벤치마크: {label}")
    print(f"  EAR 임계값  : {EAR_THR}")
    print(f"  클래스당 샘플: {SAMPLES_PER_CLASS}장")
    print(f"  입력 사이즈  : {CAM_W}×{CAM_H}")
    print("=" * 55)

    dataset = load_dataset()
    if not dataset:
        print("[오류] 데이터셋 없음"); sys.exit(1)

    vdev = None
    if ym == "hef" or lm == "hef":
        from hailo_platform import Device, VDevice
        vdev = VDevice(device_ids=Device.scan())
        print("[Hailo] VDevice 초기화 완료")

    yobj = load_yolo_onnx() if ym == "onnx" else load_yolo_hef(vdev)
    lobj = load_lm_onnx()   if lm == "onnx" else load_lm_hef(vdev)

    # 워밍업
    print(f"\n[워밍업] {WARMUP}프레임...")
    for i in range(min(WARMUP, len(dataset))):
        frame, _ = dataset[i]
        run_frame(frame, ym, lm, yobj, lobj)
    print("[워밍업] 완료\n")

    # 측정
    labels, preds, lats, ytms, ltms, ftms = [], [], [], [], [], []
    no_face = 0
    total = len(dataset)
    print(f"[측정] {total}프레임 시작...")
    t_start = time.time()

    for i in range(total):
        frame, label_gt = dataset[i]
        t0 = time.time()
        pred, avg_ear, yt, lt, lat = run_frame(frame, ym, lm, yobj, lobj)
        t1 = time.time()
        if pred is None:
            no_face += 1; continue
        labels.append(label_gt)
        preds.append(pred)
        lats.append(lat); ytms.append(yt); ltms.append(lt); ftms.append(t1-t0)
        if (i+1) % 100 == 0:
            print(f"  {i+1}/{total} 처리 완료...")

    t_total = time.time() - t_start

    # 결과
    print("\n" + "=" * 55)
    print(f"  결과: {label}")
    print("=" * 55)

    avg_fps = len(ftms) / t_total if t_total > 0 else 0
    print(f"\n[속도]")
    print(f"  평균 FPS         : {avg_fps:.1f}")
    print(f"  평균 처리 시간   : {np.mean(lats):.1f} ms")
    print(f"  평균 YOLO 추론   : {np.mean(ytms):.1f} ms")
    print(f"  평균 LM 추론     : {np.mean(ltms):.1f} ms")

    print(f"\n[Latency]")
    print(f"  평균 : {np.mean(lats):.1f} ms")
    print(f"  최소 : {np.min(lats):.1f} ms")
    print(f"  최대 : {np.max(lats):.1f} ms")
    print(f"  P95  : {np.percentile(lats, 95):.1f} ms")

    if labels:
        p, r, f1, _ = precision_recall_fscore_support(
            labels, preds, average='binary', pos_label=1, zero_division=0)
        acc = np.mean(np.array(labels) == np.array(preds))
        print(f"\n[정확도] (EAR 임계값 {EAR_THR})")
        print(f"  Accuracy  : {acc*100:.1f}%")
        print(f"  Precision : {p*100:.1f}%")
        print(f"  Recall    : {r*100:.1f}%")
        print(f"  F1-Score  : {f1*100:.1f}%")
        print(f"\n  상세:")
        print(classification_report(
            labels, preds,
            labels=[0, 1],
            target_names=["open(정상)", "close(졸음)"],
            zero_division=0))

    open_cnt  = sum(1 for l in labels if l == 0)
    close_cnt = sum(1 for l in labels if l == 1)
    print(f"  평가 open={open_cnt}장, close={close_cnt}장")
    print(f"  얼굴 미검출: {no_face}장")
    print("=" * 55)

if __name__ == "__main__":
    main()
