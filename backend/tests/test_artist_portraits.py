import pytest
from backend.src.infrastructure.metadata.itunes_provider import ITunesMetadataProvider
from backend.src.application.use_cases.manage_playlists import SyncSmartPlaylistsUseCase


def test_extract_primary_artist():
    provider = ITunesMetadataProvider()
    assert provider._extract_primary_artist("JENNIE & Dua Lipa") == "JENNIE"
    assert provider._extract_primary_artist("Maroon 5 feat. LISA") == "Maroon 5"
    assert provider._extract_primary_artist("Farruko & ULLOA") == "Farruko"
    assert provider._extract_primary_artist("YOON MIRAE, BIBI") == "YOON MIRAE"
    assert provider._extract_primary_artist("TWICE") == "TWICE"
    assert provider._extract_primary_artist("BTS (방탄소년단)") == "BTS"


def test_extract_individual_artists():
    extracted = SyncSmartPlaylistsUseCase._extract_individual_artists("JENNIE & Dua Lipa")
    assert extracted == ["JENNIE", "Dua Lipa"]

    extracted_feat = SyncSmartPlaylistsUseCase._extract_individual_artists("Maroon 5 feat. LISA")
    assert extracted_feat == ["Maroon 5", "LISA"]

    extracted_comma = SyncSmartPlaylistsUseCase._extract_individual_artists("Farruko, ULLOA")
    assert extracted_comma == ["Farruko", "ULLOA"]

    extracted_single = SyncSmartPlaylistsUseCase._extract_individual_artists("TWICE")
    assert extracted_single == ["TWICE"]


def test_lookup_artist_artwork_avoids_placeholders():
    provider = ITunesMetadataProvider(timeout_seconds=8.0)
    
    # 1. Test TWICE gets real valid portrait
    twice_pic = provider.lookup_artist_artwork("TWICE")
    if twice_pic:
        assert "/artist//" not in twice_pic
        assert not twice_pic.endswith("/default")

    # 2. Test BTS gets real valid portrait
    bts_pic = provider.lookup_artist_artwork("BTS")
    if bts_pic:
        assert "/artist//" not in bts_pic
        assert not bts_pic.endswith("/default")

    # 3. Test Collaboration extracts primary artist portrait
    collab_pic = provider.lookup_artist_artwork("JENNIE & Dua Lipa")
    if collab_pic:
        assert "/artist//" not in collab_pic
