FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386 && apt-get -o Acquire::ForceIPv4=true update -qq && \
    apt-get -o Acquire::ForceIPv4=true install -y --no-install-recommends \
    wine64 wine32:i386 xvfb xauth pulseaudio pulseaudio-utils fonts-wine \
    fonts-wqy-microhei locales python3 ca-certificates xdotool && \
    sed -i 's/^# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/;s/^# zh_CN.GB18030 GB18030/zh_CN.GB18030 GB18030/' /etc/locale.gen && \
    locale-gen && rm -rf /var/lib/apt/lists/*
USER 1000:1000
ENV HOME=/work/home DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/runtime-user WINEPREFIX=/work/prefix WINEARCH=win64 PYTHONUTF8=1
WORKDIR /work
ENTRYPOINT ["python3", "/tools/run.py"]
