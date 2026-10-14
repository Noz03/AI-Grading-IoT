from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

import ai_grading_iot.models

from ai_grading_iot.db.base import Base


EXPECTED_TABLES = {
    "users",
    "courses",
    "course_teachers",
    "course_enrollments",
    "practices",
    "rubrics",
    "submissions",
    "grading_results",
}


def test_all_models_registered():
    tables = set(Base.metadata.tables.keys())

    assert tables == EXPECTED_TABLES


def test_foreign_keys():
    practice_table = Base.metadata.tables["practices"]
    submission_table = Base.metadata.tables["submissions"]
    grading_table = Base.metadata.tables["grading_results"]

    assert (
        "courses.id"
        in {
            fk.target_fullname
            for fk in practice_table.foreign_keys
        }
    )

    assert {
        fk.target_fullname
        for fk in submission_table.foreign_keys
    } == {
        "practices.id",
        "users.id",
    }

    assert {
        fk.target_fullname
        for fk in grading_table.foreign_keys
    } == {
        "submissions.id",
    }


def test_orm_relationships():
    configure_mappers()

    from ai_grading_iot.models import (
        Course,
        Practice,
        Submission,
    )

    assert "practices" in inspect(Course).relationships
    assert "course" in inspect(Practice).relationships
    assert "submissions" in inspect(Practice).relationships
    assert "grading_result" in inspect(Submission).relationships


def test_practice_columns():
    table = Base.metadata.tables["practices"]

    expected_columns = {
        "id",
        "course_id",
        "title",
        "description",
        "requirements",
        "environment",
        "hardware",
        "rubric_reference",
        "version",
        "status",
        "metadata",
    }

    assert expected_columns.issubset(
        set(table.columns.keys())
    )


def test_grading_result_nullable_scores():
    table = Base.metadata.tables["grading_results"]

    assert table.c.code_score.nullable
    assert table.c.data_score.nullable
    assert table.c.vision_score.nullable
    assert table.c.final_score.nullable
