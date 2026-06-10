"""face_landmarks_lite.hef 입출력 형식 확인"""
from hailo_platform import HEF

hef = HEF("../models/face_landmarks_lite.hef")

print("=== 입력 ===")
for info in hef.get_input_vstream_infos():
    print(f"  name: {info.name}")
    print(f"  shape: {info.shape}")

print("=== 출력 ===")
for info in hef.get_output_vstream_infos():
    print(f"  name: {info.name}")
    print(f"  shape: {info.shape}")
