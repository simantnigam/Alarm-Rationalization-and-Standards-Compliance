"""alarm-management MCP server. Walking-skeleton slice (02-phases.md Phase 2.5): one
tool, `search_assets`, over a real transport, calling the real connector. Phase 4 adds
the remaining 9 read tools, the 2 write-path tools, and the full 7-row error mapping
table on top of this same server object.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse

from connectors.alarm_api.client import AlarmApiClient
from connectors.alarm_api.errors import AlarmApiError
from mcp_servers.alarm_management.config import AlarmMcpSettings
from mcp_servers.alarm_management.schemas import AssetResult, SearchAssetsOutput


def _trace_id_from(ctx: Context) -> str | None:
    """Correlation/trace metadata propagates via the MCP request's `_meta` field (the
    client sends `meta={"trace_id": ...}` on call_tool), not as a tool argument -- so it
    never appears in the tool's public input schema.
    """
    meta = ctx.request_context.meta
    return getattr(meta, "trace_id", None) if meta else None


def build_server(settings: AlarmMcpSettings) -> FastMCP:
    # DNS-rebinding protection is a browser-threat mitigation (a malicious webpage
    # tricking a victim's browser into hitting a localhost service); it doesn't apply
    # to this server-to-server MCP connection, but the correct response is an accurate
    # allowlist, not disabling the check.
    mcp = FastMCP(
        name="alarm-management",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=settings.allowed_hosts_list,
            allowed_origins=settings.allowed_hosts_list,
        ),
    )
    client = AlarmApiClient(base_url=settings.alarm_api_base_url, token=settings.alarm_api_token)

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @mcp.tool(
        name="search_assets",
        description=(
            "Search for plant assets (pumps, compressors, motors, valves, exchangers, "
            "turbines) by name, type, or location. Use this to resolve an asset name "
            "mentioned in a question (e.g. 'Boiler Feed Pump 101') into an asset_id "
            "before calling other tools."
        ),
    )
    async def search_assets(
        ctx: Context,
        query: str,
        limit: int = 20,
        unit: str | None = None,
        site: str | None = None,
    ) -> SearchAssetsOutput:
        try:
            response = await client.search_assets(
                query=query,
                limit=limit,
                unit=unit,
                site=site,
                trace_id=_trace_id_from(ctx),
            )
        except AlarmApiError as exc:
            # Minimal mapping for the walking skeleton -- Phase 4 replaces this with the
            # full 7-row table (UPSTREAM_AUTH_FAILED, RATE_LIMITED, etc).
            raise RuntimeError(f"search_assets failed: {exc}") from exc

        return SearchAssetsOutput(
            results=[
                AssetResult(
                    asset_id=a.asset_id,
                    asset_name=a.asset_name,
                    asset_type=a.asset_type,
                    site=a.site,
                    unit=a.unit,
                    criticality=a.criticality,
                )
                for a in response.results
            ],
            total=response.total,
            simulator_trace_id=response.meta.trace_id,
        )

    return mcp
