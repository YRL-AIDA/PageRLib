import os
import io
import torch
import pytesseract
import torch.nn as nn
from torchvision import models, transforms
import torch.nn.functional as F
from PIL import Image, ImageDraw
import json
from pathlib import Path

def load_model(size):
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    model_path = Path(__file__).parent/f'font_identifier_model_lines_{size}.pth'
    if size == 512:
        model.fc = nn.Linear(model.fc.in_features, 71)
        
        model.load_state_dict(torch.load(model_path, map_location='cpu'))
        model.fc = nn.Identity()
    elif size == 16 or size == 32:
        model.fc = nn.Sequential(
            nn.Linear(model.fc.in_features, size),
            nn.Linear(size, 71)
        )
        model.load_state_dict(torch.load(model_path, map_location='cpu'))
        model.fc[-1] = nn.Identity()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    model.eval()

    return model

# def get_rows(image_bytes):
#     image = Image.open(io.BytesIO(image_bytes)).convert('L')

#     data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

#     rows = []
#     n = len(data["level"])

#     for i in range(n):
#         if data["level"][i] == 4:
#             left = data["left"][i]
#             top = data["top"][i]
#             width = data["width"][i]
#             height = data["height"][i]

#             if width > 200 and height > 5:
#                 bbox = [left, top, left + width, top + height]
#                 rows.append(image.crop(bbox))

#     return rows

def row_to_vec(model, row_image):

    data_transforms = transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize(18),
        transforms.CenterCrop((18, 112)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])

    image_tensor = data_transforms(row_image).unsqueeze(0).to(model.device)

    with torch.no_grad():
        vector = model(image_tensor).squeeze()
        # print(vector)

    return vector.cpu().numpy()

# def get_similar_fonts(image_bytes):

#     model = load_model()
#     rows = get_rows(image_bytes)

#     vectors = []

#     for row in rows:
#         vectors.append(row_to_vec(model, row))

#     mean_vector = torch.stack(vectors).mean(dim=0)
#     # print(mean_vector)

#     top = []

#     with open("project/database/data.json", "r") as file:
#         font_data = json.load(file)
#         for key in font_data.keys():
#             font_data[key]= torch.tensor(font_data[key])
#             top.append({
#                 "name": key, 
#                 "sim": F.cosine_similarity(mean_vector, font_data[key], dim=0).item(),
#                 "image": None
#                 })

#     sorted_top = sorted(top, key=lambda x: x["sim"], reverse=True)
        

#     return sorted_top[:5]

