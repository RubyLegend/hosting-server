# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim

# Set the working directory within the container
WORKDIR /

# Copy the necessary files and directories into the container
ADD video_gateway/__init__.py video_gateway/app.py video_gateway/requirements.txt /api-flask/
ADD video_gateway/video /api-flask/video
ADD database /api-flask/database
ADD helpers /api-flask/helpers

# Upgrade pip and install Python dependencies
RUN pip3 install --upgrade pip && pip install --no-cache-dir -r /api-flask/requirements.txt

# Expose port 9000 for the Flask application
EXPOSE 9000

# Define the command to run the Flask application using Gunicorn
# CMD ["flask", "run"]
CMD ["gunicorn", "--chdir", "api-flask", "api-flask.app:app", "-b", "0.0.0.0:9000", "-w", "4"]
