import torch
from torch.nn import ModuleList, Linear, ReLU, GELU, Softmax, Sigmoid
from torch_geometric.data import Data
from torch_geometric.nn import BatchNorm, TAGConv, GCNConv, GATConv
from torch_geometric.transforms import LineGraph
activations = {
    "gelu": GELU(),
    "relu": ReLU(),
    "softmax": Softmax(),
    "sigmoid": Sigmoid(),
    "none": None
}

gnn_convs = {
    "tag": lambda params: TAGConv(params['in_gnn'], params['out_gnn'], K=params['K']),
    "conv": lambda params: GCNConv(params['in_gnn'], params['out_gnn']),
    "gat": lambda params: GATConv(params['in_gnn'], params['out_gnn']),
}

class GNNBlock(torch.nn.Module):
    def __init__(self, type_conv, params):
        super(GNNBlock, self).__init__()
        self.is_exist_batch_norm = "batch_norm" in params and params['batch_norm'] 
        self.is_concat = "concat" in params and params['concat']

        self.linear = Linear(params['in'],params['in_gnn'])
        if self.is_exist_batch_norm:
            self.batch_norm = BatchNorm(params['in_gnn'])
        self.gnn_activation = activations[params['gnn_activation']]
        self.activation = activations[params['activation']]
        self.gnn_conv = gnn_convs[type_conv](params)
        

    def forward(self, x, edge_index):
        x_in = x
        x = self.linear(x)
        if self.is_exist_batch_norm:
            x = self.batch_norm(x)
        if self.gnn_activation is not None:
            x = self.gnn_activation(x)
        x = self.gnn_conv(x, edge_index)
        if self.is_concat:
            x = torch.cat((x, x_in), dim=-1)
        if self.activation is not None:
            x = self.activation(x)
        return x


class Block(torch.nn.Module):
    def __init__(self, params):
        super(Block, self).__init__()
        self.is_exist_linear_pred = "linear_pred" in params and len(params['linear_pred']) != 0
        self.is_exist_linear_post = "linear_post" in params and len(params['linear_post']) != 0
        self.is_exist_gnn = "gnn" in params and len(params['gnn']) != 0

        if self.is_exist_linear_pred:
            self.linear_pred = ModuleList([
                Linear(linear['in'], linear['out']) for linear in params['linear_pred']
            ])
            self.activation_pred = [
                activations[linear['activation']] for linear in params['linear_pred']
            ]
        if self.is_exist_linear_post:
            self.linear_post = ModuleList([
                Linear(linear['in'], linear['out']) for linear in params['linear_post']
            ])
            self.activation_post = [
                activations[linear['activation']] for linear in params['linear_post']
            ]
        if self.is_exist_gnn:
            self.gnns = ModuleList([
                GNNBlock(type_conv, params_conv) for type_conv, params_conv in params['gnn']
            ]) 
        

    def forward(self, x, edge_index):
        if self.is_exist_linear_pred:
            for linear, activation in zip(self.linear_pred, self.activation_pred):
                x = linear(x)
                if activation is not None:
                    x = activation(x)
        if self.is_exist_gnn:
            for gnn in self.gnns:
                x = gnn(x, edge_index)
        if self.is_exist_linear_post:
            for linear, activation in zip(self.linear_post, self.activation_post):
                x = linear(x)
                if activation is not None:
                    x = activation(x)
        return x

class TorchModel(torch.nn.Module):
    """
       Data
         |
     NodeBlock - NodeClassifierBlock -> class node
         |
    (None|PostNodeBlock)
         |
    (None|ConjugateEdgeBlock)
         |
    EdgeClassifierBlock
         |
     class edge
    """
    def __init__(self, params):
        super(TorchModel, self).__init__()
        self.node_block = Block(params["node_block"])
        self.node_classifier_block = Block(params["node_classifier_block"])
        
        self.is_exist_post_node_block = "post_node_block" in params
        if "post_node_block" in params:
            self.post_node_block = Block(params["post_node_block"])

        self.is_exist_conjugate_edge_block = "conjugate_edge_block" in params
        if "conjugate_edge_block" in params:
            self.conjugate_edge_block = Block(params["conjugate_edge_block"])
        
        self.edge_classifier_block = Block(params["edge_classifier_block"])
        

    def forward(self, data_graph_dict):
        X: torch.Tensor = data_graph_dict["X"] 
        Y: torch.Tensor = data_graph_dict["Y"]
        sp_A: torch.Tensor = data_graph_dict["sp_A"] 
        inds: List[int] = data_graph_dict["inds"]

        node_embs = self.node_block(X, sp_A)
        node_classes = self.node_classifier_block(node_embs, sp_A)
        if self.is_exist_post_node_block:
            node_embs = self.post_node_block(node_embs, sp_A)

        edge_emb = torch.cat([node_embs[inds[0]], node_embs[inds[1]], X[inds[0]], X[inds[1]], Y],dim=1)
        if self.is_exist_conjugate_edge_block:
            omega_sp_A = self.build_conjugate_graph(sp_A)
            edge_emb = self.conjugate_edge_block(edge_emb, omega_sp_A)
        else:
            omega_sp_A = None
        edge_classes = self.edge_classifier_block(edge_emb, omega_sp_A)
        edge_classes = torch.squeeze(edge_classes, 1) 
        return {
            "node_classes": node_classes, 
            "E_pred": edge_classes
        }

    # def build_conjugate_graph(self, A: torch.Tensor):
    #     # TODO optimization
    #     A.fill_diagonal_(0)
    #     A = np.array(A)
    #     g = nx.from_numpy_array(A)
    #     L = nx.line_graph(g)
    #     A_new = torch.tensor(nx.adjacency_matrix(L).toarray())
    #     A_new.fill_diagonal_(1)
    #     return A_new.float()

    def build_conjugate_graph(self, A: torch.Tensor):
        transform = LineGraph()
        if A.is_sparse:
            edge_index = A.indices().contiguous()
        else:
            edge_index = A.nonzero().t().contiguous()
        
        if edge_index.size(1) == 0:
            return torch.zeros((2, 0), dtype=torch.long, device=A.device)
        
        num_nodes = A.size(0)
        data = Data(edge_index=edge_index, num_nodes=num_nodes)
        line_graph_data = transform(data)
        return line_graph_data.edge_index.to(A.device)
        
