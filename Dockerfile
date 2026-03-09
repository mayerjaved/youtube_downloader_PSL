# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt and force latest yt-dlp nightly
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -U "yt-dlp[default]" --pre

# Create the downloads directory
RUN mkdir -p downloads

# Run download_channel.py when the container launches
CMD ["python", "download_channel.py"]
