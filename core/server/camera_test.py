"""
Camera Diagnostic & Auto-Detection Tool
Scans all connected camera indices (0 to 4) and displays live test windows.
"""

import cv2
import time

print("="*50)
print("🔍 Scanning available camera indices...")
print("="*50)

available_cameras = []

for index in range(5):
    # Try DirectShow first on Windows
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
        
    if cap.isOpened():
        ret, frame = cap.read()
        if ret and frame is not None:
            mean_val = frame.mean()
            h, w = frame.shape[:2]
            print(f"✅ Camera Index {index}: Detected ({w}x{h}) | Brightness/Mean: {mean_val:.1f}")
            available_cameras.append(index)
        else:
            print(f"⚠️ Camera Index {index}: Opened, but could not read frame (Black/Inactive)")
        cap.release()
    else:
        # Not connected
        pass

print("\n" + "="*50)
if not available_cameras:
    print("❌ No active camera streams found. Check USB / HDMI connections.")
    exit()

print(f"Available active cameras: {available_cameras}")
test_idx = available_cameras[0] if len(available_cameras) == 1 else (1 if 1 in available_cameras else available_cameras[0])
print(f"Testing Camera Index: {test_idx} (Press 'q' in video window to exit)")
print("="*50)

cap = cv2.VideoCapture(test_idx, cv2.CAP_DSHOW)
if not cap.isOpened():
    cap = cv2.VideoCapture(test_idx)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Dropped frame...")
        time.sleep(0.1)
        continue

    cv2.putText(frame, f"Camera Index: {test_idx} (Press Q to quit)", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    cv2.imshow(f"Camera Test [Index {test_idx}]", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()