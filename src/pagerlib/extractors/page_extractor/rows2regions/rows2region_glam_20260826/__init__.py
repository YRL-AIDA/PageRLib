
from .torch_model import TorchModel
from .model_params import default_arch

import torch
import os 

config = {
    "input_dim": 21 + 32,
    "gnn_type": "tag",
    "num_layers": 3,
    "edge_coef": 0.7,
    "has_post_node":True, 
    "has_lp": True,
    "hidden_dim":128,
    "gnn_hidden": 128,

}
params = default_arch(
    input_dim=21 + 32,
    gnn_type="tag",
    num_layers=3,
    has_post_node=True,
    has_lp=True,
    hidden_dim=128,
    gnn_hidden=128
)
params["node_classifier_block"]["linear_post"][-1]["activation"] = "softmax"
params["edge_classifier_block"]["linear_post"][-1]["activation"] = "sigmoid"



DIR_MODEL = os.path.dirname(os.path.abspath(__file__))
PATH_MODEL = os.path.join(DIR_MODEL, 'rows2regions_GLAM_20260826')

def get_load_model(path=PATH_MODEL, device='cpu'):
    model = TorchModel(params)
    model.load_state_dict(torch.load(path, weights_only=True, map_location=torch.device(device)))
    # model.eval()
    return model
