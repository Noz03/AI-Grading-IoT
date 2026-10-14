from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from ai_grading_iot.clients.groq_client import GroqClient
from ai_grading_iot.db.session import get_db
from ai_grading_iot.graders.code_grader import CodeGrader


DBSession = Annotated[
    Session,
    Depends(get_db),
]


def get_code_grader() -> CodeGrader:
    llm_client = GroqClient()

    return CodeGrader(
        llm_client=llm_client
    )
