from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Interface trừu tượng cho các LLM Client."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Gửi prompt tới LLM và nhận chuỗi phản hồi thô (raw response text).

        Args:
            prompt: Nội dung prompt gửi đi.

        Returns:
            Chuỗi text kết quả trả về từ LLM.
        """
        pass
