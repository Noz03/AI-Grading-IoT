import json
from ai_grading_iot.clients.llm_client import LLMClient
from ai_grading_iot.schemas.code_evaluation import CodeEvaluation
from ai_grading_iot.schemas.grading_result import GradingResult
from ai_grading_iot.schemas.practice import Practice
from ai_grading_iot.schemas.rubric import Rubric, RubricType
from ai_grading_iot.schemas.submission import Submission


class CodeGrader:
    """Điều phối toàn bộ quá trình chấm điểm mã nguồn bằng LLM."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def grade(
        self,
        practice: Practice,
        rubric: Rubric,
        submission: Submission,
    ) -> tuple[GradingResult, CodeEvaluation]:
        # 1. Validate Rubric (Mục 10)
        if rubric.type != RubricType.CODE:
            raise ValueError(f"CodeGrader chỉ hỗ trợ RubricType.CODE, nhận được: {rubric.type}")

        if not rubric.criteria:
            raise ValueError("Rubric criteria không được rỗng.")

        # 2. Validate Submission (Mục 11)
        if not submission.code or not submission.code.strip():
            raise ValueError("Submission code không được để trống.")

        # 3. Build Prompt động (Mục 12, 13)
        prompt = self._build_prompt(practice, rubric, submission)

        # 4. Gửi tới LLM Client
        try:
            raw_response = self.llm_client.generate(prompt)
        except Exception as e:
            raise RuntimeError(f"Lỗi khi gọi LLM Client: {str(e)}") from e

        # 5. Parse JSON & Validate CodeEvaluation Schema (Mục 14)
        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned.removeprefix("```").removesuffix("```").strip()

            parsed_data = json.loads(cleaned)
            evaluation = CodeEvaluation.model_validate(parsed_data)
        except Exception as e:
            raise ValueError(f"Không thể parse phản hồi từ LLM thành CodeEvaluation: {str(e)}") from e

        # 6. Validate đầy đủ Criterion so với Rubric (Mục 15)
        returned_map = {item.criterion.strip().lower(): item for item in evaluation.criteria_results}
        for criterion in rubric.criteria:
            crit_key = criterion.strip().lower()
            if crit_key not in returned_map:
                raise ValueError(
                    f"LLM trả về thiếu tiêu chí đánh giá bắt buộc: '{criterion}'"
                )

        # 7. Tính Weighted Code Score chính thức (Mục 16)
        num_criteria = len(rubric.criteria)
        weight_per_crit = (rubric.weight / num_criteria) if num_criteria > 0 else 0

        calculated_score = sum(
            returned_map[crit.strip().lower()].score * (weight_per_crit / rubric.weight)
            for crit in rubric.criteria
        )
        calculated_score = round(calculated_score, 2)

        # 8. Đóng gói GradingResult (Mục 17)
        grading_result = GradingResult(
            submission_id=submission.id,
            code_score=calculated_score,
            data_score=None,
            vision_score=0.0,
            final_score=calculated_score,
        )

        return grading_result, evaluation

    def _build_prompt(self, practice: Practice, rubric: Rubric, submission: Submission) -> str:
        tasks_text = "\n".join([f"- [{t.id}] {t.description}" for t in practice.requirements.tasks])
        constraints_text = "\n".join([f"- {c}" for c in practice.requirements.constraints])
        criteria_text = "\n".join([f"- {crit}" for crit in rubric.criteria])

        return f"""You are an automated grading system evaluating IoT source code.
### PRACTICE CONTEXT
Title: {practice.title}
Description: {practice.description}
Board: {practice.environment.board} | Framework: {practice.environment.framework} | Language: {practice.environment.language}

### PRACTICE REQUIREMENTS
Objective: {practice.requirements.objective}
Tasks:
{tasks_text}
Constraints:
{constraints_text}

### CODE RUBRIC CRITERIA
Each criterion must be evaluated independently with a score from 0 to 100:
{criteria_text}

### STUDENT CODE
{submission.code}
### EVALUATION RULES
1. Evaluate EVERY criterion listed above. Do not skip or create new criteria.
2. Score each criterion between 0 and 100.
3. Provide constructive feedback for each criterion.
4. Output strictly valid JSON matching this schema:
{{
  "criteria_results": [
    {{
      "criterion": "Exact criterion string",
      "score": 85.0,
      "feedback": "Detailed reason"
    }}
  ],
  "code_score": 85.0,
  "overall_feedback": "Overall summary"
}}
"""
