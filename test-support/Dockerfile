FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /suite
COPY requirements.txt /opt/test-support/requirements.txt
RUN pip install --no-cache-dir -r /opt/test-support/requirements.txt
COPY public_test_isolation.py run_public_tests.py /opt/test-support/
ENTRYPOINT ["python", "/opt/test-support/run_public_tests.py"]
