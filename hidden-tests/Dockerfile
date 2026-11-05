FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake redis-server libpq-dev libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY module2-backend/requirements.txt module2-backend/requirements.txt
COPY module3-face-recognition/requirements.txt module3-face-recognition/requirements.txt
COPY hidden-tests/requirements.txt hidden-tests/requirements.txt
RUN pip install --no-cache-dir -r hidden-tests/requirements.txt
COPY module2-backend module2-backend
COPY module3-face-recognition module3-face-recognition
COPY sample_images sample_images
COPY hidden-tests hidden-tests
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "-m", "pytest", "-c", "hidden-tests/pytest.ini", "hidden-tests"]

