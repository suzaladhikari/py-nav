import yaml
import os
from core.map import Map

class LiteralString(str):
    pass

def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

yaml.add_representer(LiteralString, literal_presenter)

def load_map(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
        
    raw_map_str = data.get('map', '')
    grid = [list(line) for line in raw_map_str.strip('\n').split('\n')]
    
    return {
        'wrap': data.get('wrap', False),
        'diagonal_moves': data.get('diagonal_moves', True),
        'diagonal_move_true_cost': data.get('diagonal_move_true_cost', True),
        'min_distance': data.get('min_distance', 0),
        'map': grid,
        'validated': data.get('validated', False)
    }

def save_map(filepath: str, map_obj: Map, validated: bool):
    map_str = LiteralString('\n'.join(''.join(row) for row in map_obj.map))
    
    data = {
        'wrap': map_obj.wrap,
        'diagonal_moves': map_obj.diagonal_moves,
        'diagonal_move_true_cost': map_obj.diagonal_move_true_cost,
        'min_distance': map_obj.min_distance,
        'map': map_str,
        'validated': validated
    }
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
