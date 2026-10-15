"""Per-image observations and one rubric-grounded submission evaluation."""
import io
import json

from PIL import Image

from ai_grading_iot.schemas.vision import AggregateEvaluation, ImageEvaluation


class VisionGrader:
    def __init__(self, client, model: str, timeout: float):
        if not model or timeout <= 0:
            raise ValueError("VISION_GROQ_MODEL and positive timeout are required")
        self.client, self.model, self.timeout = client, model, timeout

    @staticmethod
    def _png(payload: bytes) -> bytes:
        with Image.open(io.BytesIO(payload)) as image:
            image.load()
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PNG")
            return buffer.getvalue()

    def grade(self, practice, rubric, images):
        criteria = set(rubric.criteria)
        image_ids = {item[0].image_id for item in images}
        observations = []
        for detections, original, annotated in images:
            prompt = ("Return JSON {image_id, observations:[{criterion,status,evidence}], limitations:[string]}. "
                      "Statuses: observed, not_observed, uncertain, not_applicable. Do not assign scores. "
                      "A missed detection does not prove absence. Inspect original and annotated image. "
                      f"image_id: {detections.image_id}. Practice requirements: "
                      f"{json.dumps(practice.requirements.model_dump(mode='json'))}. "
                      f"Hardware: {json.dumps([h.model_dump(mode='json') for h in practice.hardware])}. "
                      f"Vision rubric: {json.dumps(rubric.criteria)}. "
                      f"Detections: {detections.model_dump_json()}.")
            raw = self.client.generate_vision(prompt, [self._png(original), annotated],
                                              model=self.model, timeout=self.timeout)
            evaluation = ImageEvaluation.model_validate_json(raw)
            if evaluation.image_id != detections.image_id or any(
                item.criterion not in criteria for item in evaluation.observations
            ):
                raise ValueError("Invalid per-image Vision evaluation")
            observations.append(evaluation)
        prompt = ("Aggregate ALL per-image observations into ONE Vision score for the submission. "
                  "Return JSON {score: number|null, evidence_status: sufficient|insufficient, feedback: string, "
                  "criteria_feedback:[{criterion,status,feedback,image_ids:[uuid]}]}. "
                  "Use only approved criteria. A component seen in one angle counts once; unseen in another angle "
                  "does not prove absence. Do not average image scores. If essential evidence cannot be evaluated, "
                  "use insufficient and null score. No per-criterion weights are defined; explain the overall score "
                  "against the equally considered applicable criteria. "
                  f"Rubric: {json.dumps(rubric.criteria)}. "
                  f"Detections: {json.dumps([item[0].model_dump(mode='json') for item in images])}. "
                  f"Observations: {json.dumps([item.model_dump(mode='json') for item in observations])}.")
        raw = self.client.generate_vision(prompt, [], model=self.model, timeout=self.timeout)
        aggregate = AggregateEvaluation.model_validate_json(raw)
        if any(item.criterion not in criteria or not set(item.image_ids) <= image_ids
               for item in aggregate.criteria_feedback):
            raise ValueError("Invalid aggregated Vision evidence")
        if aggregate.evidence_status == "sufficient":
            if {item.criterion for item in aggregate.criteria_feedback} != criteria:
                raise ValueError("Sufficient evaluation requires feedback for every criterion")
            observed = {(item.criterion, evaluation.image_id, item.status)
                        for evaluation in observations for item in evaluation.observations}
            if any(not item.image_ids or not any(
                criterion == item.criterion and image_id in item.image_ids and status == item.status
                for criterion, image_id, status in observed
            ) for item in aggregate.criteria_feedback):
                raise ValueError("Aggregated Vision feedback lacks per-image evidence")
        return aggregate, observations
