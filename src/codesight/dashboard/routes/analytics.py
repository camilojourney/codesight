"""Query analytics dashboard routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from . import get_manager, get_templates


def analytics_router() -> APIRouter:
    router = APIRouter()

    @router.get("/analytics")
    async def analytics_page(
        request: Request,
        workspace_id: str | None = Query(default=None),
        days: int = Query(default=30, ge=1, le=365),
    ):
        query_log = request.app.state.query_log
        templates = get_templates(request)
        manager = get_manager(request)

        # // SPEC-014-008: Analytics supports workspace filter and defaults to last 30 days.
        top_queries = query_log.top_queries(days=days, workspace_id=workspace_id)
        p50_latency_ms, p95_latency_ms = query_log.latency_percentiles(
            days=days,
            workspace_id=workspace_id,
        )
        confidence = query_log.confidence_distribution(days=days, workspace_id=workspace_id)
        workspaces = manager.list()

        return templates.TemplateResponse(
            request,
            "analytics.html",
            {
                "title": "Analytics",
                "top_queries": top_queries,
                "p50_latency_ms": p50_latency_ms,
                "p95_latency_ms": p95_latency_ms,
                "confidence": confidence,
                "workspaces": workspaces,
                "selected_workspace_id": workspace_id,
                "days": days,
            },
        )

    return router


__all__ = ["analytics_router"]
