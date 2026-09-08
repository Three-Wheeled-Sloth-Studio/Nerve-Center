from nerve_center.scoring.service import _title_role_alignment


def test_title_role_alignment_separates_target_and_unrelated_roles() -> None:
    targets = ["Director of Product Management", "Head of Product"]

    assert _title_role_alignment("Senior Director, Product Management", targets) == 1.0
    assert _title_role_alignment("Principal Product Manager", targets) == 1.0
    assert _title_role_alignment("Director, Product Marketing", targets) == 0.5
    assert _title_role_alignment("Senior Software Engineer", targets) == 0.0
    assert _title_role_alignment("Accounting Manager", targets) == 0.0
