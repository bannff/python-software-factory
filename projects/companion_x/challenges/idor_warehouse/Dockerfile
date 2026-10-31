FROM python:3.12-slim
WORKDIR /app
RUN pip install flask --no-cache-dir
COPY app.py .
EXPOSE 5000
CMD ["python", "app.py"]
