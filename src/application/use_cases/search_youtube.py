"""Use Case: Search YouTube tracks."""

from __future__ import annotations

import logging
from typing import Optional

from src.application.dto import SearchQueryDTO, SearchResultItemDTO
from src.domain.services import IYouTubeSearchService

logger = logging.getLogger(__name__)


class SearchYouTubeUseCase:
    """Orchestrates YouTube search queries and transforms domain results into DTOs."""

    def __init__(self, search_service: IYouTubeSearchService) -> None:
        self._search_service = search_service

    def execute(self, query_dto: SearchQueryDTO) -> list[SearchResultItemDTO]:
        """Executes search query against YouTube search service."""
        cleaned_query = query_dto.query.strip()
        if not cleaned_query:
            logger.warning("Empty search query provided.")
            return []

        logger.info("Searching YouTube for query: '%s' (limit=%d)", cleaned_query, query_dto.max_results)
        results = self._search_service.search(cleaned_query, max_results=query_dto.max_results)

        return [
            SearchResultItemDTO(
                youtube_id=item.youtube_id,
                title=item.title,
                duration_seconds=item.duration_seconds,
                duration_formatted=item.duration_formatted,
                channel_name=item.channel_name,
                thumbnail_url=item.thumbnail_url,
                url=item.url,
            )
            for item in results
        ]

    def get_info(self, url_or_id: str) -> Optional[SearchResultItemDTO]:
        """Fetches metadata for a direct YouTube URL or single ID."""
        cleaned = url_or_id.strip()
        if not cleaned:
            return None

        item = self._search_service.get_info(cleaned)
        if not item:
            return None

        return SearchResultItemDTO(
            youtube_id=item.youtube_id,
            title=item.title,
            duration_seconds=item.duration_seconds,
            duration_formatted=item.duration_formatted,
            channel_name=item.channel_name,
            thumbnail_url=item.thumbnail_url,
            url=item.url,
        )
