#raspi code
                                                                                                                                                                                                                                                                                                                                                                                                                                                                      app.py                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 import subprocess
from flask import Flask, render_template_string
from flask_sock import Sock

app = Flask(_name_)
sock = Sock(app)

# -----------------------------
# WebSocket Camera Stream
# -----------------------------
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
# Home Page (simple HTML)
# -----------------------------
@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Camera Stream</title>
    </head>
    <body>
      <h2>Live Camera</h2>
      <img id="video" width="320" height="240" />
      <script>
        const img = document.getElementById("video");
        const ws = new WebSocket(
          (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/camera"
        );
        ws.onmessage = (event) => {
          const blob = new Blob([event.data], { type: "image/jpeg" });
          img.src = URL.createObjectURL(blob);
        };
      </script>
    </body>
    </html>
    """)


if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000, debug=True)