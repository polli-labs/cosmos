from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

# ruff: noqa: UP035
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class ClipStatus(Enum):
    """Status of a clip's data availability"""
    COMPLETE = "complete"    # All expected segments present
    PARTIAL = "partial"      # Some segments missing
    MISSING = "missing"      # No segments found
    INVALID = "invalid"      # Metadata inconsistency detected


@dataclass
class Position:
    """
    Represents a position in the COSM directory structure.

    Format is typically "NH/MM/SS.sss" where:
    - N: Hour number
    - MM: Minute number
    - SS.sss: Second with fractional component
    """
    hour: int
    minute: int
    second: float

    @classmethod
    def from_string(cls, pos_str: str) -> Position:
        """Parse a position string like '0H/0M/3.8S/'"""
        parts = pos_str.strip('/').split('/')
        if len(parts) != 3:
            raise ValueError(f"Invalid position string format: {pos_str}")
        
        try:
            hour = int(parts[0].rstrip('H'))
            minute = int(parts[1].rstrip('M'))
            second = float(parts[2].rstrip('S'))
            return cls(hour=hour, minute=minute, second=second)
        except (ValueError, IndexError) as e:
            raise ValueError(f"Failed to parse position string: {pos_str}") from e

    def to_string(self) -> str:
        """Convert position back to string format"""
        return f"{self.hour}H/{self.minute}M/{self.second}S"
    
    def to_seconds(self) -> float:
        """Convert position to total seconds from start of hour"""
        return self.hour * 3600 + self.minute * 60 + self.second
    
    def path_fragment(self) -> str:
        """Return a directory path fragment like '0H/0M/25S'."""
        return f"{self.hour}H/{self.minute}M/{self.second}S"


@dataclass
class ClipInfo:
    """
    Information about a single clip from the manifest.

    Clips represent continuous recording sessions, each containing multiple
    video segments that should be processed together.
    """
    name: str                     # Clip identifier (e.g., "CLIP1")
    start_epoch: float            # Start timestamp (Unix epoch)
    end_epoch: float | None              # End timestamp (Unix epoch) - may be None initially
    start_pos: Position           # Starting directory position
    end_pos: Position | None             # Ending directory position
    start_idx: int                # Starting frame index
    end_idx: int                  # Ending frame index
    start_time: datetime | None          # Human-readable start time
    status: ClipStatus = ClipStatus.MISSING

    @property
    def duration(self) -> float:
        """Duration of clip in seconds"""
        if self.end_epoch is None:
            return 0.0
        return self.end_epoch - self.start_epoch

    @property
    def frame_count(self) -> int:
        """Total number of frames in clip"""
        return self.end_idx - self.start_idx
        
    @property
    def fps(self) -> int:
        if self.end_epoch is None or self.duration <= 0:
            raise ValueError(f"Clip {self.name} has no valid duration. Cannot compute FPS.")
        raw_fps = self.frame_count / self.duration
        return int(round(raw_fps))


class ManifestParser:
    """
    Parser for COSM C360 camera clip manifests.

    The manifest XML contains information about recording sessions ("clips"),
    including their temporal boundaries, frame indices, and positions within
    the directory structure.
    """
    
    def __init__(self, manifest_path: Path, logger: logging.Logger | None = None):
        """
        Initialize parser with path to manifest XML.
        
        Args:
            manifest_path: Path to the manifest XML file
            logger: Optional logger instance
            
        Raises:
            FileNotFoundError: If manifest file doesn't exist
            xml.etree.ElementTree.ParseError: If XML is malformed
        """
        self.manifest_path = manifest_path
        self._clips: dict[str, ClipInfo] = {}
        self.logger = logger or logging.getLogger(__name__)
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")
        
        self._parse_manifest()
    
    def _parse_manifest(self) -> None:
        """Parse the manifest XML and populate clip information.

        Expected XML structure per clip element:
        - Name: Clip identifier (e.g., "CLIP1")
        - Epoch: Start timestamp (Unix epoch)
        - Pos: Starting position "NH/MM/SS.sss/"
        - InIdx/OutIdx: Frame index boundaries
        - InStr: Human-readable timestamp
        """
        tree = ET.parse(self.manifest_path)  # noqa: S314
        root = tree.getroot()
        
        self.logger.debug(f"Parsing manifest: {self.manifest_path}")
        self.logger.debug(f"Found {len(root)} clip entries in manifest")
        
        for elem in root:
            try:
                name = elem.attrib['Name']
                self.logger.debug(f"Parsing clip: {name}")
                self.logger.debug(f"Raw attributes: {elem.attrib}")
                
                start_epoch = float(elem.attrib['Epoch'])
                pos = Position.from_string(elem.attrib['Pos'])
                start_idx = int(elem.attrib['InIdx'])
                end_idx = int(elem.attrib['OutIdx'])
                start_time = datetime.strptime(
                    elem.attrib['InStr'],
                    "%H:%M:%S.%f %m/%d/%Y"
                )
                
                # We don't have end_epoch or end_pos yet
                self._clips[name] = ClipInfo(
                    name=name,
                    start_epoch=start_epoch,
                    end_epoch=None, 
                    start_pos=pos,
                    end_pos=None,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    start_time=start_time
                )
                
                self.logger.debug(
                    f"Parsed {name}: start_epoch={start_epoch}, "
                    f"pos={pos.to_string()}, "
                    f"frame_range={start_idx}-{end_idx}"
                )
                
            except (KeyError, ValueError) as e:
                # Log warning but continue parsing other clips
                self.logger.warning(f"Warning: failed to parse clip element: {e}")
                continue
        
        self.logger.info(f"Successfully parsed {len(self._clips)} clips from manifest")
        for name, clip in self._clips.items():
            self.logger.info(
                f"Clip {name}: "
                f"start={clip.start_time}, "
                f"frames={clip.frame_count}, "
                f"pos={clip.start_pos.to_string()}"
            )
    
    def get_clip(self, name: str) -> ClipInfo | None:
        """Get information for a specific clip by name"""
        return self._clips.get(name)
    
    def get_clips(self) -> list[ClipInfo]:
        """Get list of all clips in temporal order"""
        return sorted(
            self._clips.values(),
            key=lambda x: x.start_epoch
        )
    
    def update_clip_status(self, name: str, status: ClipStatus) -> None:
        """Update the status of a clip after validation"""
        if clip := self._clips.get(name):
            clip.status = status
    
    def find_clip_for_timestamp(self, timestamp: float) -> ClipInfo | None:
        """Find the clip containing a given timestamp"""
        for clip in self._clips.values():
            if clip.start_epoch <= timestamp and (
                clip.end_epoch is None or timestamp <= clip.end_epoch
            ):
                return clip
        return None


def find_manifest(base_dir: Path) -> Path | None:
    """
    Find the COSM manifest XML file in the specified directory.
    Find the COSM manifest XML file in the specified directory.

    Args:
        base_dir: Directory Path object to search for manifest

    Returns:
        Path to manifest if exactly one is found, None otherwise

    Raises:
        ValueError: If multiple manifest files are found
    """
    logger = logging.getLogger(__name__)  # Get named logger

    # Log the state of base_dir as received
    logger.debug(f"Searching for manifest in received base_dir: '{base_dir}' (type: {type(base_dir)})")
    if not base_dir.is_dir():
        logger.error(f"The provided base_dir '{base_dir}' is not a valid directory.")
        return None

    # --- Simplified Search ---
    logger.debug(f"Attempting direct glob search: {base_dir}/*.xml")
    try:
        manifests = list(base_dir.glob("*.xml"))
        logger.debug(f"Direct glob found {len(manifests)} XML files: {manifests}")
    except Exception as e:
        # Log potential errors during glob, e.g., permission issues
        logger.error(f"Error during glob search in '{base_dir}': {e}")
        return None
    # --- End Simplified Search ---

    if not manifests:
        logger.warning(f"No *.xml manifest files found directly in {base_dir}")
        return None

    if len(manifests) > 1:
        logger.error(f"Multiple *.xml manifest files found directly in {base_dir}: {manifests}")
        raise ValueError(
            f"Multiple manifest files found in '{base_dir}': {', '.join(str(p.name) for p in manifests)}"
        )

    manifest_path = manifests[0]
    logger.info(f"Found manifest: {manifest_path}")
    return manifest_path
