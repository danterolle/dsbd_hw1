FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire 'app' directory contents into the container
COPY ./app .


# Expose the port the Flask app will run on
EXPOSE 5000

# Run the flask server and make it accessible from outside the container
CMD ["python", "app.py"]