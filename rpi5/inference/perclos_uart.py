"""
실시간 카메라 기반 DMS (Headless + 동적 임계값 + UART 송신)
YOLO HEF + face_landmarks HEF -> 졸음 판정 -> UART로 STM32에 상태 송신
"""
import cv2
import time
import serial
import numpy as np
from collections import deque
from pathlib import Path
from hailo_platform import (HEF, Device, VDevice, HailoStreamInterface,
                            InferVStreams, ConfigureParams,
                            InputVStreamParams, OutputVStreamParams, FormatType)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from detection_hef import Detector

try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ picamera2 모듈을 찾을 수 없습니다.")
    exit()

LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

# --- 동적 임계값 및 상태 설정 ---
DROWSINESS_TIME = 1.5
EAR_HISTORY_LEN = 150
EAR_RATIO = 0.75

# --- UART 설정 ---
UART_PORT = "/dev/serial0"
UART_BAUD = 115200
SEND_INTERVAL = 0.1          # 100ms 주기 송신

def calculate_ear(eye_points):
    v1 = np.linalg.norm(eye_points[1] - eye_points[5])
    v2 = np.linalg.norm(eye_points[2] - eye_points[4])
    h = np.linalg.norm(eye_points[0] - eye_points[3])
    if h == 0: return 0.0
    return (v1 + v2) / (2.0 * h)

BASE = Path(__file__).resolve().parent.parent
HEF_LANDMARK = str(BASE / "models" / "face_landmarks_lite.hef")

print("[1/4] VDevice 생성 + 두 모델 초기화 (공유)...")
devices = Device.scan()
shared_vdevice = VDevice(device_ids=devices)

detector = Detector(conf_threshold=0.5, vdevice=shared_vdevice)

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

print("[2/4] UART 포트 열기...")
ser = serial.Serial(UART_PORT, UART_BAUD, timeout=1)

print("[3/4] 카메라 연결...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

print("[4/4] Headless DMS + UART 송신 시작! (종료: Ctrl+C)")
prev_time = time.time()
fps = 0.0

eye_closed_start_time = None
driver_state = 0
STATE_STR = {0: "NORMAL", 1: "CAUTION", 2: "DROWSY WARNING!!!"}

ear_history = deque(maxlen=EAR_HISTORY_LEN)
current_threshold = 0.23

# --- UART 송신용 ---
seq = 0
last_send_time = time.time()

try:
    while True:
        t0 = time.time()
        frame_rgb = picam2.capture_array()
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        curr_time = time.time()
        td = curr_time - prev_time
        if td > 0: fps = (fps * 0.9) + ((1.0 / td) * 0.1)
        prev_time = curr_time

        dets = detector.detect_faces(frame, with_conf=True)
        avg_ear = 0.0

        if dets:
            x1, y1, x2, y2, _ = dets[0]
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

                le = lm[LEFT_EYE_IDX][:, :2]
                re = lm[RIGHT_EYE_IDX][:, :2]
                avg_ear = (calculate_ear(le) + calculate_ear(re)) / 2.0

                ear_history.append(avg_ear)
                if len(ear_history) > 50:
                    ear_max = np.percentile(ear_history, 90)
                    current_threshold = ear_max * EAR_RATIO

                if avg_ear < current_threshold:
                    if eye_closed_start_time is None:
                        eye_closed_start_time = curr_time
                        driver_state = 1
                    else:
                        if (curr_time - eye_closed_start_time) >= DROWSINESS_TIME:
                            driver_state = 2
                else:
                    eye_closed_start_time = None
                    driver_state = 0
        else:
            eye_closed_start_time = None
            driver_state = 0

        # -------------------------------------------------
        # UART 송신 (100ms 주기)
        # -------------------------------------------------
        if curr_time - last_send_time >= SEND_INTERVAL:
            seq = (seq + 1) % 256
            ear_int = int(avg_ear * 100)        # EAR×100 (옵션B)
            if ear_int > 255:
                ear_int = 255
            
            checksum = (0xAA + driver_state + ear_int + seq) & 0xFF
            frame = bytes([0xAA, driver_state, ear_int, seq, checksum])
            ser.write(frame)
            last_send_time = curr_time

        sys.stdout.write(
            f"\r[DMS] FPS: {fps:4.1f} | EAR: {avg_ear:.3f} (Thr:{current_threshold:.3f}) "
            f"| STATE: {STATE_STR[driver_state]:18s} | Seq: {seq:3d} "
        )
        sys.stdout.flush()

except KeyboardInterrupt:
    print("\n정상 종료합니다.")
finally:
    picam2.stop()
    ser.close()
