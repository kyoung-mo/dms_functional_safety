"""
실시간 카메라 기반 DMS 검증 (Headless 모드 + 동적 임계값 Dynamic Threshold)
YOLO HEF + face_landmarks HEF -> 터미널 결과 로그 출력
"""
import cv2
import time
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
DROWSINESS_TIME = 1.5       # 졸음 판정 지속 시간 (초)
EAR_HISTORY_LEN = 150       # 약 2.5~3초 분량의 프레임(56 FPS 기준) 저장
EAR_RATIO = 0.75            # EAR 최대값 대비 75% 이하로 떨어지면 눈을 감은 것으로 판정

def calculate_ear(eye_points):
    v1 = np.linalg.norm(eye_points[1] - eye_points[5])
    v2 = np.linalg.norm(eye_points[2] - eye_points[4])
    h = np.linalg.norm(eye_points[0] - eye_points[3])
    if h == 0: return 0.0
    return (v1 + v2) / (2.0 * h)

BASE = Path(__file__).resolve().parent.parent
HEF_LANDMARK = str(BASE / "models" / "face_landmarks_lite.hef")

print("[1/3] VDevice 생성 + 두 모델 초기화 (공유)...")
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

print("[2/3] 카메라 연결...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()

print("[3/3] Headless DMS (동적 임계값 적용) 구동 시작! (종료: Ctrl+C)")
prev_time = time.time()
fps = 0.0

# --- 상태 추적용 변수 ---
eye_closed_start_time = None 
driver_state = 0  
STATE_STR = {0: "NORMAL", 1: "CAUTION", 2: "DROWSY WARNING!!!"}

# --- 동적 임계값 큐 ---
ear_history = deque(maxlen=EAR_HISTORY_LEN)
current_threshold = 0.23 # 초기 기본값

try:
    while True:
        t0 = time.time()
        frame_rgb = picam2.capture_array()
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        t_cam = time.time()
        curr_time = time.time()
        
        td = curr_time - prev_time
        if td > 0: fps = (fps * 0.9) + ((1.0 / td) * 0.1)
        prev_time = curr_time

        dets = detector.detect_faces(frame, with_conf=True)
        t_yolo = time.time()
        t_lm = t_yolo
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
                t_lm = time.time()

                le = lm[LEFT_EYE_IDX][:, :2]
                re = lm[RIGHT_EYE_IDX][:, :2]
                avg_ear = (calculate_ear(le) + calculate_ear(re)) / 2.0

                # -------------------------------------------------
                # 핵심: 동적 임계값 갱신
                # -------------------------------------------------
                ear_history.append(avg_ear)
                if len(ear_history) > 50: # 데이터가 어느 정도 쌓이면 작동
                    # 상위 10%의 값을 현재 눈을 뜬 최대치(EAR_max)로 간주 (튀는 값 방지)
                    ear_max = np.percentile(ear_history, 90) 
                    current_threshold = ear_max * EAR_RATIO
                
                # PERCLOS 상태 판정
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

        # 로그 출력 (Thr 값이 고개 각도에 따라 유동적으로 변하는지 확인)
        sys.stdout.write(
            f"\r[DMS] FPS: {fps:4.1f} | EAR: {avg_ear:.3f} (Thr:{current_threshold:.3f}) | STATE: {STATE_STR[driver_state]:18s} "
        )
        sys.stdout.flush()

except KeyboardInterrupt:
    print("\n정상 종료합니다.")
finally:
    picam2.stop()
