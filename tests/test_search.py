from pathlib import Path

import pytest

from objecttwin.imageio import ImageLoadError
from objecttwin.search import Progress, SearchCancelled, search_similar

from .conftest import FakeEmbedder, save_solid

RED, ORANGE, BLUE, GREEN = (250, 10, 10), (240, 120, 20), (10, 10, 250), (10, 200, 10)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    save_solid(root / "blue.tif", BLUE)
    save_solid(root / "sub" / "orange.tif", ORANGE)
    save_solid(root / "sub" / "deeper" / "red_copy.png", RED, size=(64, 48))
    save_solid(root / "green.tiff", GREEN)
    return root


def test_ranks_most_similar_first(tmp_path: Path, tree: Path, fake_embedder: FakeEmbedder) -> None:
    query = save_solid(tmp_path / "query.tif", RED)
    result = search_similar(query, tree, fake_embedder, top_k=10)

    names = [m.path.name for m in result.matches]
    assert names[:2] == ["red_copy.png", "orange.tif"]
    assert result.matches[0].score == pytest.approx(1.0)
    assert result.scanned == 4
    assert result.skipped == []
    scores = [m.score for m in result.matches]
    assert scores == sorted(scores, reverse=True)


def test_top_k_limits_results(tmp_path: Path, tree: Path, fake_embedder: FakeEmbedder) -> None:
    query = save_solid(tmp_path / "query.tif", RED)
    assert len(search_similar(query, tree, fake_embedder, top_k=2).matches) == 2


def test_query_inside_root_is_excluded(tree: Path, fake_embedder: FakeEmbedder) -> None:
    result = search_similar(tree / "blue.tif", tree, fake_embedder)
    assert all(m.path.name != "blue.tif" for m in result.matches)
    assert result.scanned == 3


def test_unreadable_files_are_skipped(
    tmp_path: Path, tree: Path, fake_embedder: FakeEmbedder
) -> None:
    (tree / "sub" / "broken.tif").write_bytes(b"garbage")
    query = save_solid(tmp_path / "query.tif", RED)
    result = search_similar(query, tree, fake_embedder)
    assert result.scanned == 4
    assert [p.name for p, _ in result.skipped] == ["broken.tif"]


def test_batching_and_progress(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    root = tmp_path / "many"
    for i in range(7):
        save_solid(root / f"img{i}.png", (i * 30, 0, 0))
    query = save_solid(tmp_path / "q.png", RED)
    events: list[Progress] = []

    result = search_similar(query, root, fake_embedder, batch_size=3, on_progress=events.append)

    assert result.scanned == 7
    assert fake_embedder.batch_sizes == [1, 3, 3, 1]  # query, then batches
    assert events[0] == Progress(0, 7)
    assert events[-1] == Progress(7, 7)
    assert [e.done for e in events] == [0, 3, 6, 7]


def test_cancel(tmp_path: Path, tree: Path, fake_embedder: FakeEmbedder) -> None:
    query = save_solid(tmp_path / "query.tif", RED)
    with pytest.raises(SearchCancelled):
        search_similar(query, tree, fake_embedder, should_cancel=lambda: True)


def test_empty_folder(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    (tmp_path / "empty").mkdir()
    query = save_solid(tmp_path / "query.tif", RED)
    result = search_similar(query, tmp_path / "empty", fake_embedder)
    assert result.matches == []
    assert result.scanned == 0


def test_bad_query_raises(tmp_path: Path, tree: Path, fake_embedder: FakeEmbedder) -> None:
    with pytest.raises(ImageLoadError):
        search_similar(tmp_path / "missing.tif", tree, fake_embedder)


def test_bad_root_raises(tmp_path: Path, fake_embedder: FakeEmbedder) -> None:
    query = save_solid(tmp_path / "query.tif", RED)
    with pytest.raises(NotADirectoryError):
        search_similar(query, tmp_path / "nope", fake_embedder)
