# Offline runtime assembly. PYTHON_BASE must name an already-installed digest.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
COPY runtime/evas/ /opt/evas/src/evas/
COPY --chmod=0555 runtime/evas-kernel /opt/evas/evas-kernel
COPY runtime/source-identity.json /opt/evas/source-identity.json
ENV PYTHONPATH=/opt/evas/src EVAS_KERNEL=/opt/evas/evas-kernel PYTHONDONTWRITEBYTECODE=1
