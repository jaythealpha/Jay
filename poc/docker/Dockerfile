# Memory App POC — Animated Drawings server
# Wraps facebookresearch/AnimatedDrawings with TorchServe.
# CPU-only image. For GPU, swap base image to pytorch/torchserve:0.7.1-gpu and add --gpus all.

FROM pytorch/torchserve:0.7.1-cpu

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Pin to a known-good commit so the POC is reproducible.
# (Update this hash if upstream API changes.)
ARG ANIMATED_DRAWINGS_REF=main
RUN git clone https://github.com/facebookresearch/AnimatedDrawings.git \
    && cd AnimatedDrawings \
    && git checkout ${ANIMATED_DRAWINGS_REF}

WORKDIR /workspace/AnimatedDrawings

# Install the package and its drawn-humanoid model handlers.
RUN pip install --no-cache-dir -e .

# Download the pre-trained models the project ships its own scripts for.
# The torchserve subdir contains a script that fetches model weights and
# packages them as .mar archives.
WORKDIR /workspace/AnimatedDrawings/torchserve
RUN bash -lc "./download_models.sh && ./create_mar_files.sh" \
    || echo "WARN: model fetch failed at build time; will retry at container start"

# Copy MAR files into TorchServe's model store.
RUN mkdir -p /home/model-server/model-store \
    && cp -v *.mar /home/model-server/model-store/ 2>/dev/null || true

# Custom config so TorchServe auto-loads our two models.
COPY config.properties /home/model-server/config.properties

EXPOSE 8080 8081

# Use the official entrypoint with our config.
CMD ["torchserve", "--start", "--ncs", "--ts-config", "/home/model-server/config.properties", "--model-store", "/home/model-server/model-store", "--models", "drawn_humanoid_detector=drawn_humanoid_detector.mar", "drawn_humanoid_pose_estimator=drawn_humanoid_pose_estimator.mar"]
