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

COPY font/FrutigerNeueLTW1G-Medium.otf /usr/share/fonts/
RUN fc-cache -fv

WORKDIR /opt

RUN chown ubuntu:ubuntu /opt

USER ubuntu
ARG RSUDP_COMMIT=e4bf7abbbe4db4e70e04150d436e7d68dd16312a

RUN git clone https://github.com/raspishake/rsudp.git \
 && cd rsudp && git checkout ${RSUDP_COMMIT}

RUN bash rsudp/unix-install-rsudp.sh

COPY c_plots.diff c_plots.diff
COPY plot_meta.diff plot_meta.diff
COPY plot_style.diff plot_style.diff
COPY c_liveness.diff c_liveness.diff

RUN cd rsudp && patch -p1 < ../c_plots.diff && rm -f ../c_plots.diff
RUN cd rsudp && patch -p1 < ../plot_meta.diff && rm -f ../plot_meta.diff
RUN cd rsudp && patch -p1 < ../plot_style.diff && rm -f ../plot_style.diff
RUN cd rsudp && patch -p1 < ../c_liveness.diff && rm -f ../c_liveness.diff

RUN jq '.settings.station = "Shake" \
      | .settings.output_dir = "/opt/rsudp/data" \
      | .write.enabled = true \
      | .plot.eq_screenshots = true \
      | .rsam.enabled = true \
      | .rsam.deconvolve = true \
      | .rsam.fwaddr = false \
      | .rsam.fwport = false \
      | .health.enabled = true \
      | .health.interval = 30' \
    /home/ubuntu/.config/rsudp/rsudp_settings.json > /tmp/rsudp_settings.json \
 && mv /tmp/rsudp_settings.json /home/ubuntu/.config/rsudp/rsudp_settings.json

# NOTE: 以下はビューワー用
RUN mkdir rsudp/webui

WORKDIR /opt/rsudp/webui

ENV PATH="/home/ubuntu/.local/bin:$PATH"
ENV UV_LINK_MODE=copy \
    UV_NO_SYNC=1

# ubuntu ユーザーで uv をインストール
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=cache,target=/home/ubuntu/.cache/uv,uid=1000,gid=1000 \
    uv sync --no-install-project --no-editable --no-group dev --compile-bytecode

ARG IMAGE_BUILD_DATE
ENV IMAGE_BUILD_DATE=${IMAGE_BUILD_DATE}

COPY --chown=ubuntu:ubuntu . .

# プロジェクトをインストール
RUN --mount=type=cache,target=/home/ubuntu/.cache/uv,uid=1000,gid=1000 \
    uv sync --no-group dev --compile-bytecode

EXPOSE 8888/udp
EXPOSE 5000

# NOTE: デフォルトでは rsudp を実行
WORKDIR /opt
CMD ["bash", "rsudp/unix-start-rsudp.sh"]
