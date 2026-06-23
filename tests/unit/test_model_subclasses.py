"""Unit tests for the concrete model subclasses (MACK, MCBound, JPCP).

These cover the offline-reachable surface: construction/default injection,
embedding transforms, config builders (which only assemble params, no data
load), MACK's KMeans label transform, and the save/load round-trip on an
untrained estimator. The ``get_test_config`` valid branches and the SB
(SentenceTransformer) embedding path require network/large downloads and are
intentionally not exercised here.
"""

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("sklearn")
pytest.importorskip("xgboost")
pytest.importorskip("sentence_transformers")

from seanergys_modelzoo.models.common.seanergys_model import (  # noqa: E402
    SeanergysModelTask,
)
from seanergys_modelzoo.models.tasks.performance_prediction.mack.mack_model import (  # noqa: E402
    MACK,
    Embedding as MackEmbedding,
)
from seanergys_modelzoo.models.tasks.performance_prediction.mcbound.mcbound_model import (  # noqa: E402
    MCBound,
    Embedding as McbEmbedding,
)
from seanergys_modelzoo.models.tasks.power_consumption_prediction.jpcp.jpcp_model import (  # noqa: E402
    JPCP,
    Embedding as JpcpEmbedding,
)


# ---------------------------------------------------------------------------
# Construction / default injection
# ---------------------------------------------------------------------------


def test_mack_defaults():
    m = MACK()
    assert m.task_type == SeanergysModelTask.CLASSIFICATION
    assert m.kmeans_flops is not None
    assert m.kmeans_memory_bw is not None


def test_mcbound_defaults():
    m = MCBound()
    assert m.task_type == SeanergysModelTask.CLASSIFICATION


def test_jpcp_defaults():
    m = JPCP()
    assert m.task_type == SeanergysModelTask.REGRESSION


# ---------------------------------------------------------------------------
# transform_embeddings / embedding_parsing
# ---------------------------------------------------------------------------


def test_embedding_none_passthrough():
    feats = np.array([[1.0, 2.0], [3.0, 4.0]])
    assert np.array_equal(MACK().transform_embeddings(feats), feats)
    assert np.array_equal(
        MCBound(embedding_type=McbEmbedding.NONE).transform_embeddings(feats), feats
    )
    assert np.array_equal(
        JPCP(embedding_type=JpcpEmbedding.NONE).transform_embeddings(feats), feats
    )


def test_embedding_int_label_encodes():
    feats = np.array([["a", "x"], ["b", "x"], ["a", "y"]])
    out = MACK(embedding_type=MackEmbedding.INT).transform_embeddings(feats)
    assert out.shape == (3, 2)
    # MCBound/JPCP require fit=True for the encoder to be fitted first
    out_mcb = MCBound(embedding_type=McbEmbedding.INT).transform_embeddings(
        feats, fit=True
    )
    assert out_mcb.shape == (3, 2)
    out_jpcp = JPCP(embedding_type=JpcpEmbedding.INT).transform_embeddings(
        feats, fit=True
    )
    assert out_jpcp.shape == (3, 2)


def test_embedding_parsing_returns_384_vector():
    arr = MACK().embedding_parsing([np.arange(384)])
    assert arr.shape == (384,)


# ---------------------------------------------------------------------------
# MACK-specific: transform_kmeans, parse_job_script
# ---------------------------------------------------------------------------


def test_mack_transform_kmeans_fit():
    m = MACK(k_flops=2, k_memory_bw=2)
    flops = np.array([1.0, 1.1, 10.0, 10.2])
    memory_bw = np.array([2.0, 2.1, 20.0, 20.5])
    labels = m.transform_kmeans(flops, memory_bw, fit=True)
    assert len(labels) == 4
    assert all(isinstance(t, tuple) and len(t) == 2 for t in labels)


def test_mack_parse_job_script():
    script = "#SBATCH stuff\nmodule load gcc\nrun --flag # comment\n"
    out = MACK().parse_job_script(script)
    # Comment lines (starting with '#') and inline '# comment' trailers are stripped.
    assert "#SBATCH" not in out
    assert "comment" not in out
    # NOTE: characterizes a known off-by-one — for lines without '#', idx stays -1
    # so e[:-1] drops the final character ("gcc" -> "gc") and lines are concatenated
    # without separators. Captured here so a future fix is a deliberate change.
    assert out == "module load gcrun --flag "


# ---------------------------------------------------------------------------
# get_train_config (params only — no data load)
# ---------------------------------------------------------------------------


def test_mack_get_train_config_fdata():
    cfg = MACK.get_train_config("f-data")
    model, ds_cls, (ds_params, dl_params) = cfg["f-data"]
    assert isinstance(model, MACK)
    assert ds_cls.__name__ == "FDataDataset"
    assert dl_params.batch_size == 1


def test_mack_get_train_config_invalid():
    with pytest.raises(Exception):
        MACK.get_train_config("nope")


def test_mcbound_get_train_config_fdata():
    cfg = MCBound.get_train_config("f-data")
    model, ds_cls, _ = cfg["f-data"]
    assert isinstance(model, MCBound)


def test_mcbound_get_train_config_invalid():
    with pytest.raises(Exception):
        MCBound.get_train_config("nope")


def test_jpcp_get_train_config_fdata():
    cfg = JPCP.get_train_config("f-data")
    model, ds_cls, _ = cfg["f-data"]
    assert isinstance(model, JPCP)
    assert ds_cls.__name__ == "FDataDataset"


def test_jpcp_get_train_config_pm100():
    """The non-f-data branch builds the PM100 config without any data load."""
    cfg = JPCP.get_train_config("pm100")
    model, ds_cls, (ds_params, dl_params) = cfg["pm100"]
    assert isinstance(model, JPCP)
    assert ds_cls.__name__ == "PM100Dataset"
    assert "num_nodes_req_cat" in ds_params.input_features


# ---------------------------------------------------------------------------
# get_test_config invalid branches (valid branches need Zenodo)
# ---------------------------------------------------------------------------


def test_get_test_config_invalid_dataset_raises():
    with pytest.raises(Exception):
        MACK.get_test_config(MACK(), "nope")
    with pytest.raises(Exception):
        MCBound.get_test_config(MCBound(), "nope")
    with pytest.raises(Exception):
        JPCP.get_test_config(JPCP(), "nope")


# ---------------------------------------------------------------------------
# save / load round-trip (untrained estimator)
# ---------------------------------------------------------------------------


def test_mcbound_save_load_roundtrip(tmp_path):
    m = MCBound()
    save_dir = tmp_path / "mcb"
    assert m.save(save_dir) is True
    loaded = MCBound.load(save_dir)
    assert isinstance(loaded, MCBound)
    assert loaded.is_trained is True


def test_jpcp_save_load_roundtrip(tmp_path):
    m = JPCP()
    save_dir = tmp_path / "jpcp"
    assert m.save(save_dir) is True
    loaded = JPCP.load(save_dir)
    assert isinstance(loaded, JPCP)


def test_mack_save_load_roundtrip(tmp_path):
    m = MACK()
    save_dir = tmp_path / "mack"
    assert m.save(save_dir) is True
    loaded = MACK.load(save_dir)
    assert isinstance(loaded, MACK)
    assert loaded.kmeans_flops is not None


def test_load_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        MCBound.load(tmp_path / "nope")
    with pytest.raises(FileNotFoundError):
        MACK.load(tmp_path / "nope")
    with pytest.raises(FileNotFoundError):
        JPCP.load(tmp_path / "nope")
