# One image, five entrypoints (D-10): alarm-api, alarm-mcp, copilot-api, gui,
# rag-ingest/rag-bootstrap all run from this same image, differing only in `command:`.
# Single dependency resolution, single layer cache -- faster and less fragile than six
# independent builds.
FROM python:3.12-slim AS runtime

# Apple-Silicon evaluators get a predictable (if slower) emulated build rather than a
# build that silently differs by host architecture (L-20).
# platform is pinned in docker-compose.yml, not here, so local `docker build` still
# works on any host during development.

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed_cache

# Dependency layer cached separately from source so code-only changes don't reinstall.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# Bake both FastEmbed models at build time; fail the build loudly on download failure
# rather than deferring to (and silently breaking) first use at runtime (R-02).
RUN uv run python -c "\
from rag.ingestion.embedder import Embedder; \
e = Embedder(cache_dir='/opt/fastembed_cache'); \
list(e.embed_dense(['warm up'])); \
list(e.embed_sparse(['warm up'])); \
print('FastEmbed models baked into the image successfully')"

# No network access needed at runtime -- the models are already on disk.
ENV HF_HUB_OFFLINE=1

EXPOSE 8000 9000 8080 8501

ENTRYPOINT ["uv", "run"]
CMD ["python", "-m", "alarm_api_simulator"]
