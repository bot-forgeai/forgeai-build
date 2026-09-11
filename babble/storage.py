import json

from .model import MarkovModel


def save_model(model, path):
    with open(path, "w") as f:
        json.dump(model.to_dict(), f)


def load_model(path):
    with open(path) as f:
        data = json.load(f)
    return MarkovModel.from_dict(data)
