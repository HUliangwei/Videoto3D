# Videoto3D Windows SAM 2 Setup

This runtime is independent from Videoto3D's Python 3.9 environment.

## 1. Create the Conda environment

```powershell
conda create -n videoto3d-seg python=3.11 -y
conda activate videoto3d-seg
```

## 2. Install CUDA-enabled PyTorch

```powershell
conda install pytorch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 pytorch-cuda=12.1 -c pytorch -c nvidia -y
```

Verify:

```powershell
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

CUDA must print `True`.

## 3. Clone SAM 2 inside Videoto3D runtime

From the Videoto3D project root:

```powershell
New-Item -ItemType Directory -Force .\runtime\sam2 | Out-Null
git clone https://github.com/facebookresearch/sam2.git .\runtime\sam2\repo
cd .\runtime\sam2\repo
```

Install without the optional custom CUDA extension:

```powershell
$env:SAM2_BUILD_CUDA="0"
pip install -e ".[notebooks]"
```

## 4. Download SAM 2.1 Hiera Small

Return to the Videoto3D project root and run:

```powershell
New-Item -ItemType Directory -Force .\runtime\sam2\checkpoints | Out-Null

curl.exe -L `
  "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt" `
  -o ".\runtime\sam2\checkpoints\sam2.1_hiera_small.pt"
```

## 5. Verify from Videoto3D

Deactivate the segmentation environment and return to the normal Videoto3D environment:

```powershell
conda deactivate
python app.py run mask
```

Videoto3D will validate the separate `videoto3d-seg` environment automatically. A window will open on the first frame. Drag one box around the target, then press Enter or Space.

Generated files:

```text
workspace/runs/v0_object_masked/
├── frames/
├── masks/
│   ├── frame_0001.jpg.png
│   └── ...
├── segmentation/
│   └── report.json
└── logs/
    └── sam2_mask_worker.log
```
