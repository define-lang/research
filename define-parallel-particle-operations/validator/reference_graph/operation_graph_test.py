"""Test Operation Graph node identity independently of Define source.

Dependency semantics belong in Define-source integration tests, not in
manually constructed graphs.
"""

from __future__ import annotations

from define.compiler import ast
from define.compiler.validator.reference_graph import operation_graph_model


def test_operation_nodes_use_identity_equality():
    location = ast.start_of_file_location()
    target = ast.PositionReference(
        typed_names=(
            ast.LocalTypedNameReference(
                name_type=ast.NameType.POSITION,
                name_content=ast.LocalNameContent(name="one", location=location),
                location=location,
            ),
        ),
        location=location,
    )
    one = operation_graph_model.CreateNode(node_id=1, target=target, depends_on=())
    equivalent = operation_graph_model.CreateNode(
        node_id=1, target=target, depends_on=()
    )

    assert one != equivalent
    assert len({one, equivalent}) == 2
