FROM python:3.11-slim

ARG PADDLEPADDLE_VERSION=3.2.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

RUN python -m pip install --no-cache-dir \
        "paddlepaddle==${PADDLEPADDLE_VERSION}" \
        "paddleocr[all]>=3,<4" \
    && paddlex --install serving

EXPOSE 8080

CMD ["paddlex", "--serve", "--pipeline", "OCR", "--host", "0.0.0.0", "--port", "8080", "--device", "cpu"]

