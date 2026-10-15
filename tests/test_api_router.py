from ai_grading_iot.main import app


def test_api_routes_registered():

    openapi_schema = app.openapi()

    routes = set(openapi_schema["paths"].keys())

    expected_routes = {
        "/",
        "/api/v1/practices",
        "/api/v1/rubrics",
        "/api/v1/practices/{practice_id}/submissions",
        "/api/v1/submissions/my",
        "/api/v1/submissions/{submission_id}",
        "/api/v1/submissions/{submission_id}/images",
        "/api/v1/submissions/{submission_id}/images/{image_id}",
        "/api/v1/grading-results",
        "/api/v1/graders/code",
    }

    assert expected_routes.issubset(routes)


def test_api_versioning():

    openapi_schema = app.openapi()

    routes = set(openapi_schema["paths"].keys())

    api_routes = {
        route
        for route in routes
        if route != "/"
    }

    assert all(
        route.startswith("/api/v1/")
        for route in api_routes
    )
