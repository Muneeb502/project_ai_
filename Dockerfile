# Dockerfile
FROM python:3.12-slim

# Prevent writing pyc files and enable stdout logging
ENV PYTHONDONTWRITEBYTECODE=1

# Set environment variable for unbuffered stdout
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app    

# Copy the requirements.txt file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port (Hugging Face expects 7860)
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]