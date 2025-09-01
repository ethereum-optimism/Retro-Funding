#!/usr/bin/env python3

import os
import sys
import pandas as pd
import glob
from typing import List, Dict
import argparse

# Add the project root and eval-algos to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../..'))
eval_algos_dir = os.path.abspath(os.path.join(script_dir, '../..'))
sys.path.extend([project_root, eval_algos_dir])

from S8.utils.config import get_measurement_period_paths


def find_rewards_files(outputs_dir: str) -> List[str]:
    """
    Find all rewards CSV files in the outputs directory.
    
    Args:
        outputs_dir: Path to the outputs directory
        
    Returns:
        List of paths to rewards CSV files
    """
    return glob.glob(os.path.join(outputs_dir, "*__*_rewards.csv"))


def process_rewards_file(file_path: str) -> pd.DataFrame:
    """
    Process a single rewards file and standardize its format.
    
    Args:
        file_path: Path to the rewards CSV file
        
    Returns:
        DataFrame with standardized columns
    """
    df = pd.read_csv(file_path)
    filename = os.path.basename(file_path)
    
    # Determine round_id based on filename
    round_id = '7' if 'devtooling' in filename else '8'
    atlas_id_key = 'project_id' if 'devtooling' in filename else 'project_name'
    
    # Standardize column names
    if atlas_id_key in df.columns:
        df = df.rename(columns={atlas_id_key: 'op_atlas_id'})
    
    # Add filename and round_id columns
    df['filename'] = filename
    df['round_id'] = round_id
    
    # Select and reorder columns
    return df[['op_atlas_id', 'op_reward', 'filename', 'round_id']]


def consolidate_rewards(measurement_period: str) -> pd.DataFrame:
    """
    Consolidate all rewards files into a single DataFrame.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        
    Returns:
        Consolidated DataFrame with all rewards
    """
    # Get the outputs directory from config
    paths = get_measurement_period_paths(measurement_period)
    outputs_dir = paths['outputs']
    
    # Find all rewards files
    rewards_files = find_rewards_files(outputs_dir)
    
    if not rewards_files:
        print(f"No rewards files found in {outputs_dir}")
        return pd.DataFrame()
    
    # Process each file and concatenate results
    dfs = [process_rewards_file(f) for f in rewards_files]
    df_consolidated = pd.concat(dfs, ignore_index=True)
    
    # Sort by op_atlas_id and round_id
    df_consolidated = df_consolidated.sort_values(['op_atlas_id', 'round_id'])
    
    return df_consolidated


def save_consolidated_rewards(df: pd.DataFrame, measurement_period: str) -> str:
    """
    Save the consolidated rewards DataFrame to a CSV file.
    
    Args:
        df: Consolidated rewards DataFrame
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        
    Returns:
        Path to the saved file
    """
    # Get the outputs directory from config
    paths = get_measurement_period_paths(measurement_period)
    outputs_dir = paths['outputs']
    
    # Save to CSV
    output_path = os.path.join(outputs_dir, f"{measurement_period}_consolidated_rewards.csv")
    df.to_csv(output_path, index=False)
    
    return output_path


def main():
    """
    Main entry point for the rewards consolidation script.
    """
    parser = argparse.ArgumentParser(description='Consolidate rewards from multiple sources')
    parser.add_argument('--measurement-period', '-m', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    
    
    df_consolidated = consolidate_rewards(args.measurement_period)
    if df_consolidated.empty:
        print("No rewards data to consolidate")
        return
    
    output_path = save_consolidated_rewards(df_consolidated, args.measurement_period)
    print(f"✓ Saved consolidated rewards to {output_path}")


if __name__ == "__main__":
    main() 