import time
import numpy as np
from ultralytics import YOLO
from hailo_platform import (HEF, VDevice, HailoStreamInterface, 
                            InferVStreams, ConfigureParams, 
                            InputVStreamParams, OutputVStreamParams, FormatType)

ONNX_PATH = "../models/yolov8_face.onnx"
HEF_PATH = "../models/yolov8_face_zoo.hef"
ITERATIONS = 100

print("-" * 50)
print("1. YOLOv8 ONNX (CPU) 벤치마크 시작...")
print("-" * 50)
# CPU 모드로 YOLO 로드
detector = YOLO(ONNX_PATH, task="detect")
# 320x320 더미 이미지 생성 (RGB)
dummy_img_onnx = np.zeros((320, 320, 3), dtype=np.uint8)

# 워밍업 (초기 로딩 시간 배제)
for _ in range(5):
    detector.predict(source=dummy_img_onnx, imgsz=320, verbose=False, device='cpu')

start_time = time.time()
for _ in range(ITERATIONS):
    detector.predict(source=dummy_img_onnx, imgsz=320, verbose=False, device='cpu')
onnx_time_sec = (time.time() - start_time) / ITERATIONS
onnx_ms = onnx_time_sec * 1000
onnx_fps = 1.0 / onnx_time_sec

print(f"> CPU 추론 시간: {onnx_ms:.2f} ms")
print(f"> CPU 최대 처리량: {onnx_fps:.1f} FPS\n")


print("-" * 50)
print("2. YOLOv8 HEF (NPU) 벤치마크 시작...")
print("-" * 50)
hef = HEF(HEF_PATH)
device = VDevice()
cfg = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
ng = device.configure(hef, cfg)[0]
ngp = ng.create_params()

ii = hef.get_input_vstream_infos()[0]
# 입력 포맷을 FLOAT32 또는 UINT8로 설정 (모델 컴파일 설정에 따라 다름, 보통 UINT8이 빠름)
ivp = InputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.UINT8)
ovp = OutputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)

# HEF 모델이 요구하는 정확한 입력 shape 추출 (예: 1, 640, 640, 3)
input_shape = ii.shape
print(f"[디버그] NPU 요구 입력 Shape: {input_shape}")

dummy_img_hef = np.zeros(input_shape, dtype=np.uint8)
dummy_img_hef_batched = np.expand_dims(dummy_img_hef, axis=0)

with InferVStreams(ng, ivp, ovp) as pipeline:
    with ng.activate(ngp):
        # 워밍업
        for _ in range(5):
            pipeline.infer({ii.name: dummy_img_hef_batched})
            
        start_time = time.time()
        for _ in range(ITERATIONS):
            pipeline.infer({ii.name: dummy_img_hef_batched})
        hef_time_sec = (time.time() - start_time) / ITERATIONS
        hef_ms = hef_time_sec * 1000
        hef_fps = 1.0 / hef_time_sec

print(f"> NPU 추론 시간: {hef_ms:.2f} ms")
print(f"> NPU 최대 처리량: {hef_fps:.1f} FPS")
print("-" * 50)

# 최종 요약
speedup = onnx_ms / hef_ms
print(f"결론: Hailo-8 NPU가 RPi5 CPU보다 약 {speedup:.1f}배 더 빠릅니다.")
