FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ansible \
        git \
        openssh-client \
        rsync \
    && rm -rf /var/lib/apt/lists/*

RUN ansible-galaxy collection install ansible.posix community.docker

COPY pyproject.toml .
COPY app ./app

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
