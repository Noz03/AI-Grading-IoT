from fastapi.routing import APIRoute

from ai_grading_iot.api.dependencies import get_code_grader
from ai_grading_iot.api.v1.grading import router as grading_router
from ai_grading_iot.main import app


def test_grading_endpoint_registered():
    openapi_schema = app.openapi()

    assert "/api/v1/graders/code" in openapi_schema["paths"]


def test_grading_dependency_registered():
    grading_routes = [
        route
        for route in grading_router.routes
        if isinstance(route, APIRoute)
        and route.path == "/graders/code"
    ]

    assert len(grading_routes) == 1

    grading_route = grading_routes[0]

    dependencies = [
        dependency.call
        for dependency in grading_route.dependant.dependencies
    ]

    assert get_code_grader in dependencies
