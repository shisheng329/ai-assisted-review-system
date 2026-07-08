from __future__ import annotations

import pandas as pd
import pytest

from app.services.bertopic_service import BERTopicInputError, _normalize_params, _prepare_docs


def test_bertopic_input_validation_fails_before_worker() -> None:
    df = pd.DataFrame({"Title": ["Only one"], "Abstract": ["Not enough records"]})
    with pytest.raises(BERTopicInputError):
        _prepare_docs(df)


def test_bertopic_param_normalization_stays_within_sample_size() -> None:
    params = {
        "random_state": 42,
        "n_neighbors": 50,
        "n_components": 50,
        "min_topic_size": 50,
        "nr_topics": 50,
    }
    normalized = _normalize_params(params, doc_count=5)
    assert normalized["n_neighbors"] <= 4
    assert normalized["n_components"] <= 4
    assert normalized["min_topic_size"] <= 5
    assert normalized["nr_topics"] <= 5
