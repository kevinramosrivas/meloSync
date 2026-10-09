"""Views package exports."""

from src.presentation.views.bottom_bar import BottomBarWidget
from src.presentation.views.downloads_view import DownloadsView
from src.presentation.views.library_view import LibraryView
from src.presentation.views.main_window import MainWindow
from src.presentation.views.metadata_dialog import MetadataEditDialog
from src.presentation.views.search_view import SearchView
from src.presentation.views.sidebar import SidebarWidget

__all__ = [
    "SidebarWidget",
    "SearchView",
    "LibraryView",
    "DownloadsView",
    "BottomBarWidget",
    "MainWindow",
    "MetadataEditDialog",
]
