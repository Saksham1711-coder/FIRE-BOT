#!/usr/bin/env python3
"""
Real RPLidar A1 Web SLAM - Complete Working Version
Serves a live 2D occupancy map at http://localhost:5000
"""

import numpy as np
import time
import threading
import base64
import io
import serial
import math
from PIL import Image
from flask import Flask, jsonify

class RPLidarSLAM:
    def _init_(self, port='/dev/ttyUSB0'):
        # Map configuration
        self.MAP_SIZE = 600
        self.MAP_METERS = 20.0
        self.PIXELS_PER_METER = self.MAP_SIZE / self.MAP_METERS

        # Robot in center of the map
        self.robot_x = self.MAP_SIZE // 2
        self.robot_y = self.MAP_SIZE // 2

        # Occupancy map: 50=unknown, 127=free, 255=occupied
        self.map_data = np.full((self.MAP_SIZE, self.MAP_SIZE), 50, dtype=np.uint8)

        # Stats
        self.scan_count = 0
        self.total_points = 0
        self.running = False

        # Serial
        self.port = port
        self.serial_conn = None

        # Thread
        self.thread = None

    def connect_lidar(self):
        """Open serial and start RPLidar scanning."""
        try:
            print(f"🔄 Connecting to RPLidar on {self.port}...")
            self.serial_conn = serial.Serial(self.port, 115200, timeout=1)
            time.sleep(2)

            # Stop any ongoing scan
            self.serial_conn.write(b'\xA5\x25')
            time.sleep(0.5)

            # Reset
            self.serial_conn.write(b'\xA5\x40')
            time.sleep(2)

            # Clear buffer
            self.serial_conn.reset_input_buffer()

            # Start scan
            self.serial_conn.write(b'\xA5\x20')
            time.sleep(1)

            print("✅ RPLidar connected and scanning")
            return True

        except Exception as e:
            print(f"❌ RPLidar connection failed: {e}")
            return False

    def read_scan_data(self):
        """Read and parse data from RPLidar (simple 5-byte node parser)."""
        if not self.serial_conn:
            return []

        scan_points = []
        try:
            if self.serial_conn.in_waiting > 10:
                data = self.serial_conn.read(min(self.serial_conn.in_waiting, 1000))

                i = 0
                # Each node is 5 bytes: check start bit on first byte
                while i < len(data) - 4:
                    b0 = data[i]
                    if b0 & 0x01:
                        try:
                            quality = (b0 >> 2) & 0x3F
                            angle_raw = (data[i+1] | (data[i+2] << 8)) >> 1  # Q6
                            distance_raw = (data[i+3] | (data[i+4] << 8))    # Q2

                            angle = (angle_raw / 64.0) % 360.0
                            distance = distance_raw / 4.0  # mm

                            if 100 < distance < 8000 and quality > 0:
                                scan_points.append((angle, distance))
                            i += 5
                        except Exception:
                            i += 1
                    else:
                        i += 1
        except Exception as e:
            print(f"⚠ Read error: {e}")

        return scan_points

    def mark_free_line(self, x0, y0, x1, y1):
        """Bresenham-like ray marking unknown cells as free (127)."""
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0
        steps = 0
        while steps < 1000:
            if 0 <= x < self.MAP_SIZE and 0 <= y < self.MAP_SIZE:
                if self.map_data[y, x] == 50:  # unknown only
                    self.map_data[y, x] = 127  # free

            if x == x1 and y == y1:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
            steps += 1

    def update_map(self, scan_points):
        """Project points to the map and update occupancy."""
        for angle, distance in scan_points:
            # Convert to map coordinates
            angle_rad = math.radians(angle)
            distance_m = distance / 1000.0

            x = self.robot_x + (distance_m * self.PIXELS_PER_METER * math.cos(angle_rad))
            y = self.robot_y + (distance_m * self.PIXELS_PER_METER * math.sin(angle_rad))

            x = int(np.clip(x, 0, self.MAP_SIZE - 1))
            y = int(np.clip(y, 0, self.MAP_SIZE - 1))

            # Mark obstacle cell
            self.map_data[y, x] = 255

            # Mark free space along the ray
            self.mark_free_line(self.robot_x, self.robot_y, x, y)

    def get_map_image(self):
        """Return RGB image array for current map."""
        map_rgb = np.zeros((self.MAP_SIZE, self.MAP_SIZE, 3), dtype=np.uint8)
        map_rgb[self.map_data == 50] = [50, 50, 50]       # unknown -> dark gray
        map_rgb[self.map_data == 127] = [200, 200, 200]   # free -> light gray
        map_rgb[self.map_data == 255] = [255, 255, 255]   # occupied -> white

        # Draw robot as a red circle
        r = 8
        y0 = max(0, self.robot_y - r)
        y1 = min(self.MAP_SIZE, self.robot_y + r)
        x0 = max(0, self.robot_x - r)
        x1 = min(self.MAP_SIZE, self.robot_x + r)
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                if (xx - self.robot_x) ** 2 + (yy - self.robot_y) ** 2 <= r * r:
                    map_rgb[yy, xx] = [255, 0, 0]

        return map_rgb

    def slam_loop(self):
        """Main loop: connect lidar, read points, update map."""
        if not self.connect_lidar():
            print("❌ Could not connect to lidar; SLAM not started.")
            return

        self.running = True
        print("🔄 SLAM loop started")

        try:
            while self.running:
                points = self.read_scan_data()
                if points:
                    self.update_map(points)
                    self.scan_count += 1
                    self.total_points += len(points)

                    if self.scan_count % 20 == 0:
                        print(f"📡 Scans: {self.scan_count} | Points: {self.total_points}")

                time.sleep(0.05)  # ~20 Hz loop
        except Exception as e:
            print(f"💥 SLAM loop error: {e}")
        finally:
            # Stop scan and close port
            try:
                if self.serial_conn:
                    self.serial_conn.write(b'\xA5\x25')
            except Exception:
                pass
            try:
                if self.serial_conn:
                    self.serial_conn.close()
            except Exception:
                pass
            print("🛑 SLAM loop stopped")

    def start(self):
        """Start SLAM loop in a background thread."""
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.slam_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop SLAM loop."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)


# Flask app
app = Flask(_name_)
slam = RPLidarSLAM('/dev/ttyUSB0')


@app.route('/')
def index():
    # Simple HTML page that fetches map data
    return '''
<!DOCTYPE html>
<html>
<head>
  <title>RPLidar SLAM</title>
  <style>
    body { font-family: Arial; background: #f0f0f0; text-align: center; padding: 20px; }
    .wrap { max-width: 820px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 10px; }
    #map { border: 3px solid #333; border-radius: 10px; }
    .stats { display: flex; justify-content: space-around; margin: 15px 0; }
    .stat { background: #007bff; color: #fff; padding: 10px 15px; border-radius: 8px; }
    .legend { display: flex; justify-content: center; gap: 12px; margin: 12px 0; }
    .box { display: inline-flex; align-items: center; gap: 6px; background:#f8f9fa; padding:6px 10px; border-radius: 6px; }
    .color { width:18px; height:18px; border:1px solid #333; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>🤖 RPLidar A1 Real-Time SLAM</h1>
    <div class="legend">
      <div class="box"><div class="color" style="background:#323232;"></div>Unknown</div>
      <div class="box"><div class="color" style="background:#c8c8c8;"></div>Free</div>
      <div class="box"><div class="color" style="background:#ffffff;"></div>Obstacle</div>
      <div class="box"><div class="color" style="background:#ff0000;"></div>Robot</div>
    </div>
    <img id="map" src="" width="600" height="600" alt="Map">
    <div class="stats">
      <div class="stat">Scans: <span id="scans">0</span></div>
      <div class="stat">Points: <span id="points">0</span></div>
    </div>
  </div>

  <script>
    function update() {
      fetch('/map_data').then(r => r.json()).then(d => {
        if (d.image) {
          document.getElementById('map').src = 'data:image/png;base64,' + d.image;
          document.getElementById('scans').textContent = d.scan_count;
          document.getElementById('points').textContent = d.total_points;
        }
      }).catch(_ => {});
    }
    setInterval(update, 500);
    update();
  </script>
</body>
</html>
    '''


@app.route('/map_data')
def map_data():
    try:
        # Build image
        img_arr = slam.get_map_image()
        img = Image.fromarray(img_arr)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({
            'image': img_b64,
            'scan_count': slam.scan_count,
            'total_points': slam.total_points,
            'running': slam.running
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/clear_map', methods=['POST'])
def clear_map():
    slam.map_data.fill(50)
    slam.scan_count = 0
    slam.total_points = 0
    return jsonify({'success': True})


def main():
    print("🌐 Starting RPLidar Web SLAM server...")
    # Start SLAM
    slam.start()
    # Start web server
    print("📱 Open your browser: http://localhost:5000")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        slam.stop()
        print("✅ Shutdown complete")


if _name_ == '_main_':
    main()