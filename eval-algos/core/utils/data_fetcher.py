import argparse
import os
import sys
from typing import List, Dict, Any
import pandas as pd
from dotenv import load_dotenv
from pyoso import Client

from .config import SeasonConfig


class DataFetcher:
    """
    Generic data fetcher that works for any season.
    """
    
    def __init__(self, season_config: SeasonConfig):
        self.config = season_config
        self.client = self._init_oso_client()
    
    def _init_oso_client(self) -> Client:
        load_dotenv()
        api_key = os.environ.get('OSO_API_KEY')
        if not api_key:
            raise ValueError("OSO_API_KEY environment variable not set")
        return Client(api_key=api_key)
    
    def get_output_path(self, measurement_period: str, filename: str, filetype: str) -> str:
        """Get the output path for a given measurement period and filename."""
        paths = self.config.get_measurement_period_paths(measurement_period)
        data_dir = paths['data']
        
        # Ensure the directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Return the full path
        return os.path.join(data_dir, f"{filename}.{filetype}")
    
    def execute_query(self, query_obj: Dict[str, Any], measurement_period: str) -> None:
        """
        Execute a query and save the results to a CSV or JSON file.
        """
        query_sql = query_obj["query"]
        filename = query_obj["filename"]
        filetype = query_obj.get("filetype", "csv")
        output_path = self.get_output_path(measurement_period, filename, filetype)
        
        print(f"Executing query for {filename}...")
        try:
            dataframe = self.client.to_pandas(query_sql)
            
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
    
    def fetch_data(self, measurement_period: str, queries: List[Dict[str, Any]]) -> None:
        """
        Fetch all data for a given measurement period.
        """
        print(f"Fetching data for measurement period: {measurement_period}")
        
        # Ensure all directories exist
        self.config.ensure_directories(measurement_period)
        
        # Execute all queries
        for query in queries:
            self.execute_query(query, measurement_period)
        
        print(f"Data fetch complete for {measurement_period}")


def get_season_queries(season: str):
    """
    Get the appropriate season queries.
    """
    if season == '7':
        try:
            from queries.s7_queries import QUERIES as query_instructions
        except ImportError:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from queries.s7_queries import QUERIES as query_instructions
        return query_instructions
    elif season == '8':
        try:
            from queries.s8_queries import QUERIES as query_instructions
        except ImportError:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from queries.s8_queries import QUERIES as query_instructions
        return query_instructions
    else:
        raise ValueError(f"Unsupported season: {season}")


def fetch_data(season: str, measurement_period: str, queries: List[Dict[str, Any]]) -> None:
    """
    Convenience function to fetch data for a specific season.
    """
    config = SeasonConfig.get_season_config(season)
    fetcher = DataFetcher(config)
    fetcher.fetch_data(measurement_period, queries)


def main():
    parser = argparse.ArgumentParser(description='Fetch data from OSO for a specific season and measurement period')
    parser.add_argument('--season', '-s', type=str, required=True, choices=['7', '8'],
                       help='Season number (7 or 8)')
    parser.add_argument('--period', '-p', type=str, required=True,
                       help='Measurement period (e.g., M1, M2)')
    
    args = parser.parse_args()
    
    try:
        queries = get_season_queries(args.season)
        fetch_data(args.season, args.period, queries)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
