# ATLAS risk engine — minimal, dependency-free container.
FROM python:3.11-slim

# Non-root runtime user.
RUN useradd --create-home --uid 10001 atlas
WORKDIR /app

# Install the package itself (no third-party deps to resolve).
COPY pyproject.toml README.md ./
COPY atlas ./atlas
RUN pip install --no-cache-dir .

USER atlas
EXPOSE 8080
ENV ATLAS_HOST=0.0.0.0 ATLAS_PORT=8080 ATLAS_LOG_FORMAT=json

# Liveness check hits the health endpoint.
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status==200 else 1)"

ENTRYPOINT ["atlas"]
CMD ["serve"]
