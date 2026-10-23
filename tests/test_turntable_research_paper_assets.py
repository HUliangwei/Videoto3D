from pathlib import Path


def test_research_paper_assets_are_not_mislabeled_html():
    root = Path(__file__).resolve().parents[1]
    papers = (
        root
        / "docs"
        / "research"
        / "turntable"
        / "papers"
    )
    kosaka = (
        papers
        / "Kosaka_2026_Turntable_Constrained_Camera_Pose_Estimation.pdf"
    )
    assert kosaka.exists()
    assert kosaka.read_bytes()[:5] == b"%PDF-"

    rotgs = papers / "Kim_2026_RotGS.pdf"
    assert (
        not rotgs.exists()
        or rotgs.read_bytes()[:5] == b"%PDF-"
    )
