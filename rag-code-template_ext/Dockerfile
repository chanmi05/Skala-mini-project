FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*
COPY requirements-e.txt ./
COPY rag-service/requirements-rag-workflow.txt ./rag-service/
RUN python -m pip install --upgrade pip \
 && python -m pip install -r rag-service/requirements-rag-workflow.txt
COPY . .
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "rag_external-web_pdf_closed_llm:app", "--host", "0.0.0.0", "--port", "8001"]
