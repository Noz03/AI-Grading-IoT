import os
import pytest
from dotenv import load_dotenv

from ai_grading_iot.clients.groq_client import GroqClient

load_dotenv()


@pytest.mark.skipif(
    not os.getenv("GROQ_API_KEY"),
    reason="Bỏ qua integration test vì chưa cấu hình GROQ_API_KEY trong .env",
)
def test_groq_client_live_connection():
    client = GroqClient()
    prompt = 'Return a valid JSON object with format: {"status": "ok", "provider": "groq"}'

    response_text = client.generate(prompt)

    assert isinstance(response_text, str)
    assert len(response_text) > 0
    assert "status" in response_text
    assert "groq" in response_text
