"""face_landmarks_lite 468점을 이미지에 찍어서 시각 검증"""
import numpy as np
import cv2
from pathlib import Path
from hailo_platform import (HEF, VDevice, HailoStreamInterface,
                            InferVStreams, ConfigureParams,
                            InputVStreamParams, OutputVStreamParams, FormatType)

HEF_PATH = Path(__file__).resolve().parent.parent / "models" / "face_landmarks_lite.hef"
IMG_PATH = "/home/pi/project/face-security-system/data/test.jpg"
OUT_PATH = "/home/pi/project/dms/rpi5/inference/landmarks_result.jpg"

# 이미지 준비 (192x192)
frame = cv2.imread(IMG_PATH)
img192 = cv2.resize(frame, (192, 192))
img_rgb = cv2.cvtColor(img192, cv2.COLOR_BGR2RGB)
inp = np.expand_dims(img_rgb.astype(np.float32), 0)

# 추론
hef = HEF(str(HEF_PATH))
with VDevice() as devices:
    cfg = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
    ng = devices.configure(hef, cfg)[0]
    ngp = ng.create_params()
    ii = hef.get_input_vstream_infos()[0]
    ivp = InputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)
    ovp = OutputVStreamParams.make_from_network_group(ng, quantized=False, format_type=FormatType.FLOAT32)
    with InferVStreams(ng, ivp, ovp) as pipeline:
        with ng.activate(ngp):
            out = pipeline.infer({ii.name: inp})

# 468점 추출 (1404 → 468 x 3)
lm = out["face_landmarks_lite/conv22"][0].flatten().reshape(468, 3)

# 192 이미지에 점 찍기
canvas = img192.copy()
for (x, y, z) in lm:
    px, py = int(x), int(y)
    if 0 <= px < 192 and 0 <= py < 192:
        cv2.circle(canvas, (px, py), 1, (0, 255, 0), -1)

# 보기 좋게 크게 저장 (4배 확대)
canvas = cv2.resize(canvas, (768, 768), interpolation=cv2.INTER_NEAREST)
cv2.imwrite(OUT_PATH, canvas)
print(f"저장: {OUT_PATH}")
print(f"점 개수: {len(lm)}")
