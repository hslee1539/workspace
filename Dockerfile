# syntax=docker/dockerfile:1
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        unzip \
        zip \
        git \
        ca-certificates \
        build-essential \
        openjdk-17-jdk \
        wget \
        python3 \
        python3-pip \
        gnupg \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS) and npm
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH="${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${PATH}"

RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools \
    && curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip \
    && unzip -q /tmp/cmdline-tools.zip -d ${ANDROID_SDK_ROOT}/cmdline-tools \
    && rm /tmp/cmdline-tools.zip \
    && mv ${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/latest

RUN yes | ${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager --licenses

RUN yes | ${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager \
        "platform-tools" \
        "build-tools;34.0.0" \
        "platforms;android-35" \
        "ndk;29.0.13113456" \
        "build-tools;35.0.0" \
        "platforms;android-36" \
        "cmake;3.18.1" \
        "cmake;3.22.1"

RUN npm install -g @openai/codex@0.46.0 \
    && npm install -g opencode-ai \
    && npm install -g @qwen-code/qwen-code@0.0.15-nightly.8

ENV OPENAI_BASE_URL=https://api.openai.com/v1
ENV OPENAI_MODEL=gpt-5-mini

WORKDIR /workspace

CMD ["bash"]
