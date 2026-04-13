# ---- Builder stage ----
FROM python:3.12-slim AS builder

WORKDIR /build

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    fi \
 && if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
    fi \
 && apt-get update \
 && apt-get install -y --no-install-recommends gcc \
 && rm -rf /var/lib/apt/lists/*

COPY vna-main-server/requirements.txt .
COPY vna-common /build/vna-common
RUN pip install --no-cache-dir --prefix=/install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-deps /build/vna-common \
 && pip install --no-cache-dir --prefix=/install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# ---- Runtime stage ----
FROM python:3.12-slim

RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    fi \
 && if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g; s|http://security.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list; \
    fi

WORKDIR /app

COPY --from=builder /install /usr/local

COPY vna-main-server/ .
RUN chmod +x /app/scripts/start.sh

EXPOSE 8000

RUN useradd --create-home --shell /bin/bash appuser
USER appuser
CMD ["/app/scripts/start.sh"]
