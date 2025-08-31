""Raspberry Pi camera streaming with client-side (browser) MediaPipe object detection.

Architecture change (lightweight Pi):
  - Pi only captures frames (ffmpeg -> MJPEG) and pushes over a single WebSocket /ws/camera.
  - Browser receives raw JPEG frames, displays them, and runs MediaPipe Tasks (WASM) locally
    for object detection, drawing bounding boxes on a separate canvas.

Advantages:
  - Offloads ML inference from Pi CPU/GPU to the viewer's device.
  - Keeps stream latency low (only encoding + network).

This file therefore has NO runtime dependency on mediapipe / opencv; detection is entirely client-side.
"""

import os
import subprocess
import threading
from typing import Optional, Set

from flask import Flask, render_template_string
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# -----------------------------
# Globals / State
# -----------------------------
RAW_CLIENTS: Set = set()
CLIENTS_LOCK = threading.Lock()
FRAME_THREAD: Optional[threading.Thread] = None
STOP_EVENT = threading.Event()



@sock.route('/ws/camera')
def camera_stream(ws):
    ffmpeg_cmd = [
        'ffmpeg',
        '-f', 'v4l2',
        '-i', '/dev/video0',
        '-vf', 'scale=320:240',
        '-q:v', '5',
        '-f', 'mjpeg',
        'pipe:1'
    ]
    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE)

    try:
        while True:
            data = b''
            while True:
                byte = process.stdout.read(1)
                if not byte:
                    break
                data += byte
                if data[-2:] == b'\xff\xd9':  # JPEG frame end
                    break
            if data:
                ws.send(data)
            else:
                break
    finally:
        process.terminate()


# -----------------------------
# Home Page
# -----------------------------
@app.route('/')
def index():
    return render_template_string(
        """
<!DOCTYPE html>
<html>
  <head>
    <title>Camera Stream with Client-Side Detection</title>
  <style>
    body { font-family: Arial, sans-serif; }
      .row { display: flex; gap: 30px; }
      figure { text-align: center; }
      img, canvas { border: 1px solid #444; }
      #status { margin-top: 10px; font-size: 0.9rem; color: #555; }
  </style>
  </head>
  <body>
    <h2>Live Camera + Client-Side MediaPipe Object Detection</h2>
  <div class="row">
    <figure>
    <img id="raw" width="320" height="240" alt="Raw stream" />
    <figcaption>Raw</figcaption>
    </figure>
    <figure>
        <canvas id="processed" width="320" height="240"></canvas>
        <figcaption>Detected Objects (Browser)</figcaption>
    </figure>
  </div>
  <p id="status">Connecting...</p>
    <script type="module">
      // Load MediaPipe Tasks for vision
      import { FilesetResolver, ObjectDetector } from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3";

      const statusEl = document.getElementById('status');
      const rawImg = document.getElementById('raw');
      const canvas = document.getElementById('processed');
      const ctx = canvas.getContext('2d');

      let detector = null;
      let processing = false;
      let lastFrameBlobUrl = null;

      async function initDetector() {
        try {
          statusEl.textContent = 'Loading detector...';
          const vision = await FilesetResolver.forVisionTasks(
            'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm'
          );
          detector = await ObjectDetector.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite'
            },
            scoreThreshold: 0.45,
            maxResults: 5
          });
          statusEl.textContent = 'Detector ready. Connecting stream...';
          connectStream();
        } catch (e) {
          console.error(e);
          statusEl.textContent = 'Failed to load detector; showing raw only.';
          connectStream();
        }
      }

      function connectStream() {
        const proto = (location.protocol === 'https:') ? 'wss://' : 'ws://';
        const ws = new WebSocket(proto + location.host + '/ws/camera');
        ws.binaryType = 'arraybuffer';
        ws.onopen = () => { statusEl.textContent = 'Streaming'; };
        ws.onmessage = async (ev) => {
          const blob = new Blob([ev.data], { type: 'image/jpeg' });
          if (lastFrameBlobUrl) URL.revokeObjectURL(lastFrameBlobUrl);
            const url = URL.createObjectURL(blob);
          lastFrameBlobUrl = url;
          rawImg.onload = () => {
            if (!processing) {
              requestAnimationFrame(runDetection);
            }
          };
          rawImg.src = url;
        };
        ws.onclose = () => {
          statusEl.textContent = 'Disconnected - retrying...';
          setTimeout(connectStream, 1500);
        };
      }

      async function runDetection() {
        if (!detector || processing || rawImg.naturalWidth === 0) return;
        processing = true;
        try {
          canvas.width = rawImg.naturalWidth;
          canvas.height = rawImg.naturalHeight;
          ctx.drawImage(rawImg, 0, 0, canvas.width, canvas.height);
          const result = await detector.detect(rawImg);
          if (result && result.detections) {
            ctx.lineWidth = 2;
            ctx.font = '14px Arial';
            for (const det of result.detections) {
              const bbox = det.boundingBox; // xMin, yMin, width, height
              const x = bbox.originX;
              const y = bbox.originY;
              const w = bbox.width;
              const h = bbox.height;
              ctx.strokeStyle = '#00FF55';
              ctx.fillStyle = 'rgba(0,255,85,0.15)';
              ctx.strokeRect(x, y, w, h);
              ctx.fillRect(x, y, w, h);
              if (det.categories && det.categories.length) {
                const cat = det.categories[0];
                const label = `${cat.categoryName || 'obj'} ${(cat.score || 0).toFixed(2)}`;
                const tw = ctx.measureText(label).width + 8;
                const th = 18;
                ctx.fillStyle = '#00FF55';
                ctx.fillRect(x, y - th < 0 ? y : y - th, tw, th);
                ctx.fillStyle = '#000';
                ctx.fillText(label, x + 4, y - th/2 + 5 < 10 ? y + 14 : y - 4);
              }
            }
          }
        } catch (e) {
          // Swallow any detection errors.
        } finally {
          processing = false;
        }
      }

      initDetector();
    </script>
  </body>
</html>
    """
  )


@app.route('/health')
def health():  # simple health check
  return {"status": "ok", "raw_clients": len(RAW_CLIENTS)}
 


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5002, debug=True)