"""
실시간 카메라 기반 DMS 검증 (Headless 모드: 디스플레이 창 제거 버전)
YOLO HEF + face_landmarks HEF -> 터미널 결과 로그 출력
"""
import cv2
import time
import numpy as np
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

# --- EAR 설정 ---
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]

EAR_THRESHOLD = 0.23        # 눈 감음 판정 임계값 (상향 조정)
DROWSINESS_TIME = 1.5       # 졸음으로 판정할 지속 시간 (초)

def calculate_ear(eye_points):
    v1 = np.linalg.norm(eye_points[1] - eye_points[5])
    v2 = np.linalg.norm(eye_points[2] - eye_points[4])
    h = np.linalg.norm(eye_points[0] - eye_points[3])
    if h == 0:
        return 0.0
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

print("[3/3] Headless DMS 구동 시작! (종료: Ctrl+C)")
prev_time = time.time()
fps = 0.0

# --- 상태 추적용 변수 ---
eye_closed_start_time = None 
driver_state = 0  # 0: NORMAL, 1: CAUTION, 2: DROWSY

# 상태 텍스트 매핑
STATE_STR = {0: "NORMAL", 1: "CAUTION", 2: "DROWSY WARNING!!!"}

try:
    while True:
        t0 = time.time()

        frame_rgb = picam2.capture_array()
        frame = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        t_cam = time.time()
        curr_time = time.time()
        
        td = curr_time - prev_time
        if td > 0:
            fps = (fps * 0.9) + ((1.0 / td) * 0.1)
        prev_time = curr_time

        # 1) YOLO 검출 (NPU)
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
            nx2 = min(frame.shape[1], nx1 + size)
            ny2 = min(frame.shape[0], ny1 + size)
            crop = frame[ny1:ny2, nx1:nx2]

            if crop.size > 0:
                img192 = cv2.resize(crop, (192, 192))
                img192_rgb = cv2.cvtColor(img192, cv2.COLOR_BGR2RGB)

                # 2) landmark 추론 (NPU)
                lm = infer_landmark(img192_rgb)
                t_lm = time.time()

                le = lm[LEFT_EYE_IDX][:, :2]
                re = lm[RIGHT_EYE_IDX][:, :2]
                avg_ear = (calculate_ear(le) + calculate_ear(re)) / 2.0

                # 3) 시간 기반 시계열 상태 판정 (PERCLOS)
                if avg_ear < EAR_THRESHOLD:
                    if eye_closed_start_time is None:
                        eye_closed_start_time = curr_time
                        driver_state = 1
                    else:
                        closed_duration = curr_time - eye_closed_start_time
                        if closed_duration >= DROWSINESS_TIME:
                            driver_state = 2
                else:
                    eye_closed_start_time = None
                    driver_state = 0
        else:
            # 얼굴을 놓친 경우 상태 초기화
            eye_closed_start_time = None
            driver_state = 0

        t_viz = time.time() # 시각화 연산 없음 (0ms에 수렴)

        # 터미널에 실시간 상태 요약 출력 (\r 메커니즘으로 한 줄 업데이트)
        sys.stdout.write(
            f"\r[DMS] FPS: {fps:4.1f} | EAR: {avg_ear:.3f} | STATE: {STATE_STR[driver_state]:18s} "
            f"(cam:{ (t_cam-t0)*1000:3.1f}ms YOLO:{(t_yolo-t_cam)*1000:4.1f}ms LM:{(t_lm-t_yolo)*1000:3.1f}ms)"
        )
        sys.stdout.flush()

except KeyboardInterrupt:
    print("\n정상 종료합니다.")
finally:
    picam2.stop()
