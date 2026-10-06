# Offline runtime assembly. PYTHON_BASE must name an installed base; record and verify its image ID.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
COPY runtime/evas/ /opt/evas/src/evas/
# -B prevents writes but still reads bytecode. Remove inherited caches offline.
RUN python3 -c "from pathlib import Path; [p.unlink() for p in Path('/opt/evas/src').rglob('*.pyc')]"
COPY --chmod=0555 runtime/evas-kernel /opt/evas/evas-kernel
COPY runtime/source-identity.json /opt/evas/source-identity.json
ENV PYTHONPATH=/opt/evas/src EVAS_KERNEL=/opt/evas/evas-kernel PYTHONDONTWRITEBYTECODE=1
