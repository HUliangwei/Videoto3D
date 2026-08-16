from pathlib import Path


def _root():
    return Path(__file__).resolve().parents[1]


def test_job_panel_renders_progress_bar_stage_stepper_elapsed_and_collapsible_log():
    text = (_root() / "gui" / "control" / "web" / "src" / "components" / "JobPanel.tsx").read_text(encoding="utf-8")
    assert "progress-bar" in text
    assert "job-stepper" in text
    assert "Elapsed" in text
    assert "Live Log" in text
    assert "logOpen" in text
    assert "progress?.percent" in text


def test_active_job_status_is_visible_in_global_top_navigation():
    text = (_root() / "gui" / "control" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "global-job-status" in text
    assert "activeJob" in text
    assert "progress?.detail" in text


def test_roi_button_changes_to_busy_copy_while_mask_job_runs():
    text = (_root() / "gui" / "control" / "web" / "src" / "components" / "RoiSelector.tsx").read_text(encoding="utf-8")
    assert "Generating Masks…" in text
