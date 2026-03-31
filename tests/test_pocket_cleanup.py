from cam.model.machine import Machine
from cam.model.setup import Setup
from cam.model.stock import Stock
from cam.model.tool import Tool
from cam.moves import CommentMove, CutMove, Move
from cam.path.strategies import pocket_then_finish_profile
from cam.primitives import rectangle
from cam.transforms import Transform2D, place


def _create_test_setup():
    tool = Tool(name="6mm_flat", diameter=6.0, rpm=18000, feed_xy=2000, feed_z=300)
    stock = Stock(width=200.0, height=200.0, thickness=19.0)
    machine = Machine(name="default_grbl")
    return Setup(stock=stock, tool=tool, machine=machine, safe_z=5.0)


def _comments_containing(moves: list[Move], text: str) -> list[CommentMove]:
    return [m for m in moves if isinstance(m, CommentMove) and text in m.text]


def _shape_at_center():
    shape = rectangle(100, 100)
    return place(shape, Transform2D(tx=50, ty=50))


def test_pocket_cleanup_enabled_by_default():
    shape = _shape_at_center()
    setup = _create_test_setup()

    moves = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=True,
        pocket_strategy="raster",
    )

    assert len(moves) > 0
    assert len(_comments_containing(moves, "rough pocket")) > 0
    assert len(_comments_containing(moves, "finish profile pass")) > 0
    assert len(_comments_containing(moves, "no finish")) == 0
    cut_moves = [m for m in moves if isinstance(m, CutMove)]
    assert len(cut_moves) > 0


def test_pocket_cleanup_disabled():
    shape = _shape_at_center()
    setup = _create_test_setup()

    moves = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=False,
        pocket_strategy="raster",
    )

    assert len(moves) > 0
    assert len(_comments_containing(moves, "no finish")) > 0
    assert len(_comments_containing(moves, "finish profile pass")) == 0
    assert len(_comments_containing(moves, "rough pocket")) == 0


def test_pocket_cleanup_with_custom_offset():
    shape = _shape_at_center()
    setup = _create_test_setup()

    moves = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        cleanup_offset_mm=0.5,
        finish_perimeter=True,
        pocket_strategy="raster",
    )

    assert len(_comments_containing(moves, "rough pocket")) > 0
    assert len(_comments_containing(moves, "finish profile pass")) > 0
    assert len(_comments_containing(moves, "cleanup=0.5")) > 0


def test_finish_pass_produces_profile_moves():
    shape = _shape_at_center()
    setup = _create_test_setup()

    moves_with_finish = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=True,
        pocket_strategy="raster",
    )

    moves_without_finish = pocket_then_finish_profile(
        shape,
        setup,
        total_depth_mm=10.0,
        finish_perimeter=False,
        pocket_strategy="raster",
    )

    finish_comments = _comments_containing(moves_with_finish, "finish profile pass")
    no_finish_comments = _comments_containing(moves_without_finish, "finish profile pass")
    assert len(finish_comments) > 0
    assert len(no_finish_comments) == 0
