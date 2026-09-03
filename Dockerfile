# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install OS-level dependencies required for WebRTC, PyAudio, and Pipecat
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    portaudio19-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose port (Railway will provide $PORT)
EXPOSE 8080

# Use run.py which internally invokes Hypercorn with proper SSL/WebRTC thread handling
# Pipecat requires a clean async loop without Gunicorn worker interference for WebRTC
CMD ["python", "run.py"]
