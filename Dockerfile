FROM ubuntu:24.04

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    curl \
    ca-certificates \
    tini \
    build-essential \
    git \
    language-pack-ja \
    tzdata

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    jq wget ffmpeg

WORKDIR /opt

ARG RSUDP_COMMIT=e4bf7abbbe4db4e70e04150d436e7d68dd16312a

RUN git clone https://github.com/raspishake/rsudp.git \
 && cd rsudp && git checkout ${RSUDP_COMMIT}

RUN bash rsudp/unix-install-rsudp.sh

COPY c_plots.diff c_plots.diff
RUN cd rsudp && patch -p1 < ../c_plots.diff && rm ../c_plots.diff

RUN jq '.settings.station = "Raspberry Shake" | .settings.output_dir = "/opt/rsudp/data" | .write.enabled = true | .plot.eq_screenshots = true' \
    /root/.config/rsudp/rsudp_settings.json > /tmp/rsudp_settings.json \
 && mv /tmp/rsudp_settings.json /root/.config/rsudp/rsudp_settings.json

EXPOSE 8888/udp

CMD ["bash", "rsudp/unix-start-rsudp.sh"]
