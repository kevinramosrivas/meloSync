"""Use Case: Search YouTube."""

from __future__ import annotations

import logging
from typing import Optional

from ..dto import SearchResultDTO
from ...domain.services import IYouTubeSearchService

logger = logging.getLogger(__name__)


class SearchYouTubeUseCase:
    """Orchestrates YouTube search queries and maps results to DTOs."""

    def __init__(self, search_service: IYouTubeSearchService) -> None:
        self._search_service = search_service

    def execute(self, query: str, max_results: int = 15) -> list[SearchResultDTO]:
        """Executes query and returns list of SearchResultDTO."""
        if not query or not query.strip():
            return []

        results = self._search_service.search(query.strip(), max_results=max_results)
        return [SearchResultDTO.from_domain(r) for r in results]

    def get_info(self, url_or_id: str) -> Optional[SearchResultDTO]:
        """Fetches metadata for a single YouTube video."""
        result = self._search_service.get_info(url_or_id)
        return SearchResultDTO.from_domain(result) if result else None
