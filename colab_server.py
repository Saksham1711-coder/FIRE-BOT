import asyncio
import websockets
import cv2
import numpy as np
import threading
import base64
from ultralytics import YOLO
from flask import Flask, render_template

# Flask app
app = Flask(__name__)

# Load YOLO model
model = YOLO("YOLOv8-Fire-and-Smoke-Detection.pt")

# RasPi WebSocket URL (update if tunnel changes)
RASPI_WS_URL = "ws://entrance-determination-gpl-acknowledged.trycloudflare.com/ws/camera"

# Connected browser clients
connected_viewers = set()

# Process and forward frames
async def receive_frames():
    async with websockets.connect(RASPI_WS_URL) as ws:
        while True:
            try:
                data = await ws.recv()
                np_data = np.frombuffer(data, dtype=np.uint8)
                frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

                # YOLO inference
                results = model.predict(frame, imgsz=320, conf=0.4, verbose=False)
                annotated = results[0].plot()

                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', annotated)
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')

                # Send to all connected viewers
                if connected_viewers:
                    await asyncio.gather(*[viewer.send(jpg_as_text) for viewer in connected_viewers])

                await asyncio.sleep(0.05)  # ~20 FPS
            except Exception as e:
                print("Error receiving frames:", e)
                break

# WebSocket server for browser viewers
async def viewer_ws(websocket):
    connected_viewers.add(websocket)
    try:
        async for _ in websocket:
            pass  # no need to handle incoming messages
    finally:
        connected_viewers.remove(websocket)

async def viewer_server():
    async with websockets.serve(viewer_ws, "0.0.0.0", 8766):
        await asyncio.Future()  # run forever

def start_asyncio_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(asyncio.gather(receive_frames(), viewer_server()))

@app.route('/')
def index():
    return render_template("index.html")

if __name__ == "__main__":
    threading.Thread(target=start_asyncio_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
