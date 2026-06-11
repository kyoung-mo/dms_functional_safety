"""
실시간 카메라 기반 DMS (Headless + 동적 임계값 + UART 송신)
YOLO HEF + face_landmarks HEF -> 졸음 판정 -> UART로 STM32에 상태 송신

[v2] is_drowsy 동결 메커니즘 추가:
  - 정상 모드: ear_history 누적 + 동적 threshold (기존과 동일)
  - 졸음 모드: history 누적 중단 + frozen_threshold 사용 (캘리브 오염 방지)
  - 복귀: RECOVERY_FRAMES 연속 눈뜸 확인 후 정상 모드 전환
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
EAR_HISTORY_LEN = 300
EAR_RATIO = 0.75
EAR_OPEN_RATIO = 0.90
FIXED_THRESHOLD = 0.223      # 벤치마크 검증 고정 임계값 (Recall 98.8%) - frozen 없을 때 fallback
RECOVERY_FRAMES = 10         # 졸음 -> 정상 복귀에 필요한 연속 눈뜸 프레임 (~0.7s @ 13fps)

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

# --- 졸음 모드 동결 메커니즘 ---
is_drowsy = False            # 졸음 모드 진입 플래그
frozen_threshold = None      # 졸음 진입 시점의 close_thr 보존
recovery_counter = 0         # 복귀 판정용 연속 눈뜸 카운터

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

                if not is_drowsy:
                    # ───── 정상 모드: history 누적 + 동적 threshold ─────
                    ear_history.append(avg_ear)          # 정상일 때만 누적 (오염 방지)
                    if len(ear_history) > 50:
                        ear_max = np.percentile(ear_history, 90)
                        current_threshold = ear_max

                    close_thr = current_threshold * EAR_RATIO
                    open_thr = current_threshold * EAR_OPEN_RATIO

                    if avg_ear < close_thr:
                        if eye_closed_start_time is None:
                            eye_closed_start_time = curr_time
                            driver_state = 1
                        else:
                            if (curr_time - eye_closed_start_time) >= DROWSINESS_TIME:
                                driver_state = 2
                                # 졸음 모드 진입: threshold 동결
                                is_drowsy = True
                                frozen_threshold = close_thr
                                recovery_counter = 0

                    elif avg_ear > open_thr:
                        eye_closed_start_time = None
                        driver_state = 0

                else:
                    # ───── 졸음 모드: history 중단 + frozen threshold ─────
                    # ear_history.append() 하지 않음 - 감긴 눈 EAR로 캘리브 오염 방지
                    thr = frozen_threshold if frozen_threshold is not None else FIXED_THRESHOLD

                    if avg_ear > thr:
                        recovery_counter += 1
                    else:
                        recovery_counter = 0

                    if recovery_counter >= RECOVERY_FRAMES:
                        # 복귀: 동결 해제, 정상 모드로
                        is_drowsy = False
                        frozen_threshold = None
                        eye_closed_start_time = None
                        recovery_counter = 0
                        driver_state = 0
                    else:
                        driver_state = 2     # 아직 졸음 유지

        else:
            # 졸음 모드 중 얼굴 미검출 = 고개 떨굼 가능성 -> 상태 유지가 안전
            if not is_drowsy:
                eye_closed_start_time = None
                driver_state = 0
            # is_drowsy면 driver_state=2 유지 (안전 우선)

        # -------------------------------------------------
        # UART 송신 (100ms 주기)
        # -------------------------------------------------
        if curr_time - last_send_time >= SEND_INTERVAL:
            seq = (seq + 1) % 256
            ear_int = int(avg_ear * 100)        # EAR×100 (옵션B)
            if ear_int > 255:
                ear_int = 255

            checksum = (0xAA + driver_state + ear_int + seq) & 0xFF
            tx_frame = bytes([0xAA, driver_state, ear_int, seq, checksum])
            ser.write(tx_frame)
            last_send_time = curr_time

        mode_str = "DROWSY-LOCK" if is_drowsy else "NORMAL-CAL"
        sys.stdout.write(
            f"\r[DMS] FPS: {fps:4.1f} | EAR: {avg_ear:.3f} (Thr:{current_threshold:.3f}|{mode_str}) "
            f"| STATE: {STATE_STR[driver_state]:18s} | Seq: {seq:3d} "
        )
        sys.stdout.flush()

except KeyboardInterrupt:
    print("\n정상 종료합니다.")
finally:
    picam2.stop()
    ser.close()
