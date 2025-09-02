import os
from pathlib import Path
from typing import Dict


class SeasonConfig:
    """
    Unified configuration management for Retro Funding seasons.
    """
    
    def __init__(self, season: str):
        """
        Initialize configuration for a specific season.
        
        Args:
            season: The season number (e.g., '7', '8')
        """
        self.season = season
        self.project_root = self._get_project_root()
        self.results_root = os.path.join(self.project_root, 'results', f'S{season}')
    
    def _get_project_root(self) -> str:
        """Get the absolute path to the project root directory."""
        # Navigate from core/utils/config.py to project root
        current_file = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(current_file, '../../..'))
    
    def get_measurement_period_paths(self, measurement_period: str) -> Dict[str, str]:
        """
        Get all relevant paths for a specific measurement period.
        
        Args:
            measurement_period: The measurement period (e.g., 'M1', 'M2')
            
        Returns:
            Dictionary containing paths for data, weights, and outputs
        """
        base = os.path.join(self.results_root, measurement_period)
        return {
            'data': os.path.join(base, 'data'),
            'weights': os.path.join(base, 'weights'),
            'outputs': os.path.join(base, 'outputs')
        }
    
    def get_model_yaml_path(self, measurement_period: str, model_name: str) -> str:
        """
        Get the full path to a model YAML file.
        
        Args:
            measurement_period: The measurement period (e.g., 'M1', 'M2')
            model_name: The name of the model (e.g., 'arcturus', 'goldilocks')
            
        Returns:
            Full path to the model YAML file
        """
        paths = self.get_measurement_period_paths(measurement_period)
        return os.path.join(paths['weights'], f'{model_name}.yaml')
    
    def get_output_path(self, measurement_period: str, model_name: str = None) -> str:
        """
        Get the output path for a specific model.
        
        Args:
            measurement_period: The measurement period (e.g., 'M1', 'M2')
            model_name: The name of the model (e.g., 'arcturus', 'goldilocks')
            
        Returns:
            Full path to the output file
        """
        paths = self.get_measurement_period_paths(measurement_period)
        
        if model_name:
            base_filename = f'{model_name}_rewards'
        else:
            base_filename = 'rewards'
        
        return os.path.join(paths['outputs'], f'{base_filename}.csv')
    
    def ensure_directories(self, measurement_period: str) -> None:
        """
        Create all necessary directories for a measurement period if they don't exist.
        
        Args:
            measurement_period: The measurement period (e.g., 'M1', 'M2')
        """
        paths = self.get_measurement_period_paths(measurement_period)
        for path in paths.values():
            Path(path).mkdir(parents=True, exist_ok=True)
    
    def resolve_yaml_path(self, relative_path: str) -> str:
        """
        Resolve a relative path from YAML file to absolute path relative to project root.
        
        Args:
            relative_path: Relative path from YAML file (e.g., 'results/S8/test/data/')
            
        Returns:
            Absolute path resolved relative to project root
        """
        return os.path.join(self.project_root, relative_path)
    
    @classmethod
    def get_season_config(cls, season: str) -> 'SeasonConfig':
        """
        Factory method to get a season configuration.
        
        Args:
            season: The season number (e.g., '7', '8')
            
        Returns:
            SeasonConfig instance for the specified season
        """
        return cls(season)


# Convenience functions for backward compatibility
def get_measurement_period_paths(season: str, measurement_period: str) -> Dict[str, str]:
    """Get measurement period paths for a specific season."""
    config = SeasonConfig.get_season_config(season)
    return config.get_measurement_period_paths(measurement_period)


def get_model_yaml_path(season: str, measurement_period: str, model_name: str) -> str:
    """Get model YAML path for a specific season."""
    config = SeasonConfig.get_season_config(season)
    return config.get_model_yaml_path(measurement_period, model_name)


def get_output_path(season: str, measurement_period: str, model_name: str = None) -> str:
    """Get output path for a specific season."""
    config = SeasonConfig.get_season_config(season)
    return config.get_output_path(measurement_period, model_name)


def ensure_directories(season: str, measurement_period: str) -> None:
    """Ensure directories exist for a specific season."""
    config = SeasonConfig.get_season_config(season)
    config.ensure_directories(measurement_period)


def resolve_yaml_data_path(season: str, relative_path: str) -> str:
    """
    Resolve a relative path from YAML file to absolute path relative to project root.
    
    Args:
        season: The season number (e.g., '7', '8')
        relative_path: Relative path from YAML file (e.g., 'results/S8/test/data/')
        
    Returns:
        Absolute path resolved relative to project root
    """
    config = SeasonConfig.get_season_config(season)
    return config.resolve_yaml_path(relative_path)
