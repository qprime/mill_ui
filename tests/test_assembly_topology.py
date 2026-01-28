import pytest

from assembly.topology import AssemblyTopology, FaceSpec, MatingEdge, MatingFeature
from assembly.primitives import box_topology, pyramid_topology, prism_topology


class TestFaceSpec:
    def test_edge_count(self):
        face = FaceSpec(
            name="rect",
            polygon=((0, 0), (100, 0), (100, 50), (0, 50)),
            thickness_mm=6.0,
        )
        assert face.edge_count == 4

    def test_edge_length(self):
        face = FaceSpec(
            name="rect",
            polygon=((0, 0), (100, 0), (100, 50), (0, 50)),
            thickness_mm=6.0,
        )
        assert face.edge_length(0) == 100.0
        assert face.edge_length(1) == 50.0
        assert face.edge_length(2) == 100.0
        assert face.edge_length(3) == 50.0

    def test_triangle_edge_count(self):
        face = FaceSpec(
            name="tri",
            polygon=((0, 0), (100, 0), (50, 86.6)),
            thickness_mm=6.0,
        )
        assert face.edge_count == 3


class TestAssemblyTopologyValidation:
    def test_validates_missing_face(self):
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
        }
        mating_edges = (
            MatingEdge(face_a="a", edge_index_a=0, face_b="b", edge_index_b=0),
        )
        topo = AssemblyTopology(faces=faces, mating_edges=mating_edges)
        with pytest.raises(ValueError, match="unknown face: b"):
            topo.validate()

    def test_validates_edge_index_out_of_range(self):
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
        }
        mating_edges = (
            MatingEdge(face_a="a", edge_index_a=10, face_b="b", edge_index_b=0),
        )
        topo = AssemblyTopology(faces=faces, mating_edges=mating_edges)
        with pytest.raises(ValueError, match="out of range"):
            topo.validate()

    def test_validates_edge_length_mismatch(self):
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (200, 0), (200, 50), (0, 50)), thickness_mm=6.0),
        }
        mating_edges = (
            MatingEdge(face_a="a", edge_index_a=0, face_b="b", edge_index_b=0),
        )
        topo = AssemblyTopology(faces=faces, mating_edges=mating_edges)
        with pytest.raises(ValueError, match="length mismatch"):
            topo.validate()

    def test_validates_missing_feature_face(self):
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
        }
        features = (
            MatingFeature(face="nonexistent", kind="dado", params={}),
        )
        topo = AssemblyTopology(faces=faces, mating_edges=(), mating_features=features)
        with pytest.raises(ValueError, match="unknown face: nonexistent"):
            topo.validate()


class TestPhaseAssignment:
    def test_simple_two_faces(self):
        faces = {
            "a": FaceSpec(name="a", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
            "b": FaceSpec(name="b", polygon=((0, 0), (100, 0), (100, 50), (0, 50)), thickness_mm=6.0),
        }
        mating_edges = (
            MatingEdge(face_a="a", edge_index_a=0, face_b="b", edge_index_b=0),
        )
        topo = AssemblyTopology(faces=faces, mating_edges=mating_edges)
        phases = topo.compute_phase_assignment()
        assert phases[("a", 0)] != phases[("b", 0)]

    def test_box_topology_is_bipartite(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
        )
        phases = topo.compute_phase_assignment()
        for edge in topo.mating_edges:
            phase_a = phases.get((edge.face_a, edge.edge_index_a))
            phase_b = phases.get((edge.face_b, edge.edge_index_b))
            if phase_a is not None and phase_b is not None:
                assert phase_a != phase_b, f"Mating edges must have different phases: {edge}"


class TestBoxTopology:
    def test_basic_finger_box_has_4_faces(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=False,
        )
        assert len(topo.faces) == 4
        assert "front" in topo.faces
        assert "back" in topo.faces
        assert "left_side" in topo.faces
        assert "right_side" in topo.faces

    def test_box_with_bottom_has_5_faces(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
        )
        assert len(topo.faces) == 5
        assert "bottom" in topo.faces

    def test_box_with_top_has_6_faces(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
            include_top=True,
        )
        assert len(topo.faces) == 6
        assert "top" in topo.faces

    def test_finger_joint_dimensions(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
            bottom_style="captured",
        )
        front = topo.faces["front"]
        left = topo.faces["left_side"]
        bottom = topo.faces["bottom"]

        assert front.edge_length(0) == 200.0
        assert front.edge_length(1) == 100 - 6 - 6

        assert left.edge_length(0) == 150 - 12
        assert left.edge_length(1) == 100 - 12

        assert bottom.edge_length(0) == 200 - 12
        assert bottom.edge_length(1) == 150 - 12

    def test_dado_bottom_creates_features(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
            bottom_style="dado",
            dado_inset_mm=10.0,
        )
        front_features = topo.features_for_face("front")
        assert len(front_features) == 1
        assert front_features[0].kind == "dado"
        assert front_features[0].params["position_from_edge_mm"] == 10.0

    def test_validates_successfully(self):
        topo = box_topology(
            width_mm=200,
            depth_mm=150,
            height_mm=100,
            thickness_mm=6,
            joinery="finger",
            include_bottom=True,
        )
        topo.validate()


class TestPyramidTopology:
    def test_pyramid_has_5_faces(self):
        topo = pyramid_topology(
            base_mm=100,
            slant_height_mm=80,
            thickness_mm=6,
        )
        assert len(topo.faces) == 5
        assert "base" in topo.faces
        for name in ["face_n", "face_e", "face_s", "face_w"]:
            assert name in topo.faces

    def test_triangular_faces(self):
        topo = pyramid_topology(
            base_mm=100,
            slant_height_mm=80,
            thickness_mm=6,
        )
        for name in ["face_n", "face_e", "face_s", "face_w"]:
            assert topo.faces[name].edge_count == 3


class TestPrismTopology:
    def test_triangular_prism(self):
        triangle = ((0, 0), (100, 0), (50, 86.6))
        topo = prism_topology(
            base_polygon=triangle,
            height_mm=50,
            thickness_mm=6,
        )
        assert "base" in topo.faces
        assert "top" in topo.faces
        assert "side_0" in topo.faces
        assert "side_1" in topo.faces
        assert "side_2" in topo.faces

    def test_hexagonal_prism(self):
        import math
        r = 50
        hexagon = tuple(
            (r * math.cos(math.radians(60 * i)), r * math.sin(math.radians(60 * i)))
            for i in range(6)
        )
        topo = prism_topology(
            base_polygon=hexagon,
            height_mm=100,
            thickness_mm=6,
        )
        assert len(topo.faces) == 8
