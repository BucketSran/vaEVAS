FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY starter/ /app/
RUN mkdir -p /app/output
# The trusted deployment must provide the licensed Spectre executable and libraries.
# This image does not install, replace, or claim access to that backend.
