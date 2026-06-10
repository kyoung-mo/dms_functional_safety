import argparse
import subprocess
import os

parser = argparse.ArgumentParser()
parser.add_argument('--id', required=True, help='촬영자 ID (예: kym)')
args = parser.parse_args()

save_dir = "./dark"
os.makedirs(save_dir, exist_ok=True)

# 1단계: open 20장
print(f"[open] 촬영 시작 - {args.id}_open000.jpg ~")
subprocess.run([
    "rpicam-still",
    "--timelapse", "100",
    "--timeout", "10000",
    "--nopreview",
    "-o", f"{save_dir}/{args.id}_open%03d.jpg"
])
print("[open] 완료")

# N 입력 대기
while True:
    key = input("\nclosed 촬영 시작하려면 N 입력: ").strip().upper()
    if key == "N":
        break

# 2단계: closed 20장
print(f"[closed] 촬영 시작 - {args.id}_close000.jpg ~")
subprocess.run([
    "rpicam-still",
    "--timelapse", "100",
    "--timeout", "10000",
    "--nopreview",
    "-o", f"{save_dir}/{args.id}_close%03d.jpg"
])
print("[closed] 완료")
print(f"\n전체 완료: {save_dir}/")
