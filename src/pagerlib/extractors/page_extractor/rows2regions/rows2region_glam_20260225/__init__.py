
from .torch_model import TorchModelBase
import torch
import os 

DIR_MODEL = os.path.dirname(os.path.abspath(__file__))
PATH_MODEL = os.path.join(DIR_MODEL, 'row2region_GLAM_20260225')

def get_load_model(path=PATH_MODEL, device='cpu'):
    model = TorchModelBase({
        "sigmoidEdge": True,
        "node_featch": 15,
        "edge_featch": 4,
        "Tag":[  {'in': -1, 'size': 512, 'out': 512, 'k': 3},
                {'in': 512, 'size': 256, 'out': 256, 'k': 3},
                ],
        "NodeLinear": [-1, 64, 32],
        "NodeLinearClassifier": [-1, 16, 8],
        "EdgeLinear": [-1, 16, 4],
        "batchNormNode": True,
        "batchNormEdge": True,
        'NodeClasses': 6,
        "seg_k": 0.5,
    })
    model.load_state_dict(torch.load(path, weights_only=True, map_location=torch.device(device)))
    return model
