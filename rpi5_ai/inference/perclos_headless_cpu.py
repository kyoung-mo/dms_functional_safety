import cv2
import time
import numpy as np
from pathlib import Path
from hailo_platform import (HEF, Device, VDevice, HailoStreamInterface,
                            InferVStreams, ConfigureParams,
                            InputVStreamParams, OutputVStreamParams, FormatType)
import sys
from ultralytics import YOLO

try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ picamera2 모듈을 찾을 수 없습니다.")
    exit()

LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

ONNX_PATH = "../models/yolov8_face.onnx"
HEF_LANDMARK = "../models/face_landmarks_lite.hef"

print("[1/3] CPU YOLOv8 로드 및 NPU 랜드마크 초기화...")
detector = YOLO(ONNX_PATH, task="detect")

devices = Device.scan()
shared_vdevice = VDevice(device_ids=devices)
hef_lm = HEF(HEF_LANDMARK)
cfg_lm = ConfigureParams.create_from_hef(hef_lm, interface=HailoStreamInterface.PCIe)
ng_lm = shared_vdevice.configure(hef_lm, cfg_lm)[0]
ngp_lm = ng_lm.create_params()
ii_lm = hef_lm.get_input_vstream_infos()[0]
ivp_lm = InputVStreamParams.make_from_network_group(ng_lm, quantized=False, format_type=FormatType.FLOAT32)
ovp_lm = OutputVStreamParams.make_from_network_group(ng_lm, quantized=False, format_type=FormatType.FLOAT32)

def infer_landmark(img192_rgb):
    inp = np.expand_dims(img192_rgb.astype(np.float32), 0)
    with InferVStreams(ng_lm, ivp_lm, ovp_lm) as pipeline:
        with ng_lm.activate(ngp_lm):
            out = pipeline.infer({ii_lm.name: inp})
    return out["face_landmarks_lite/conv22"][0].flatten().reshape(468, 3)

print("[2/3] 카메라 연결...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

print("[3/3] 대조군(CPU YOLO + Headless) 구동 시작...")
prev_time = time.time()
fps = 0.0

try:
    for _ in range(100):  # 100프레임 동안 평균 FPS 측정
        t0 = time.time()
        frame_rgb = picam2.capture_array()
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        t_cam = time.time()

        curr_time = time.time()
        td = curr_time - prev_time
        if td > 0: fps = (fps * 0.9) + ((1.0 / td) * 0.1)
        prev_time = curr_time

        # YOLO 검출 (CPU 연산 강제)
        res = detector.predict(source=frame, imgsz=320, conf=0.5, verbose=False, device='cpu')[0]
        dets = res.boxes
        t_yolo = time.time()
        t_lm = t_yolo

        if dets is not None and len(dets) > 0:
            xyxy = list(dets.xyxy.cpu().numpy()[0])
            x1, y1, x2, y2 = map(int, xyxy[:4])
            w, h = x2 - x1, y2 - y1
            size = max(w, h)
            cx, cy = x1 + w/2, y1 + h/2
            size = int(size + size * 0.2)
            nx1 = max(0, int(cx - size/2))
            ny1 = max(0, int(cy - size/2))
            crop = frame[ny1:min(frame.shape[0], ny1+size), nx1:min(frame.shape[1], nx1+size)]

            if crop.size > 0:
                img192 = cv2.resize(crop, (192, 192))
                img192_rgb = cv2.cvtColor(img192, cv2.COLOR_BGR2RGB)
                lm = infer_landmark(img192_rgb)
                t_lm = time.time()

        sys.stdout.write(
            f"\r[대조군 CPU] FPS: {fps:4.1f} | (cam:{(t_cam-t0)*1000:3.1f}ms YOLO(CPU):{(t_yolo-t_cam)*1000:4.1f}ms LM:{(t_lm-t_yolo)*1000:3.1f}ms)"
        )
        sys.stdout.flush()
    print("\n측정 완료.")
except KeyboardInterrupt:
    pass
finally:
    picam2.stop()
