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

ENV TZ=Asia/Tokyo \
    LANG=ja_JP.UTF-8 \
    LANGUAGE=ja_JP:ja \
    LC_ALL=ja_JP.UTF-8

RUN locale-gen en_US.UTF-8
RUN locale-gen ja_JP.UTF-8

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    jq wget ffmpeg

WORKDIR /opt

RUN chown ubuntu:ubuntu /opt

USER ubuntu


ARG RSUDP_COMMIT=e4bf7abbbe4db4e70e04150d436e7d68dd16312a

RUN git clone https://github.com/raspishake/rsudp.git \
 && cd rsudp && git checkout ${RSUDP_COMMIT}

RUN bash rsudp/unix-install-rsudp.sh

COPY c_plots.diff c_plots.diff
RUN cd rsudp && patch -p1 < ../c_plots.diff && rm ../c_plots.diff

RUN jq '.settings.station = "Shake" \
      | .settings.output_dir = "/opt/rsudp/data" \
      | .write.enabled = true \
      | .plot.eq_screenshots = true \
      | .rsam.enabled = true \
      | .rsam.deconvolve = true \
      | del(.rsam.fwaddr) \
      | del(.rsam.fwport)' \
    /home/ubuntu/.config/rsudp/rsudp_settings.json > /tmp/rsudp_settings.json \
 && mv /tmp/rsudp_settings.json /home/ubuntu/.config/rsudp/rsudp_settings.json

EXPOSE 8888/udp

CMD ["bash", "rsudp/unix-start-rsudp.sh"]
