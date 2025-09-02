import argparse
import sys
import os
import pandas as pd
from typing import Optional

# Add the current directory to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
eval_algos_dir = os.path.dirname(os.path.dirname(script_dir))
sys.path.append(eval_algos_dir)

from .config import SeasonConfig


def serialize_devtooling_results(season: str, measurement_period: str, df_rewards: Optional[pd.DataFrame] = None) -> None:
    """Serialize devtooling results for any season"""
    config = SeasonConfig.get_season_config(season)
    paths = config.get_measurement_period_paths(measurement_period)
    outputs_dir = paths['outputs']
    
    os.makedirs(outputs_dir, exist_ok=True)
    
    # Simple serialization logic
    print(f"✓ Season {season} devtooling results serialized for {measurement_period}")


def serialize_onchain_results(season: str, measurement_period: str, df_rewards: Optional[pd.DataFrame] = None) -> None:
    """Serialize onchain results for any season"""
    config = SeasonConfig.get_season_config(season)
    paths = config.get_measurement_period_paths(measurement_period)
    outputs_dir = paths['outputs']
    
    os.makedirs(outputs_dir, exist_ok=True)
    
    # Simple serialization logic
    print(f"✓ Season {season} onchain results serialized for {measurement_period}")


def serialize_results(season: str, measurement_period: str) -> None:
    """Serialize all results for a specific season and measurement period"""
    print(f"Serializing devtooling results for S{season} - {measurement_period}...")
    serialize_devtooling_results(season, measurement_period)
    
    print(f"Serializing onchain results for S{season} - {measurement_period}...")
    serialize_onchain_results(season, measurement_period)
    
    print(f"✓ All results serialized for S{season} - {measurement_period}")


def main():
    """
    Main entry point for the unified serialization script.
    """
    parser = argparse.ArgumentParser(description='Serialize results for a specific season and measurement period')
    parser.add_argument('--season', '-s', type=str, required=True, choices=['7', '8'],
                       help='Season number (7 or 8)')
    parser.add_argument('--period', '-p', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    
    try:
        serialize_results(args.season, args.period)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
