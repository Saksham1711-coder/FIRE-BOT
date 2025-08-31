# Raspberry Pi Audio and Camera Streaming with LCD Control and Client-Side Object Detection

![Project Overview](https://via.placeholder.com/800x400?text=Project+Diagram+or+Screenshot) <!-- Replace with an actual diagram or screenshot -->

This repository provides a comprehensive solution for transforming your Raspberry Pi into a versatile multimedia server. It combines live audio streaming, interactive LCD display control, and real-time camera streaming with an innovative client-side object detection feature. This architecture offloads computationally intensive tasks from the Raspberry Pi to the client's browser, ensuring smooth performance.

## Table of Contents

*   [Features](#features)
*   [Project Structure](#project-structure)
*   [Hardware Requirements](#hardware-requirements)
*   [Software Setup](#software-setup)
    *   [Operating System Preparation](#operating-system-preparation)
    *   [Python Dependencies](#python-dependencies)
    *   [System-Level Dependencies](#system-level-dependencies)
*   [Running the Applications](#running-the-applications)
    *   [Running the Audio and LCD Server](#running-the-audio-and-lcd-server)
    *   [Running the Camera Server](#running-the-camera-server)
*   [Usage](#usage)
    *   [Audio and LCD Interface](#audio-and-lcd-interface)
    *   [Camera and Object Detection Interface](#camera-and-object-detection-interface)
*   [Troubleshooting](#troubleshooting)
*   [Contributing](#contributing)
*   [License](#license)

## Features

*   **Live Audio Streaming**: Capture audio from a connected microphone on your Raspberry Pi and stream it directly to any web browser on your local network. The stream is delivered in WAV format for broad compatibility.
*   **Interactive LCD Display Control**: Send custom text messages, clear the display, or show the current time on an I2C-connected LCD screen directly from a user-friendly web interface.
*   **Real-time Camera Streaming**: Stream live video from your Raspberry Pi camera module (CSI or USB) to a web browser using efficient MJPEG encoding.
*   **Client-Side Object Detection**: Leverage the power of the client's device! Object detection is performed in the web browser using Google's MediaPipe library, drawing bounding boxes on a separate canvas without burdening the Raspberry Pi's CPU/GPU. This ensures low latency for the video stream.

## Project Structure

*   `LCD and MIC.py`:
    *   Manages audio capture using `arecord`.
    *   Initializes and controls an I2C LCD display.
    *   Hosts a Flask web server for audio streaming and LCD text input.
*   `Camera Detection.py`:
    *   Manages camera video capture using `ffmpeg`.
    *   Implements a WebSocket server for streaming raw JPEG frames to clients.
    *   Serves an HTML page with JavaScript that handles displaying the video and performing client-side object detection.

## Hardware Requirements

To fully utilize this project, you will need the following hardware components:

*   **Raspberry Pi**: Any modern Raspberry Pi model (e.g., Raspberry Pi 3B+, 4, Zero 2 W) running Raspberry Pi OS (formerly Raspbian).
*   **Microphone**: A USB microphone or an audio HAT with a microphone input.
*   **I2C LCD Display**: A character LCD display (e.g., 16x2 or 20x4) with an I2C PCF8574 adapter board. This connects to the Raspberry Pi's I2C pins.
*   **Raspberry Pi Camera Module**: Either a CSI camera module (connected via the dedicated camera port) or a USB webcam.

## Software Setup

### Operating System Preparation

Before installing Python libraries, ensure your Raspberry Pi OS is up-to-date and configured correctly.

1.  **Update your system**:
    ```bash
    sudo apt update
    sudo apt upgrade -y
    ```
2.  **Enable Interfaces**:
    *   **I2C**: Essential for communicating with the LCD display.
        ```bash
        sudo raspi-config
        # Navigate to 'Interface Options' -> 'I2C' -> 'Yes'
        ```
    *   **Camera**: Essential for the camera module.
        ```bash
        sudo raspi-config
        # Navigate to 'Interface Options' -> 'Camera' -> 'Yes'
        ```
    *   **Reboot** your Raspberry Pi after making these changes: `sudo reboot`

3.  **Verify I2C (Optional but Recommended)**:
    After rebooting, you can check if your LCD is detected on the I2C bus.
    ```bash
    sudo apt install i2c-tools
    i2cdetect -y 1 # For newer Pis (Pi 2, 3, 4, Zero 2 W)
    # or i2cdetect -y 0 # For older Pis (Pi 1, Zero)
    ```
    You should see an address like `27` or `3f` in the output, which corresponds to your LCD's I2C address. The code defaults to `0x27`.

4.  **Configure Audio Device (if necessary)**:
    The `LCD and MIC.py` script assumes your microphone is `plughw:0,0`. If you have multiple audio devices or your microphone isn't detected correctly, you might need to adjust this.
    *   List your audio devices: `arecord -l`
    *   Identify your microphone's card and device number.
    *   If needed, modify the `DEVICE` variable in `LCD and MIC.py` (e.g., `'plughw:1,0'`).

### Python Dependencies

It's recommended to use a Python virtual environment to manage dependencies.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```
    *(Replace `your-username` and `your-repo-name` with your actual GitHub details)*

2.  **Create and activate a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python libraries**:
    ```bash
    pip install Flask Flask-Sock RPLCD
    ```
    *   **Note on `RPi.GPIO`**: `RPLCD` often pulls `RPi.GPIO` as a dependency automatically. If you encounter issues related to GPIO, ensure `RPi.GPIO` is installed: `pip install RPi.GPIO`.

### System-Level Dependencies

Install these command-line tools using `apt`.

1.  **Install `alsa-utils` (for `arecord`)**:
    ```bash
    sudo apt-get install alsa-utils -y
    ```

2.  **Install `ffmpeg`**:
    ```bash
    sudo apt-get install ffmpeg -y
    ```

## Running the Applications

Each Python script runs its own Flask web server. For continuous operation, you would typically run them in separate terminal sessions or configure them as system services (e.g., using `systemd`).

### Running the Audio and LCD Server

This server will be accessible on port `5000`.

1.  **Open a new terminal session** on your Raspberry Pi.
2.  **Navigate to the project directory**:
    ```bash
    cd /path/to/your/project/directory
    ```
3.  **Activate the virtual environment**:
    ```bash
    source venv/bin/activate
    ```
4.  **Run the script**:
    ```bash
    python "LCD and MIC.py"
    ```
    You should see output indicating microphone testing, LCD initialization, and the server starting. It will also print the local IP address and port.

### Running the Camera Server

This server will be accessible on port `5002`.

1.  **Open another new terminal session** on your Raspberry Pi.
2.  **Navigate to the project directory**:
    ```bash
    cd /path/to/your/project/directory
    ```
3.  **Activate the virtual environment**:
    ```bash
    source venv/bin/activate
    ```
4.  **Run the script**:
    ```bash
    python "Camera Detection.py"
    ```
    You should see output indicating the Flask server starting.

## Usage

Once both servers are running, you can access their web interfaces from any device on the same local network as your Raspberry Pi.

To find your Raspberry Pi's IP address, you can use `hostname -I` in the terminal.

### Audio and LCD Interface

1.  **Open your web browser** and navigate to: `http://<YOUR_RASPBERRY_PI_IP_ADDRESS>:5000`
2.  **Live Audio Stream**: Click the play button on the audio player to listen to the live microphone feed.
3.  **LCD Display Control**:
    *   Type text into the input field and click "📺 Send to LCD" to display it. The text will wrap to two lines if longer than 16 characters.
    *   Use the "Quick Messages" buttons for predefined text.
    *   Click "🗑 Clear LCD" to clear the display.
    *   Click "🕐 Show Time" to display the current date and time on the LCD.

### Camera and Object Detection Interface

1.  **Open your web browser** and navigate to: `http://<YOUR_RASPBERRY_PI_IP_ADDRESS>:5002`
2.  **Live Camera Stream**: You will see two video feeds:
    *   **Raw**: This is the direct, unprocessed MJPEG stream from your Raspberry Pi camera.
    *   **Detected Objects (Browser)**: This canvas displays the same video feed but with bounding boxes and labels drawn over detected objects. This processing happens entirely in your web browser, not on the Raspberry Pi.
3.  **Status**: A status message at the bottom will indicate the detector loading and stream connection status.

## Troubleshooting

*   **"LCD library not available" / LCD not working**:
    *   Ensure `RPLCD` and `RPi.GPIO` are installed.
    *   Verify I2C is enabled in `raspi-config` and your LCD is correctly wired.
    *   Check the I2C address of your LCD using `i2cdetect -y 1`. If it's not `0x27`, update the `CharLCD` initialization in `LCD and MIC.py`.
    *   Ensure the LCD's contrast potentiometer is adjusted correctly.
*   **"Microphone test FAILED" / No audio stream**:
    *   Confirm your microphone is properly connected and powered.
    *   Run `arecord -l` to list available audio devices and verify your microphone is listed.
    *   Adjust the `DEVICE` variable in `LCD and MIC.py` to match your microphone's `plughw:X,Y` identifier if it's not `0,0`.
    *   Check audio levels with `alsamixer`.
*   **"Camera not working" / No video stream**:
    *   Ensure your camera module is securely connected to the CSI port or your USB webcam is plugged in.
    *   Verify the camera is enabled in `raspi-config`.
    *   Check if `ffmpeg` is installed correctly.
    *   Ensure `/dev/video0` exists (this is the default camera device path).
*   **Web interface not loading or "This site can't be reached"**:
    *   Double-check that both Python scripts are running in their respective terminals without errors.
    *   Verify your Raspberry Pi's IP address is correct.
    *   Ensure your client device (computer/phone) is on the same local network as the Raspberry Pi.
    *   Temporarily disable any firewalls on your Raspberry Pi (e.g., `sudo ufw disable`) for testing, but re-enable them for security.
*   **Object detection not working in browser**:
    *   Ensure your browser is modern and supports WebAssembly (WASM) and MediaPipe.
    *   Check your browser's developer console (F12) for any JavaScript errors related to MediaPipe or network issues.
    *   Verify you have an active internet connection on the client device, as MediaPipe libraries are loaded from a CDN.

## Contributing

Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features, please feel free to:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature`).
3.  Make your changes.
4.  Commit your changes (`git commit -m 'Add some feature'`).
5.  Push to the branch (`git push origin feature/YourFeature`).
6.  Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
