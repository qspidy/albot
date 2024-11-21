import json


def load_config(filename="config.json"):
    with open(filename, "r") as config_file:
        config = json.load(config_file)
    return config
