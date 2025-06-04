# syntax=docker/dockerfile:1

# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for psycopg2 and other potential C extensions
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev curl && \
    # Clean up apt cache to reduce image size
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the Django project code into the container
COPY . /app/

# Expose the port the app runs on (Gunicorn/Django dev server)
EXPOSE 8000

# The command to run the application will be specified in docker-compose.yml
# This allows for different commands for development vs. production.