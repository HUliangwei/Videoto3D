
import math
import sqlite3
import struct
from pathlib import Path

import pytest

from pipeline.workflows.turntable.legacy_v13.reconstruction import (
    build_uniform_pose_records,
    camera_center_from_qt,
    choose_turntable_candidate,
    estimate_turntable_translation,
    read_database_scene,
    write_known_pose_model,
)


def make_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE cameras (camera_id INTEGER PRIMARY KEY, model INTEGER, width INTEGER, height INTEGER, params BLOB, prior_focal_length INTEGER)")
    con.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT UNIQUE, camera_id INTEGER)")
    con.execute("INSERT INTO cameras VALUES (7,2,1280,720,?,1)", (struct.pack("<4d",1000.0,640.0,360.0,0.01),))
    for row in [(11,"frame_0001.jpg",7),(13,"frame_0002.jpg",7),(19,"frame_0003.jpg",7),(23,"frame_0004.jpg",7)]:
        con.execute("INSERT INTO images VALUES (?,?,?)", row)
    con.commit()
    con.close()


def test_database_scene_preserves_ids(tmp_path):
    db = tmp_path / "database.db"
    make_db(db)
    camera, images = read_database_scene(db)
    assert camera["camera_id"] == 7
    assert camera["model_name"] == "SIMPLE_RADIAL"
    assert camera["params"] == pytest.approx((1000.0,640.0,360.0,0.01))
    assert [x["image_id"] for x in images] == [11,13,19,23]


def test_pose_ring_has_constant_translation_and_radius():
    images = [{"image_id":i+1,"camera_id":7,"name":f"frame_{i+1:04d}.jpg"} for i in range(8)]
    t = (0.12,-0.05,1.0)
    poses = build_uniform_pose_records(images,t,1)
    assert all(p["tvec"] == pytest.approx(t) for p in poses)
    centers = [camera_center_from_qt(p["qvec"],p["tvec"]) for p in poses]
    radii = [math.hypot(c[0],c[2]) for c in centers]
    assert max(radii)-min(radii) < 1e-9
    assert all(c[1] == pytest.approx(0.05) for c in centers)
    assert centers[0][2] * centers[4][2] < 0


def test_known_pose_model_uses_database_ids(tmp_path):
    camera = {"camera_id":7,"model_name":"SIMPLE_RADIAL","width":1280,"height":720,"params":(1000.0,640.0,360.0,0.01)}
    images = [
        {"image_id":11,"camera_id":7,"name":"frame_0001.jpg"},
        {"image_id":13,"camera_id":7,"name":"frame_0002.jpg"},
    ]
    poses = build_uniform_pose_records(images,(0,0,1),-1)
    out = tmp_path / "known"
    write_known_pose_model(out,camera,poses)
    assert "7 SIMPLE_RADIAL 1280 720 1000" in (out/"cameras.txt").read_text()
    txt = (out/"images.txt").read_text()
    assert "11 " in txt and " 7 frame_0001.jpg" in txt
    assert "13 " in txt and " 7 frame_0002.jpg" in txt


def test_candidate_selection_prefers_points_then_reprojection():
    assert choose_turntable_candidate([
        {"direction":"cw","stats":{"points3D":200,"mean_reprojection_error":0.5}},
        {"direction":"ccw","stats":{"points3D":300,"mean_reprojection_error":5.0}},
    ])["direction"] == "ccw"
    assert choose_turntable_candidate([
        {"direction":"cw","stats":{"points3D":300,"mean_reprojection_error":1.2}},
        {"direction":"ccw","stats":{"points3D":300,"mean_reprojection_error":0.8}},
    ])["direction"] == "ccw"


def test_mask_bbox_median_estimates_projected_axis(tmp_path):
    from PIL import Image, ImageDraw
    masks = tmp_path / "masks"
    masks.mkdir()
    images=[]
    for i,cx in enumerate((620,640,660),1):
        name=f"frame_{i:04d}.jpg"
        images.append({"image_id":i,"camera_id":7,"name":name})
        im=Image.new("L",(1280,720),0)
        ImageDraw.Draw(im).rectangle((cx-20,340,cx+20,380),fill=255)
        im.save(masks/(name+".png"))
    result=estimate_turntable_translation(masks,images,{"params":(1000.0,640.0,360.0,0.0)})
    assert result["axis_px"] == pytest.approx((640.5,360.5),abs=1.0)
    assert result["tvec"][0] == pytest.approx(0.0,abs=0.002)
    assert result["tvec"][1] == pytest.approx(0.0,abs=0.002)
    assert result["tvec"][2] == 1.0


def test_turntable_module_uses_known_pose_triangulator_not_mapper():
    source=Path("pipeline/workflows/turntable/legacy_v13/reconstruction.py").read_text(encoding="utf-8")
    assert '"point_triangulator"' in source
    assert '"mapper"' not in source
