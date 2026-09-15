FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /controller
COPY services/integration-controller/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY services/integration-controller/server.py ./server.py

EXPOSE 8080
CMD ["python", "server.py"]
