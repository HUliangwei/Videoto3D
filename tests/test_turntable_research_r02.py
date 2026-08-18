import math
import numpy as np
from pipeline.workflows.turntable.pose.single_axis import axis_angle_rotation, normalize_axis
from pipeline.workflows.turntable.pose.structured_fit import fit_structured_angle, structured_angle_residual_px
from pipeline.workflows.turntable.pose.synthetic_geometry import camera_intrinsics_from_ground_truth, shared_geometry_from_ground_truth

def _project(k, points):
    pixels=(k@points.T).T
    return pixels[:,:2]/pixels[:,2:3]

def test_structured_estimator_recovers_exact_relative_angle():
    rng=np.random.default_rng(4)
    k=np.array([[820.,0.,360.],[0.,810.,360.],[0.,0.,1.]])
    axis=normalize_axis([0.12,0.97,-0.08]); orbit=np.array([0.25,-0.15,4.5]); true_deg=12.30
    r=axis_angle_rotation(axis,math.radians(true_deg)); t=orbit-r@orbit
    x1=rng.uniform([-1.,-0.9,3.],[1.,0.9,6.],size=(300,3)); x2=(r@x1.T).T+t
    valid=x2[:,2]>0.5
    result=fit_structured_angle(_project(k,x1[valid]),_project(k,x2[valid]),k,axis,orbit,max_abs_angle_deg=30.)
    assert abs(result["signed_angle_deg"]-true_deg)<=0.02
    assert result["median_sampson_px"]<1e-6

def test_structured_estimator_is_robust_to_outliers():
    rng=np.random.default_rng(9)
    k=np.array([[700.,0.,320.],[0.,700.,240.],[0.,0.,1.]])
    axis=normalize_axis([0.,1.,0.15]); orbit=np.array([0.4,0.1,4.]); true_deg=7.40
    r=axis_angle_rotation(axis,math.radians(true_deg)); t=orbit-r@orbit
    x1=rng.uniform([-0.8,-0.7,3.],[0.8,0.7,5.5],size=(220,3)); x2=(r@x1.T).T+t
    p1,p2=_project(k,x1),_project(k,x2); p2[:60]=rng.uniform([0.,0.],[640.,480.],size=(60,2))
    result=fit_structured_angle(p1,p2,k,axis,orbit,max_abs_angle_deg=20.)
    assert abs(result["signed_angle_deg"]-true_deg)<=0.10

def test_wrong_angle_has_larger_residual():
    rng=np.random.default_rng(11)
    k=np.array([[760.,0.,360.],[0.,760.,360.],[0.,0.,1.]])
    axis=normalize_axis([0.1,0.98,0.05]); orbit=np.array([0.3,-0.1,4.2]); true_deg=9.
    r=axis_angle_rotation(axis,math.radians(true_deg)); t=orbit-r@orbit
    x1=rng.uniform([-0.8,-0.8,3.],[0.8,0.8,5.],size=(120,3)); x2=(r@x1.T).T+t
    p1,p2=_project(k,x1),_project(k,x2)
    assert structured_angle_residual_px(p1,p2,k,axis,orbit,true_deg) < structured_angle_residual_px(p1,p2,k,axis,orbit,18.)

def test_blender_camera_to_cv_mapping():
    payload={"rotation_axis_world":[0.,0.,1.],"rotation_center_world":[0.,0.,-5.],
             "camera":{"matrix_world":[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]],
                       "focal_mm":50.,"sensor_width_mm":36.,"resolution":[720,720]}}
    g=shared_geometry_from_ground_truth(payload)
    assert np.allclose(g["axis_cv"],[0.,0.,-1.])
    assert np.allclose(g["orbit_vector_cv"],[0.,0.,5.])

def test_intrinsics_from_r01_metadata():
    k=camera_intrinsics_from_ground_truth({"focal_mm":50.,"sensor_width_mm":36.,"resolution":[720,720]})
    assert np.isclose(k[0,0],1000.)
    assert np.isclose(k[1,1],1000.)
    assert np.isclose(k[0,2],360.)
