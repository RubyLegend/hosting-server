# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim

# Set the working directory within the container
WORKDIR /

# Copy the necessary files and directories into the container
ADD __init__.py app.py requirements.txt /api-flask/
ADD video /api-flask/video
ADD user /api-flask/user
ADD search /api-flask/search
ADD company /api-flask/company
ADD database /api-flask/database
# ADD helpers /api-flask/helpers

# Upgrade pip and install Python dependencies
RUN pip3 install --upgrade pip && pip install --no-cache-dir -r /api-flask/requirements.txt

# Expose port 8080 for the Flask application
EXPOSE 8080

# Define the command to run the Flask application using Gunicorn
# CMD ["flask", "run"]
CMD ["gunicorn", "--chdir", "api-flask", "api-flask.app:app", "-b", "0.0.0.0:8080", "-w", "4", "--timeout", "600"]
