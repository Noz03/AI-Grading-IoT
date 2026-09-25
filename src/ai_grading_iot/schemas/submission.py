from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class Submission(BaseModel):
    id: UUID = Field(
        default_factory=uuid4,
        description="Định danh duy nhất của Submission (UUID)",
    )
    practice_id: UUID = Field(
        ...,
        description="Định danh bài thực hành (Practice ID)",
    )
    student_id: UUID = Field(
        ...,
        description="Định danh sinh viên nộp bài (Student ID)",
    )
    description: str = Field(
        ...,
        description="Nội dung mô tả hoặc báo cáo bài làm của sinh viên",
    )
    code: str = Field(
        ...,
        description="Toàn bộ source code sinh viên nộp",
    )
    images: list[str] = Field(
        default_factory=list,
        description="Danh sách đường dẫn, URL hoặc key hình ảnh chụp kit thực tế",
    )
    status: SubmissionStatus = Field(
        default=SubmissionStatus.DRAFT,
        description="Trạng thái bài nộp (draft hoặc submitted)",
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Thời điểm bài được submit; null khi đang ở trạng thái draft",
    )
