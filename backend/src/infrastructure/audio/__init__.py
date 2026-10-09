"""Audio processing and tagging infrastructure."""

from .ffmpeg_processor import FFmpegAudioProcessor
from .mutagen_tagger import MutagenTaggingService

__all__ = ["FFmpegAudioProcessor", "MutagenTaggingService"]
