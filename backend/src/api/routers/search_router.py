"""Search Router: Query YouTube videos."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import Container, get_container
from ..schemas import SearchResultResponse

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", response_model=list[SearchResultResponse])
def search_youtube(
    q: str = Query(..., min_length=1, description="Search keyword query"),
    limit: int = Query(15, ge=1, le=50, description="Max results to return"),
    container: Container = Depends(get_container),
):
    """Searches YouTube videos and returns ranked metadata."""
    try:
        use_case = container.get_search_use_case()
        results = use_case.execute(query=q, max_results=limit)
        return [SearchResultResponse.from_dto(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching YouTube: {e}")


@router.get("/info", response_model=SearchResultResponse)
def get_video_info(
    url: str = Query(..., min_length=1, description="YouTube URL or video ID"),
    container: Container = Depends(get_container),
):
    """Retrieves metadata for a single YouTube video or URL."""
    use_case = container.get_search_use_case()
    result = use_case.get_info(url)
    if not result:
        raise HTTPException(status_code=404, detail="No se pudo obtener información del video.")

    return SearchResultResponse.from_dto(result)
