
def fix_state_dict_keys(state_dict):
    """Fix incorrect keys in the state dict by removing misplaced dots."""
    new_state_dict = {}
    for k, v in state_dict.items():
        # Fix keys like "norm.1" to "norm1" and "conv.1" to "conv1"
        new_key = k.replace(".1", "1").replace(".2", "2").replace(".3", "3")
        new_state_dict[new_key] = v
    return new_state_dict
