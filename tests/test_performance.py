"""Performance benchmarks and stress tests for the domain/generator system.

Stage 7: Production Readiness - Performance Testing

This module establishes baselines and validates performance for:
- Complex domain operations (many vertices, holes)
- Large domain operations (scaling behavior)
- Generator throughput (items per second)
- Memory usage patterns

Usage:
    # Run performance validation tests (default, CI-safe)
    PYTHONPATH=. python3 -m tests.test_performance

    # Run full benchmarks with stress tests (local development only)
    PYTHONPATH=. python3 -m tests.test_performance --full

    # Skip in CI by setting environment variable
    SKIP_PERF_TESTS=1 PYTHONPATH=. python3 -m tests.test_performance

Performance thresholds:
    Thresholds are set at 2-3x expected performance to avoid flaky failures
    on different hardware. These tests validate "not catastrophically slow"
    rather than precise timing. For accurate profiling, use --full locally.

    - Simple rectangle operations: < 1ms (actual ~0.07ms)
    - Complex polygon (100 vertices): < 10ms (actual ~0.12ms)
    - Domain with 10 holes: < 50ms (actual ~1.2ms)
    - Wave generator (1000+ points): < 100ms (actual ~56ms)
    - Full pipeline (domain -> AST -> IR): < 200ms (actual ~0.2ms)

Note:
    These tests are designed to catch performance regressions, not to
    enforce strict timing requirements. If running in CI, consider using
    SKIP_PERF_TESTS=1 to skip, or accept occasional flaky failures on
    heavily loaded CI runners.
"""

from __future__ import annotations

import math
import sys
import time
from collections.abc import Callable
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domains import Domain
from generators import (
    BeadParams,
    FlatPocketParams,
    GridParams,
    ProfileParams,
    WaveParams,
    bead_generator,
    flat_pocket_generator,
    grid_generator,
    profile_generator,
    wave_generator,
)
from layout_ast.layout import LayoutAST, Sheet

# =============================================================================
# Benchmark Utilities
# =============================================================================


class BenchmarkResult:
    """Result of a benchmark run."""

    def __init__(self, name: str, iterations: int, total_time: float):
        self.name = name
        self.iterations = iterations
        self.total_time = total_time
        self.avg_time = total_time / iterations
        self.ops_per_sec = iterations / total_time if total_time > 0 else float("inf")

    def __str__(self) -> str:
        if self.avg_time < 0.001:
            time_str = f"{self.avg_time * 1000000:.1f}µs"
        elif self.avg_time < 1:
            time_str = f"{self.avg_time * 1000:.2f}ms"
        else:
            time_str = f"{self.avg_time:.3f}s"
        return f"{self.name}: {time_str}/op ({self.ops_per_sec:.1f} ops/s)"


def benchmark(
    name: str,
    func: Callable[[], None],
    iterations: int = 100,
    warmup: int = 5,
) -> BenchmarkResult:
    """Run a benchmark and return results.

    Args:
        name: Benchmark name
        func: Function to benchmark (no arguments)
        iterations: Number of iterations to run
        warmup: Number of warmup iterations (not timed)

    Returns:
        BenchmarkResult with timing data
    """
    # Warmup
    for _ in range(warmup):
        func()

    # Timed runs
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    end = time.perf_counter()

    return BenchmarkResult(name, iterations, end - start)


# =============================================================================
# Domain Construction Benchmarks
# =============================================================================


def bench_domain_rectangle_construction():
    """Benchmark simple rectangle domain construction."""

    def func():
        Domain.from_rectangle(100, 100, center=(50, 50))

    return benchmark("Domain.from_rectangle", func, iterations=1000)


def bench_domain_polygon_construction():
    """Benchmark polygon domain construction with many vertices."""
    # Create a polygon with 100 vertices (approximates a circle)
    vertices = []
    for i in range(100):
        angle = 2 * math.pi * i / 100
        x = 50 + 45 * math.cos(angle)
        y = 50 + 45 * math.sin(angle)
        vertices.append((x, y))

    def func():
        Domain.from_polygon(vertices)

    return benchmark("Domain.from_polygon (100 vertices)", func, iterations=100)


def bench_domain_with_holes_construction():
    """Benchmark domain construction with multiple holes."""
    outer = [(0, 0), (200, 0), (200, 200), (0, 200)]
    holes = []
    # Create 10 small square holes in a grid
    for row in range(2):
        for col in range(5):
            x = 20 + col * 35
            y = 50 + row * 100
            holes.append([(x, y), (x + 20, y), (x + 20, y + 20), (x, y + 20)])

    def func():
        Domain.from_polygon(outer, holes=holes)

    return benchmark("Domain.from_polygon (10 holes)", func, iterations=100)


# =============================================================================
# Domain Operation Benchmarks
# =============================================================================


def bench_domain_inset():
    """Benchmark inset operation."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))

    def func():
        domain.inset(10)

    return benchmark("Domain.inset", func, iterations=500)


def bench_domain_offset():
    """Benchmark offset operation."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))

    def func():
        domain.offset(10)

    return benchmark("Domain.offset", func, iterations=500)


def bench_domain_subtract():
    """Benchmark subtract operation."""
    outer = Domain.from_rectangle(100, 100, center=(50, 50))
    inner = Domain.from_rectangle(40, 40, center=(50, 50))

    def func():
        outer.subtract(inner)

    return benchmark("Domain.subtract", func, iterations=500)


def bench_domain_intersect():
    """Benchmark intersect operation."""
    d1 = Domain.from_rectangle(100, 100, center=(50, 50))
    d2 = Domain.from_rectangle(100, 100, center=(75, 75))

    def func():
        d1.intersect(d2)

    return benchmark("Domain.intersect", func, iterations=500)


def bench_complex_domain_inset():
    """Benchmark inset on complex polygon."""
    # Create irregular polygon
    vertices = [
        (0, 0),
        (100, 0),
        (100, 50),
        (80, 50),
        (80, 100),
        (100, 100),
        (100, 150),
        (0, 150),
        (0, 100),
        (20, 100),
        (20, 50),
        (0, 50),
    ]
    domain = Domain.from_polygon(vertices)

    def func():
        domain.inset(5)

    return benchmark("Complex domain inset", func, iterations=200)


# =============================================================================
# Generator Benchmarks
# =============================================================================


def bench_flat_pocket_generator():
    """Benchmark flat pocket generator."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = FlatPocketParams(depth_mm=6.0)

    def func():
        flat_pocket_generator(domain, params)

    return benchmark("flat_pocket_generator", func, iterations=500)


def bench_profile_generator():
    """Benchmark profile generator."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = ProfileParams(side="outside", depth="through")

    def func():
        profile_generator(domain, params)

    return benchmark("profile_generator", func, iterations=500)


def bench_wave_generator():
    """Benchmark wave generator."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    params = WaveParams(
        amplitude_mm=10.0,
        wavelength_mm=20.0,
        depth_mm=3.0,
    )

    def func():
        wave_generator(domain, params)

    return benchmark("wave_generator", func, iterations=100)


def bench_grid_generator():
    """Benchmark grid generator."""
    domain = Domain.from_rectangle(200, 100, center=(100, 50))
    params = GridParams(
        spacing_x_mm=20.0,
        spacing_y_mm=20.0,
        line_width_mm=3.0,
        depth_mm=2.0,
    )

    def func():
        grid_generator(domain, params)

    return benchmark("grid_generator", func, iterations=100)


def bench_bead_generator():
    """Benchmark bead generator."""
    domain = Domain.from_rectangle(100, 100, center=(50, 50))
    params = BeadParams(width_mm=6.0, depth_mm=3.0, offset_mm=10.0)

    def func():
        bead_generator(domain, params)

    return benchmark("bead_generator", func, iterations=200)


# =============================================================================
# End-to-End Pipeline Benchmarks
# =============================================================================


def bench_shaker_door_pipeline():
    """Benchmark a complete Shaker door from domains to AST."""

    def func():
        # Create domains
        outer = Domain.from_rectangle(400, 600, center=(200, 300))
        panel_result = outer.inset(50)
        panel = panel_result.domains[0]

        # Generate items
        profile_items = profile_generator(
            outer,
            ProfileParams(side="outside", depth="through"),
        )
        pocket_items = flat_pocket_generator(
            panel,
            FlatPocketParams(depth_mm=6.0),
        )

        # Build AST
        ast = LayoutAST(
            sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
            items=tuple(profile_items + pocket_items),
        )
        return ast

    return benchmark("Shaker door (Domain -> AST)", func, iterations=200)


def bench_decorated_panel_pipeline():
    """Benchmark decorated panel with wave pattern."""

    def func():
        # Create domains
        outer = Domain.from_rectangle(300, 200, center=(150, 100))

        # Generate profile
        profile_items = profile_generator(
            outer,
            ProfileParams(side="outside", depth="through"),
        )

        # Generate wave pattern
        wave_items = wave_generator(
            outer,
            WaveParams(amplitude_mm=8.0, wavelength_mm=25.0, depth_mm=2.0),
        )

        # Build AST
        ast = LayoutAST(
            sheet=Sheet(width_mm=350, height_mm=250, thickness_mm=19, margin_mm=0.0),
            items=tuple(profile_items + wave_items),
        )
        return ast

    return benchmark("Decorated panel (wave pattern)", func, iterations=100)


def bench_full_pipeline_with_ir():
    """Benchmark complete pipeline including IR conversion."""
    from adapters.ast_to_removal import ast_to_removal_intents

    def func():
        # Domain composition
        outer = Domain.from_rectangle(400, 600, center=(200, 300))
        panel = outer.inset(50).domains[0]

        # Generate items
        items = []
        items.extend(profile_generator(outer, ProfileParams(side="outside", depth="through")))
        items.extend(flat_pocket_generator(panel, FlatPocketParams(depth_mm=6.0)))

        # Build AST
        ast = LayoutAST(
            sheet=Sheet(width_mm=450, height_mm=650, thickness_mm=19, margin_mm=0.0),
            items=tuple(items),
        )

        # Convert to IR
        warnings = []
        intents = ast_to_removal_intents(ast, warnings=warnings)
        return intents

    return benchmark("Full pipeline (Domain -> AST -> IR)", func, iterations=100)


# =============================================================================
# Stress Tests
# =============================================================================


def stress_test_many_vertices():
    """Stress test: domain with very many vertices."""
    # 1000-vertex polygon approximating a circle
    vertices = []
    for i in range(1000):
        angle = 2 * math.pi * i / 1000
        x = 500 + 450 * math.cos(angle)
        y = 500 + 450 * math.sin(angle)
        vertices.append((x, y))

    start = time.perf_counter()
    domain = Domain.from_polygon(vertices)
    construction_time = time.perf_counter() - start

    start = time.perf_counter()
    result = domain.inset(10)
    inset_time = time.perf_counter() - start

    return {
        "name": "1000-vertex polygon",
        "construction_time_ms": construction_time * 1000,
        "inset_time_ms": inset_time * 1000,
        "result_vertices": len(result.domains[0].outer_boundary) if not result.is_empty else 0,
    }


def stress_test_many_holes():
    """Stress test: domain with many holes."""
    outer = [(0, 0), (500, 0), (500, 500), (0, 500)]
    holes = []
    # 25 holes in a 5x5 grid
    for row in range(5):
        for col in range(5):
            x = 30 + col * 90
            y = 30 + row * 90
            holes.append([(x, y), (x + 40, y), (x + 40, y + 40), (x, y + 40)])

    start = time.perf_counter()
    domain = Domain.from_polygon(outer, holes=holes)
    construction_time = time.perf_counter() - start

    start = time.perf_counter()
    result = domain.inset(5)
    inset_time = time.perf_counter() - start

    return {
        "name": "25 holes",
        "construction_time_ms": construction_time * 1000,
        "inset_time_ms": inset_time * 1000,
        "result_holes": len(result.domains[0].inner_boundaries) if not result.is_empty else 0,
    }


def stress_test_chained_operations():
    """Stress test: many chained domain operations."""
    start = time.perf_counter()

    domain = Domain.from_rectangle(1000, 1000, center=(500, 500))

    # Chain of operations
    for _ in range(10):
        result = domain.inset(20)
        if result.is_empty:
            break
        domain = result.domains[0]

    total_time = time.perf_counter() - start

    return {
        "name": "10 chained insets",
        "total_time_ms": total_time * 1000,
        "final_area_mm2": domain.area_mm2,
    }


def stress_test_dense_grid():
    """Stress test: very dense grid pattern."""
    domain = Domain.from_rectangle(500, 500, center=(250, 250))
    params = GridParams(
        spacing_x_mm=5.0,  # Very dense
        spacing_y_mm=5.0,
        line_width_mm=2.0,
        depth_mm=2.0,
    )

    start = time.perf_counter()
    items = grid_generator(domain, params)
    total_time = time.perf_counter() - start

    return {
        "name": "Dense grid (5mm spacing, 500x500)",
        "total_time_ms": total_time * 1000,
        "item_count": len(items),
    }


def stress_test_fine_wave():
    """Stress test: wave pattern with many samples."""
    domain = Domain.from_rectangle(500, 300, center=(250, 150))
    params = WaveParams(
        amplitude_mm=5.0,
        wavelength_mm=10.0,  # Many waves
        depth_mm=2.0,
        tool_width_mm=2.0,  # Dense spacing
    )

    start = time.perf_counter()
    items = wave_generator(domain, params)
    total_time = time.perf_counter() - start

    return {
        "name": "Fine wave (10mm wavelength, 2mm spacing)",
        "total_time_ms": total_time * 1000,
        "item_count": len(items),
    }


# =============================================================================
# Test Runner
# =============================================================================


def run_benchmarks():
    """Run all benchmarks and display results."""
    print("=" * 70)
    print("Domain/Generator Performance Benchmarks")
    print("=" * 70)

    benchmarks = [
        (
            "Domain Construction",
            [
                bench_domain_rectangle_construction,
                bench_domain_polygon_construction,
                bench_domain_with_holes_construction,
            ],
        ),
        (
            "Domain Operations",
            [
                bench_domain_inset,
                bench_domain_offset,
                bench_domain_subtract,
                bench_domain_intersect,
                bench_complex_domain_inset,
            ],
        ),
        (
            "Generators",
            [
                bench_flat_pocket_generator,
                bench_profile_generator,
                bench_wave_generator,
                bench_grid_generator,
                bench_bead_generator,
            ],
        ),
        (
            "End-to-End Pipelines",
            [
                bench_shaker_door_pipeline,
                bench_decorated_panel_pipeline,
                bench_full_pipeline_with_ir,
            ],
        ),
    ]

    for category, funcs in benchmarks:
        print(f"\n{category}:")
        print("-" * 50)
        for func in funcs:
            result = func()
            print(f"  {result}")

    print("\n" + "=" * 70)
    print("Stress Tests")
    print("=" * 70)

    stress_tests = [
        stress_test_many_vertices,
        stress_test_many_holes,
        stress_test_chained_operations,
        stress_test_dense_grid,
        stress_test_fine_wave,
    ]

    for test in stress_tests:
        result = test()
        print(f"\n{result['name']}:")
        for key, value in result.items():
            if key != "name":
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("Benchmark complete")
    print("=" * 70)


def run_tests():
    """Run performance tests with pass/fail criteria."""
    print("Running performance validation tests...")
    print("-" * 60)

    passed = 0
    failed = 0

    # Define performance thresholds (in seconds)
    thresholds = [
        ("Rectangle construction", bench_domain_rectangle_construction, 0.001),  # 1ms
        ("Polygon 100 vertices", bench_domain_polygon_construction, 0.010),  # 10ms
        ("Domain with 10 holes", bench_domain_with_holes_construction, 0.050),  # 50ms
        ("Inset operation", bench_domain_inset, 0.005),  # 5ms
        ("Subtract operation", bench_domain_subtract, 0.005),  # 5ms
        ("Flat pocket generator", bench_flat_pocket_generator, 0.005),  # 5ms
        ("Profile generator", bench_profile_generator, 0.005),  # 5ms
        ("Wave generator", bench_wave_generator, 0.100),  # 100ms
        ("Grid generator", bench_grid_generator, 0.100),  # 100ms
        ("Full pipeline", bench_full_pipeline_with_ir, 0.200),  # 200ms
    ]

    for name, bench_func, threshold in thresholds:
        result = bench_func()
        if result.avg_time <= threshold:
            print(f"PASS: {name} ({result.avg_time * 1000:.2f}ms <= {threshold * 1000:.0f}ms)")
            passed += 1
        else:
            print(f"FAIL: {name} ({result.avg_time * 1000:.2f}ms > {threshold * 1000:.0f}ms)")
            failed += 1

    print("-" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    import os
    import sys

    # Allow skipping in CI via environment variable
    if os.environ.get("SKIP_PERF_TESTS", "").lower() in ("1", "true", "yes"):
        print("SKIP_PERF_TESTS is set, skipping performance tests")
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        run_benchmarks()
    else:
        success = run_tests()
        sys.exit(0 if success else 1)
