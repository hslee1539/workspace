# syntax=docker/dockerfile:1

ARG ANDROID_VARIANT=0-33
FROM mcr.microsoft.com/devcontainers/android:${ANDROID_VARIANT}

ARG USERNAME=vscode

RUN apt-get update \
    && apt-get install -y --no-install-recommends git-lfs zsh unzip python3 python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN su - ${USERNAME} -c "mkdir -p /home/${USERNAME}/.android && touch /home/${USERNAME}/.android/repositories.cfg"

RUN yes | sdkmanager --licenses >/dev/null 2>&1 || true

ENV GRADLE_USER_HOME=/home/${USERNAME}/.gradle
ENV ANDROID_HOME=/usr/local/android-sdk
ENV ANDROID_SDK_ROOT=/usr/local/android-sdk

CMD ["/bin/bash"]
