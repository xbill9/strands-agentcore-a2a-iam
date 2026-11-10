import os

from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Bedrock model through the runtime's execution role (no API keys).

    Model IDs must be inference-profile IDs (us./global. prefix).
    """
    return BedrockModel(model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0"))
