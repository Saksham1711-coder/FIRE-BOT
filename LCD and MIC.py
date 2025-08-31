#The LCD and MIC Code
#!/usr/bin/env python3

from flask import Flask, Response, render_template_string, request, redirect, url_for
import subprocess
import threading
import time
import queue

# LCD imports
try:
    from RPLCD.i2c import CharLCD
    LCD_AVAILABLE = True
    print("✅ LCD library imported successfully")
except ImportError:
    LCD_AVAILABLE = False
    print("⚠ LCD library not available")

app = Flask(_name_)

# Initialize LCD
if LCD_AVAILABLE:
    try:
        lcd = CharLCD('PCF8574', 0x27)
        lcd.clear()
        lcd.write_string('Audio Server\nStarting...')
        print("✅ LCD initialized")
    except Exception as e:
        print(f"❌ LCD initialization failed: {e}")
        lcd = None
else:
    lcd = None

# Audio configuration
SAMPLE_RATE = 44100
CHANNELS = 1
DEVICE = 'plughw:0,0'  # Your mic is on card 0
CHUNK_SIZE = 4096

# Global audio queue
audio_queue = queue.Queue(maxsize=50)
recording_process = None

def audio_capture():
    """Capture audio using arecord"""
    global recording_process
    
    cmd = [
        'arecord',
        '-D', DEVICE,
        '-c', str(CHANNELS),
        '-r', str(SAMPLE_RATE),
        '-f', 'S16_LE',
        '-t', 'raw'
    ]
    
    try:
        recording_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"✅ Started audio capture from {DEVICE}")
        
        if lcd:
            lcd.clear()
            lcd.write_string('Audio Server\nStreaming...')
        
        while recording_process and recording_process.poll() is None:
            data = recording_process.stdout.read(CHUNK_SIZE)
            if data:
                try:
                    if audio_queue.full():
                        try:
                            audio_queue.get_nowait()
                        except queue.Empty:
                            pass
                    audio_queue.put(data, block=False)
                except queue.Full:
                    pass
            else:
                time.sleep(0.01)
                
    except Exception as e:
        print(f"❌ Error in audio capture: {e}")
    finally:
        if recording_process:
            recording_process.terminate()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        text = request.form.get('lcd_text', '')
        if lcd and text:
            lcd.clear()
            # Handle text longer than 16 chars (split to 2 lines)
            if len(text) <= 16:
                lcd.write_string(text)
            else:
                line1 = text[:16]
                line2 = text[16:32]
                lcd.write_string(f"{line1}\n{line2}")
            print(f"📺 LCD Display: {text}")
        return redirect(url_for('index'))

    # HTML page with audio player and LCD control
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Audio Stream + LCD Control</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial; text-align: center; padding: 20px; background-color: #f0f0f0; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .section { margin: 30px 0; padding: 20px; border: 2px solid #ddd; border-radius: 8px; }
            .audio-section { border-color: #007bff; background: #f8f9ff; }
            .lcd-section { border-color: #28a745; background: #f8fff8; }
            audio { width: 100%; margin: 15px 0; }
            button { background: #007bff; color: white; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }
            button:hover { background: #0056b3; }
            .lcd-btn { background: #28a745; }
            .lcd-btn:hover { background: #1e7e34; }
            input[type="text"] { width: 100%; padding: 10px; margin: 10px 0; border: 2px solid #ddd; border-radius: 5px; font-size: 16px; box-sizing: border-box; }
            .quick-btns { margin: 15px 0; }
            .quick-btns button { background: #6c757d; font-size: 12px; padding: 8px 12px; margin: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎤 Live Audio Stream + 📺 LCD Control</h1>
            
            <div class="section audio-section">
                <h2>🔊 Live Audio Stream</h2>
                <audio controls autoplay>
                    <source src="/audio" type="audio/wav">
                    Your browser does not support audio streaming.
                </audio>
                <p><small>Click play if audio doesn't start automatically</small></p>
            </div>
            
            <div class="section lcd-section">
                <h2>📺 LCD Display Control</h2>
                
                <form method="post">
                    <input type="text" name="lcd_text" placeholder="Enter text for LCD (max 32 chars)" maxlength="32" required>
                    <br>
                    <button type="submit" class="lcd-btn">📺 Send to LCD</button>
                </form>
                
                <div class="quick-btns">
                    <p><strong>Quick Messages:</strong></p>
                    <button onclick="sendQuick('Hello World!')">Hello World!</button>
                    <button onclick="sendQuick('Welcome!')">Welcome!</button>
                    <button onclick="sendQuick('Raspberry Pi Audio')">Pi Audio</button>
                    <button onclick="sendQuick('System Ready')">System Ready</button>
                    <button onclick="sendQuick('Listening...')">Listening...</button>
                </div>
                
                <button onclick="clearLCD()" class="lcd-btn">🗑 Clear LCD</button>
                <button onclick="showTime()" class="lcd-btn">🕐 Show Time</button>
            </div>
        </div>

        <script>
            function sendQuick(message) {
                document.querySelector('input[name="lcd_text"]').value = message;
                document.querySelector('form').submit();
            }
            
            function clearLCD() {
                fetch('/clear_lcd', {method: 'POST'})
                    .then(() => location.reload());
            }
            
            function showTime() {
                fetch('/show_time', {method: 'POST'})
                    .then(() => location.reload());
            }
            
            // Auto-restart audio if it stops
            const audio = document.querySelector('audio');
            audio.addEventListener('ended', function() {
                setTimeout(() => {
                    audio.load();
                    audio.play();
                }, 1000);
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/audio')
def audio():
    """Stream audio data as WAV format"""
    def generate_wav():
        import struct
        
        # WAV header
        header = b'RIFF'
        header += struct.pack('<I', 0xFFFFFFFF)
        header += b'WAVE'
        header += b'fmt '
        header += struct.pack('<I', 16)
        header += struct.pack('<H', 1)
        header += struct.pack('<H', CHANNELS)
        header += struct.pack('<I', SAMPLE_RATE)
        header += struct.pack('<I', SAMPLE_RATE * CHANNELS * 2)
        header += struct.pack('<H', CHANNELS * 2)
        header += struct.pack('<H', 16)
        header += b'data'
        header += struct.pack('<I', 0xFFFFFFFF)
        
        yield header
        
        # Stream audio data
        while True:
            try:
                data = audio_queue.get(timeout=2.0)
                yield data
            except queue.Empty:
                yield b'\x00' * CHUNK_SIZE

    return Response(generate_wav(), mimetype='audio/wav', headers={'Cache-Control': 'no-cache'})

@app.route('/clear_lcd', methods=['POST'])
def clear_lcd():
    """Clear LCD display"""
    if lcd:
        lcd.clear()
        print("📺 LCD cleared")
    return "OK"

@app.route('/show_time', methods=['POST'])
def show_time():
    """Show current time on LCD"""
    if lcd:
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S\n%d/%m/%Y")
        lcd.clear()
        lcd.write_string(time_str)
        print(f"📺 LCD Display: {time_str}")
    return "OK"

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

if _name_ == '_main_':
    # Test microphone first
    print("🎤 Testing microphone...")
    test_cmd = ['arecord', '-D', DEVICE, '-c', str(CHANNELS), '-r', str(SAMPLE_RATE), '-f', 'S16_LE', '-d', '2', '/tmp/test.wav']
    try:
        result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Microphone test PASSED")
        else:
            print(f"❌ Microphone test FAILED: {result.stderr}")
            exit(1)
    except Exception as e:
        print(f"❌ Microphone test ERROR: {e}")
        exit(1)
    
    # Start audio capture thread
    audio_thread = threading.Thread(target=audio_capture, daemon=True)
    audio_thread.start()
    time.sleep(2)
    
    local_ip = get_local_ip()
    print("="*50)
    print("🎤 LIVE AUDIO + LCD SERVER READY!")
    print("="*50)
    print(f"📱 Local:   http://localhost:5000")
    print(f"🌐 Network: http://{local_ip}:5000")
    print("="*50)
    
    app.run(host='0.0.0.0', port=5000, threaded=True)