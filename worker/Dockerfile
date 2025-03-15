FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Make directory for model data
RUN mkdir -p /app/model_data

# Expose the port
EXPOSE 5000

# Command to run the application
CMD ["python", "worker.py"]