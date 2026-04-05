FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working dir
WORKDIR /app

# Copy files
COPY . .

# Install python deps
RUN pip install --no-cache-dir -r requirements.txt

# Start bot
CMD ["python", "main.py"]
