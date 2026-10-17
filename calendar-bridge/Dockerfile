FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bridge.py .
VOLUME /data
EXPOSE 8099
CMD ["python", "bridge.py"]
