# Solver and verifier image. The EVAS simulator is not installed yet: the
# module library does not run on current EVAS (issue 229), so the image
# build and the backend installation remain pending. The starter brings the
# fixed module library (/app/modules) and the public testbench.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
COPY starter/ /app/
