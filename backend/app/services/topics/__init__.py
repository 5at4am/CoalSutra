"""Topic modeling & word-cloud module (one of the three consumer modules)."""

from app.services.topics.topic_model import TopicLabels, run_topic_model

__all__ = [
    "TopicLabels",
    "run_topic_model",
]