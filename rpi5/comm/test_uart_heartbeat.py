"""UART Heartbeat 송신 테스트 (100ms 주기)
RPi5 → USB-시리얼 어댑터 → PC(MobaXterm COM5)로 송신 확인용.
검증용이라 사람이 읽기 쉬운 텍스트로 송신 (STM32 연동 시 바이너리 프레임으로 교체)
"""
import serial
import time

ser = serial.Serial("/dev/serial0", 115200, timeout=1)
seq = 0
print("Heartbeat 송신 시작 (100ms 주기, 종료 Ctrl+C)")
try:
    while True:
        seq = (seq + 1) % 256
        status = 0
        ear = 25
        msg = f"HB Seq={seq} Status={status} EAR={ear}\r\n"
        ser.write(msg.encode())
        print(f"송신: {msg.strip()}")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n종료")
finally:
    ser.close()
