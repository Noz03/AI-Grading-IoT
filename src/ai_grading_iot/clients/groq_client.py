import os
from groq import Groq
from ai_grading_iot.clients.llm_client import LLMClient


class GroqClient(LLMClient):
    """Client kết nối tới Groq API thông qua Groq Python SDK."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY không được tìm thấy. Vui lòng cấu hình trong file .env."
            )

        self.model_name = model_name or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        self.client = Groq(api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        """Gửi prompt tới Groq và nhận kết quả JSON string."""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are an automated grading system. You must return only a valid JSON object matching the requested schema without any markdown formatting or extra text.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("Groq API trả về phản hồi rỗng.")

        return content
