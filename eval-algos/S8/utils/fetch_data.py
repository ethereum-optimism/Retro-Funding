#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from pyoso import Client

# Add the project root and eval-algos to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../..'))
eval_algos_dir = os.path.abspath(os.path.join(script_dir, '../..'))
sys.path.extend([project_root, eval_algos_dir])

# Import queries and config
from S8.utils.queries import QUERIES
from S8.utils.config import get_measurement_period_paths, ensure_directories

# Load environment variables
load_dotenv()
OSO_API_KEY = os.environ.get('OSO_API_KEY')
if not OSO_API_KEY:
    print("Error: OSO_API_KEY environment variable not set")
    sys.exit(1)

# Initialize OSO client
client = Client(api_key=OSO_API_KEY)

def get_output_path(measurement_period, filename, filetype):
    """
    Get the output path for a given measurement period and filename.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
        filename: The filename without extension
        
    Returns:
        The full path to the output file
    """
    # Get the data directory from config
    paths = get_measurement_period_paths(measurement_period)
    data_dir = paths['data']
    
    # Ensure the directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    # Return the full path
    return os.path.join(data_dir, f"{filename}.{filetype}")

def execute_query(query_obj, measurement_period):
    """
    Execute a query and save the results to a CSV or JSON file based on the filetype.
    
    Args:
        query_obj: The query object containing the filename, filetype, and SQL query
        measurement_period: The measurement period (e.g., 'M1', 'M2')
    """
    query_sql = query_obj["query"]
    filename = query_obj["filename"]
    filetype = query_obj.get("filetype", "csv")
    output_path = get_output_path(measurement_period, filename, filetype)
    
    print(f"Executing query for {filename}...")
    try:
        dataframe = client.to_pandas(query_sql)
        
        # Export based on filetype
        if filetype.lower() == "csv":
            dataframe.to_csv(output_path, index=False)
        elif filetype.lower() == "json":
            json_str = dataframe.to_json(orient='records', indent=2)
            clean_json_str = json_str.replace('\\/', '/')
            with open(output_path, 'w') as file:
                file.write(clean_json_str)
        else:
            raise ValueError(f"Unsupported filetype: {filetype}")
            
        print(f"✓ Saved {output_path}")
    except Exception as e:
        print(f"✗ Error executing query for {filename}: {str(e)}")

def fetch_data(measurement_period):
    """
    Fetch all data for a given measurement period.
    
    Args:
        measurement_period: The measurement period (e.g., 'M1', 'M2')
    """
    print(f"Fetching data for measurement period: {measurement_period}")
    
    # Ensure all directories exist
    ensure_directories(measurement_period)
    
    # Execute all queries
    for query in QUERIES:
        execute_query(query, measurement_period)
    
    print(f"Data fetch complete for {measurement_period}")

def main():
    parser = argparse.ArgumentParser(description='Fetch data from OSO for a specific measurement period')
    parser.add_argument('--measurement-period', '-m', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    fetch_data(args.measurement_period)

if __name__ == "__main__":
    main()