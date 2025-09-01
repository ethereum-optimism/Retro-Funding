#!/usr/bin/env python3

import os
from pathlib import Path

# Get the project root directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '../../..'))

# Season 8 base directories
ROOT = os.path.join(PROJECT_ROOT, 'results', 'S8')
MODELS = os.path.join(PROJECT_ROOT, 'eval-algos', 'S8', 'models')
UTILS = os.path.join(PROJECT_ROOT, 'eval-algos', 'S8', 'utils')

# Measurement period subdirectories
def get_measurement_period_paths(measurement_period: str) -> dict:
    """
    Get all relevant paths for a specific measurement period.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        
    Returns:
        Dictionary containing paths for data, weights, and outputs
    """
    base = os.path.join(ROOT, measurement_period)
    return {
        'data': os.path.join(base, 'data'),
        'weights': os.path.join(base, 'weights'),
        'outputs': os.path.join(base, 'outputs')
    }

# File naming conventions
def get_model_yaml_path(measurement_period: str, model_name: str) -> str:
    """Get the full path to a model YAML file."""
    return os.path.join(get_measurement_period_paths(measurement_period)['weights'], f'{model_name}.yaml')

def get_output_path(measurement_period: str, model_name: str = None) -> str:
    """
    Get the output path for a specific model.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        model_name: The name of the model (e.g., 'arcturus', 'goldilocks')
    """
    
    if model_name:
        base_filename = f'{model_name}_rewards'
    else:
        base_filename = 'rewards'
    return os.path.join(get_measurement_period_paths(measurement_period)['outputs'], f'{base_filename}.csv')

# Ensure directories exist
def ensure_directories(measurement_period: str):
    """Create all necessary directories for a measurement period if they don't exist."""
    paths = get_measurement_period_paths(measurement_period)
    for path in paths.values():
        Path(path).mkdir(parents=True, exist_ok=True)

# Import paths for Python modules
PYTHON_PATHS = [
    PROJECT_ROOT,
    MODELS,
    UTILS
] 