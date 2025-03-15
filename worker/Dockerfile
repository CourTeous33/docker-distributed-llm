FROM python:3.9-slim

WORKDIR /app

# Copy only the requirements file first
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt

# Copy only the necessary application files
COPY worker.py .

# Expose the port
EXPOSE 5000

# Command to run the application
CMD ["python", "worker.py"]