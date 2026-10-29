FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY . /tests/
RUN mkdir -p /app /logs/verifier
# The trusted deployment provides Spectre and its licensed libraries.
# /app contains no candidate until Harbor restores collected artifacts.
