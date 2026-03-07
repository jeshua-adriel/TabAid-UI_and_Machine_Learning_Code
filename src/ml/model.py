# src/ml/model.py
import torch
import torch.nn as nn
import torch.nn.functional as F


class EmbeddingNet(nn.Module):
    """
    Simple CNN encoder that outputs a 128-d embedding.
    Input: (B, 3, 128, 128)
    Output: (B, 128) L2-normalized
    """
    def __init__(self):
        super().__init__()

        self.conv = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 128 -> 64

            nn.Conv2d(32, 64, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 64 -> 32

            nn.Conv2d(64, 128, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 32 -> 16

            nn.AdaptiveAvgPool2d((16, 16))  # keep stable
        )

        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 16 * 16, 512),
            nn.ReLU(inplace=True),
            nn.Linear(512, 128),
        )

    def forward(self, x):
        x = self.conv(x)
        x = self.fc(x)
        x = F.normalize(x, p=2, dim=1)  # normalize embeddings
        return x


class SiameseNet(nn.Module):
    """
    Siamese wrapper: runs two inputs through the same embedding net.
    """
    def __init__(self, embedding_net: nn.Module):
        super().__init__()
        self.embedding_net = embedding_net

    def forward(self, x1, x2):
        return self.embedding_net(x1), self.embedding_net(x2)


def euclidean_dist(x, y):
    """
    Pairwise euclidean distance between embeddings.
    x, y: (B, D)
    returns: (B,)
    """
    return F.pairwise_distance(x, y)
