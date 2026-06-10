"""face_landmarks_lite.hef 추론 + 출력값 범위 확인"""
import numpy as np
import cv2
from pathlib import Path
from hailo_platform import (HEF, VDevice, HailoStreamInterface,
                            InferVStreams, ConfigureParams,
                            InputVStreamParams, OutputVStreamParams, FormatType)

HEF_PATH = Path(__file__).resolve().parent.parent / "models" / "face_landmarks_lite.hef"
IMG_PATH = "/home/pi/project/face-security-system/data/test.jpg"

# 1. 이미지 준비 (192x192, 0~255 그대로 - 정규화는 HEF 내장)
frame = cv2.imread(IMG_PATH)
print(f"원본 이미지: {frame.shape}")
img = cv2.resize(frame, (192, 192))
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
inp = img_rgb.astype(np.float32)          # /255 안 함! (정규화 내장)
inp = np.expand_dims(inp, 0)              # (1, 192, 192, 3)

# 2. HEF 로드 및 추론
hef = HEF(str(HEF_PATH))
devices = VDevice()
cfg = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
ng = devices.configure(hef, cfg)[0]
ngp = ng.create_params()

ii = hef.get_input_vstream_infos()[0]
ivp = InputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)
ovp = OutputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)

with InferVStreams(ng, ivp, ovp) as pipeline:
    with ng.activate(ngp):
        out = pipeline.infer({ii.name: inp})

# 3. 출력 분석
print("\n=== 출력 키 ===")
for k, v in out.items():
    print(f"  {k}: shape={v.shape}")

# 랜드마크 (conv22) — 1404 = 468x3
landmarks = out["face_landmarks_lite/conv22"][0].flatten()
print(f"\n=== 랜드마크 (conv22) ===")
print(f"  총 개수: {landmarks.shape}")
print(f"  값 범위: min={landmarks.min():.3f}, max={landmarks.max():.3f}")
print(f"  앞 9개 값(점3개 xyz): {landmarks[:9]}")

# confidence (conv25)
conf = out["face_landmarks_lite/conv25"][0].flatten()
print(f"\n=== confidence (conv25) ===")
print(f"  값: {conf}  (sigmoid 내장이라 0~1 범위여야 정상)")
