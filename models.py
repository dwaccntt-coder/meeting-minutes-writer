from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MeetingMetadata:
    title: str = ""
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    attendees: str = ""
    meeting_type: str = "일반 회의"
    location: str = ""
    num_speakers: int = 0
    capture_system_audio: bool = False

    MEETING_TYPES = ["일반 회의", "스탠드업", "브레인스토밍", "리뷰", "기타"]
