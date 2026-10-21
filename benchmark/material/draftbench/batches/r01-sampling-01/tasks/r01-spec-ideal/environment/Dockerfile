# Reuse the repository's pinned Python base. No build was executed this round.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
COPY starter/ /app/
# The trusted deployment supplies licensed Spectre and its license environment.
# This image does not redistribute or install commercial simulator binaries.
