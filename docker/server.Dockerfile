# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /workspace

COPY . /workspace

EXPOSE 1539

CMD ["python", "-m", "server.app"]
