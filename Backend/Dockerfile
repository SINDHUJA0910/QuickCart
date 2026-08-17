# QuickCart backend — production image.
#
# Multi-stage build: the builder stage installs dependencies (including
# torch/ultralytics/opencv for the AI pipeline, which are large), and the
# final stage copies only the installed packages + app code, not pip's
# build cache or wheel files, keeping the shipped image smaller than a
# single-stage build would.

FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed to build some Python packages (opencv, etc.) — removed
# in the final stage since only their *effects* (installed site-packages)
# are copied forward, not these build tools themselves.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# torch is installed separately from the CPU-only wheel index FIRST.
# Plain `pip install torch` from PyPI pulls in ~2GB of NVIDIA CUDA packages
# (nvidia-cublas, nvidia-cudnn, etc.) as dependencies — completely wasted
# weight for this app, which only ever does CPU inference (Railway/Render
# don't provide GPUs on standard plans, and this pipeline was designed and
# tested for CPU throughout). Installing the explicit +cpu build here keeps
# the final image several GB smaller. The version below must match the
# torch== pin in requirements.txt exactly, or the subsequent
# `pip install -r requirements.txt` will try to replace it with the full
# CUDA build.
RUN pip install --no-cache-dir --user torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.12-slim AS runtime

# Runtime-only shared libraries that opencv's Python wheel links against
# (not full build tools — those stay in the builder stage).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — the API process never needs root, and running as root in
# a container is an unnecessary privilege escalation surface if the
# container is ever compromised.
RUN useradd --create-home --shell /bin/bash quickcart
USER quickcart
WORKDIR /home/quickcart/app

COPY --from=builder --chown=quickcart:quickcart /root/.local /home/quickcart/.local
COPY --chown=quickcart:quickcart . .

ENV PATH=/home/quickcart/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Liveness check hits the unauthenticated /health endpoint — no secrets needed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
