from dataclasses import dataclass
import numpy as np
import pandas as pd
import traceback
from typing import Dict, Any, Tuple
import yaml
import warnings
import os


# ------------------------------------------------------------------------
# Dataclass Definitions
# ------------------------------------------------------------------------

@dataclass
class DataSnapshot:
    """
    Contains file path details for onchain data.
    """
    data_dir: str
    projects_file: str
    metrics_file: str
    yaml_name: str


@dataclass
class SimulationConfig:
    """
    Contains simulation parameters for onchain analysis.
    """
    periods: Dict[str, str]
    chains: Dict[str, float]
    metrics: Dict[str, float]
    metric_variants: Dict[str, float]
    tvl_minimum: float = 0 
    tvl_maximum: float = 0
    eligibility_filter: bool = False
    percentile_cap: float = 100


# ------------------------------------------------------------------------
# OnchainBuildersCalculator Class
# ------------------------------------------------------------------------

class OnchainBuildersCalculator:
    """
    Encapsulates logic for pivoting and computing metric-based scores for onchain projects.
    Produces an 'analysis' dict containing all intermediate DataFrames and final results.
    """

    def __init__(self, config: SimulationConfig):
        """
        Initialize the calculator with simulation configuration and an empty analysis dictionary.
        """
        self.config = config
        self.analysis = {}

    def run_analysis(self, df_data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Run the complete analysis pipeline.

        Args:
            df_data (pd.DataFrame): Raw input DataFrame containing metrics.

        Returns:
            Dict[str, pd.DataFrame]: Analysis dictionary with all intermediate outputs.
        """
        # Store raw input data
        if self.config.eligibility_filter:
            print(f"[INFO] Eligibility filter: {self.config.eligibility_filter}")
            df_data = df_data[df_data['is_eligible'] == True]
        self.analysis = {"raw_data": df_data}

        # Execute pipeline steps
        self._filter_and_pivot_raw_metrics_by_chain()
        self._sum_and_weight_raw_metrics_by_chain()
        self._calculate_metric_variants()
        self._normalize_metric_variants()
        self._apply_weights_to_metric_variants()
        self._aggregate_metric_variants()
        self._prepare_final_results()

        return self.analysis

    # --------------------------------------------------------------------
    # Step 1: Pivot raw data
    # --------------------------------------------------------------------
    def _filter_and_pivot_raw_metrics_by_chain(self) -> None:

        df = self.analysis.get("raw_data")
        if df is None:
            raise ValueError("Raw data not found in analysis. Ensure 'raw_data' is set before Step 1.")
        
        tvl_metrics = [metric for metric in self.config.metrics.keys() if 'tvl' in metric.lower()]
        tvl_metric = tvl_metrics[0] if tvl_metrics else None
        non_zero_metrics = [metric for metric, weight in self.config.metrics.items() if weight > 0]
        all_metrics = non_zero_metrics
        if tvl_metric:
            all_metrics.append(tvl_metric)
        
        periods_list = list(self.config.periods.values())
        
        # First, create the basic pivot
        pivoted = (
            df.query("metric_name in @all_metrics and measurement_period in @periods_list")
              .pivot_table(
                  index=['project_id', 'project_name', 'display_name', 'chain'],
                  columns=['measurement_period', 'metric_name'],
                  values='amount',
                  aggfunc='sum'
              )
        )

       # If TVL minimum is set, apply it to TVL metrics
        if hasattr(self.config, 'tvl_minimum') and self.config.tvl_minimum > 0:
            # Calculate total TVL per project and period
            tvl_metrics = [m for m in non_zero_metrics if 'tvl' in m.lower()]
            for period in periods_list:
                if tvl_metrics:
                    # Sum TVL across all chains for each project
                    total_tvl = (
                        pivoted[period]
                        .reset_index()
                        .groupby('project_id')[tvl_metrics]
                        .sum()
                    )
                    
                    # Create a mask for projects below TVL minimum
                    below_min = (total_tvl < self.config.tvl_minimum).any(axis=1)
                    
                    # Set TVL metrics to null for projects below minimum
                    for metric in tvl_metrics:
                        mask = pivoted.index.get_level_values('project_id').isin(below_min[below_min].index)
                        pivoted.loc[mask, (period, metric)] = np.nan
        
        self.analysis["pivoted_raw_metrics_by_chain"] = pivoted

    # --------------------------------------------------------------------
    # Step 2: Sum & weight raw metrics by chain
    # --------------------------------------------------------------------
    def _sum_and_weight_raw_metrics_by_chain(self) -> None:
        """
        Multiplies raw metrics by the corresponding chain weights and sums the results over chains.
        
        Output is stored in:
            self.analysis["pivoted_raw_metrics_weighted_by_chain"]

        Raises:
            ValueError: If pivoted raw metrics are not available.
        """
        chain_weights = pd.Series({k.upper(): v for k, v in self.config.chains.items()})
        df = self.analysis.get("pivoted_raw_metrics_by_chain")
        if df is None:
            raise ValueError("Pivoted raw metrics not found. Check Step 1.")
        weighted_df = (
            df.mul(df.index.get_level_values('chain').map(chain_weights).fillna(1.0), axis=0)
              .groupby(['project_id', 'project_name', 'display_name'])
              .sum()
        )
        self.analysis["pivoted_raw_metrics_weighted_by_chain"] = weighted_df

    # --------------------------------------------------------------------
    # Step 3: Calculate metric variants
    # --------------------------------------------------------------------
    def _calculate_metric_variants(self) -> None:
        """
        Computes three metric variants for each project:
          - Adoption: The current period value.
          - Growth: The positive difference between current and previous period values.
          - Retention: The minimum value between current and previous periods.

        Output is stored in:
            self.analysis["pivoted_metric_variants"]

        Raises:
            ValueError: If weighted metrics are not available from Step 2.
        """
        df = self.analysis.get("pivoted_raw_metrics_weighted_by_chain")
        if df is None:
            raise ValueError("Weighted metrics not found. Check Step 2.")
        periods = self.config.periods
        current_period = periods.get('current')
        previous_period = periods.get('previous')
        non_zero_metrics = [metric for metric, weight in self.config.metrics.items() if weight > 0]

        variant_scores = {}
        for metric in non_zero_metrics:
            current_vals = df[(current_period, metric)]
            prev_vals = df[(previous_period, metric)]
            variant_scores[(metric, 'adoption')] = current_vals
            variant_scores[(metric, 'growth')] = (current_vals - prev_vals).clip(lower=0)
            variant_scores[(metric, 'retention')] = pd.concat([current_vals, prev_vals], axis=1).min(axis=1)

        self.analysis["pivoted_metric_variants"] = pd.DataFrame(variant_scores)

    # --------------------------------------------------------------------
    # Step 4: Normalize metric variants
    # --------------------------------------------------------------------
    def _normalize_metric_variants(self) -> None:
        """
        Applies min-max normalization to each metric variant column. Null values are preserved.
        
        Output is stored in:
            self.analysis["normalized_metric_variants"]

        Raises:
            ValueError: If metric variants have not been computed (Step 3).
        """
        df = self.analysis.get("pivoted_metric_variants")
        if df is None:
            raise ValueError("Metric variants not computed. Check Step 3.")
        df_norm = df.copy()
        for col in df_norm.columns:
            df_norm[col] = OnchainBuildersCalculator._minmax_scale(df_norm[col].values, self.config.percentile_cap)
        self.analysis["normalized_metric_variants"] = df_norm

    # --------------------------------------------------------------------
    # Step 5: Apply weights to metric variants
    # --------------------------------------------------------------------
    def _apply_weights_to_metric_variants(self) -> None:
        """
        Multiplies each normalized metric variant by its corresponding metric weight and variant weight.
        
        Output is stored in:
            self.analysis["weighted_metric_variants"]

        Raises:
            ValueError: If normalized metric variants are not available (Step 4).
        """
        df = self.analysis.get("normalized_metric_variants")
        if df is None:
            raise ValueError("Normalized metric variants not available. Check Step 4.")
        df_weighted = df.copy()
        for metric, m_weight in self.config.metrics.items():
            for variant, v_weight in self.config.metric_variants.items():
                if (metric, variant) in df_weighted.columns:
                    df_weighted[(metric, variant)] *= (m_weight * v_weight)
        self.analysis["weighted_metric_variants"] = df_weighted

    # --------------------------------------------------------------------
    # Step 6: Aggregate final scores
    # --------------------------------------------------------------------
    def _aggregate_metric_variants(self, method: str = 'power_mean') -> None:
        """
        Aggregates the weighted metric variants into a single project score using the specified method.
        By default, a weighted power mean (p=2) is used.
        
        Output is stored in:
            self.analysis["aggregated_project_scores"]

        Args:
            method (str): Aggregation method ('power_mean' or 'sum').

        Raises:
            ValueError: If weighted metric variants are not available (Step 5) or if an invalid method is provided.
        """
        df = self.analysis.get("weighted_metric_variants")
        if df is None:
            raise ValueError("Weighted metric variants not available. Check Step 5.")
        df_agg = df.copy()
        if method == 'power_mean':
            p = 2
            counts = df_agg.notna().sum(axis=1)
            df_agg['project_score'] = ((df_agg.pow(p).sum(axis=1, skipna=True) / counts)**(1 / p)).where(counts > 0)
        elif method == 'sum':
            df_agg['project_score'] = df_agg.sum(axis=1, skipna=True)
        else:
            raise ValueError(f"Invalid aggregation method: {method}")
        self.analysis["aggregated_project_scores"] = df_agg

    # --------------------------------------------------------------------
    # Step 7: Prepare final results
    # --------------------------------------------------------------------
    def _prepare_final_results(self) -> None:
        """
        Flattens multi-level columns from intermediate DataFrames and merges them with the final aggregated scores.
        The final DataFrame is sorted by the normalized weighted score.
        
        Output is stored in:
            self.analysis["final_results"]
        """
        df_pivoted_weighted = self._flatten_columns(self.analysis.get("pivoted_raw_metrics_weighted_by_chain"))
        df_variants = self._flatten_columns(self.analysis.get("pivoted_metric_variants"))
        df_weighted_variants = self._flatten_columns(self.analysis.get("weighted_metric_variants"))
        scores_df = self.analysis.get("aggregated_project_scores")
        if scores_df is None or 'project_score' not in scores_df.columns:
            warnings.warn("Aggregated project scores not found; final results may be incomplete.")
            scores_series = pd.Series(dtype=float)
        else:
            scores_series = scores_df['project_score']
        
        # Apply TVL maximum filter to final scores
        if hasattr(self.config, 'tvl_maximum') and self.config.tvl_maximum > 0:
            scores_series = self._apply_tvl_maximum_filter(scores_series, df_pivoted_weighted)
        
        normalized_series = scores_series / scores_series.sum() if scores_series.sum() != 0 else scores_series
        normalized_series.name = 'weighted_score'

        final_df = (
            df_pivoted_weighted
            # .join(df_variants)
            # .join(df_weighted_variants, lsuffix=' - weighted')
            .join(normalized_series)
            .sort_values('weighted_score', ascending=False)
        )
        #final_df = final_df[['weighted_score']]
        self.analysis["final_results"] = final_df

    def _apply_tvl_maximum_filter(self, scores_series: pd.Series, df_pivoted_weighted: pd.DataFrame) -> pd.Series:
        """
        Apply TVL maximum filter by setting scores to 0 for projects exceeding TVL maximum.
        
        Args:
            scores_series: Series of project scores
            df_pivoted_weighted: DataFrame with weighted metrics data
            
        Returns:
            Series with scores set to 0 for projects exceeding TVL maximum
        """
        # Find TVL metrics in the current period
        current_period = self.config.periods.get('current')
        tvl_columns = [col for col in df_pivoted_weighted.columns 
                      if 'tvl' in col.lower() and current_period.lower().replace(' ', '_') in col.lower()]
        
        if not tvl_columns:
            return scores_series
            
        # Calculate total TVL per project across all TVL metrics
        total_tvl = df_pivoted_weighted[tvl_columns].sum(axis=1)
        
        # Create mask for projects exceeding TVL maximum
        exceeds_max = total_tvl > self.config.tvl_maximum
        
        # Set scores to 0 for projects exceeding maximum
        filtered_scores = scores_series.copy()
        filtered_scores[exceeds_max] = 0
        
        if exceeds_max.any():
            print(f"[INFO] TVL maximum filter: {exceeds_max.sum()} projects exceeded TVL maximum of {self.config.tvl_maximum:,}")
        
        return filtered_scores

    # --------------------------------------------------------------------
    # Helper: Flatten multi-level columns
    # --------------------------------------------------------------------
    def _flatten_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Flattens multi-level columns after pivoting/weighting.

        For tuple columns, it creates intuitive names based on period and variant information.

        Args:
            df (pd.DataFrame): DataFrame with multi-level columns.

        Returns:
            pd.DataFrame: DataFrame with flattened column names.
        """
        def _flat(col):
            if isinstance(col, tuple):
                if col[0] in self.config.periods:
                    return f"{col[1].lower().replace(' ', '_')} [{col[0].lower().replace(' ', '_')}]"
                elif col[1] in self.config.metric_variants:
                    return f"{col[0].lower().replace(' ', '_')}_{col[1].lower()}_variant"
                else:
                    return "_".join(str(x).lower().replace(' ', '_') for x in col)
            return str(col).lower().replace(' ', '_')
        out = df.copy()
        out.columns = [_flat(c) for c in df.columns]
        return out

    # --------------------------------------------------------------------
    # Helper: MinMax Scaling (Static Method)
    # --------------------------------------------------------------------
    @staticmethod
    def _minmax_scale(values: np.ndarray, percentile_cap: float = 100) -> np.ndarray:
        """
        Scale values to [0,1] range using min-max scaling with optional percentile capping.
        
        Args:
            values: Array of values to scale
            percentile_cap: Percentile to cap values at (default: 100, meaning no cap)
            
        Returns:
            Array of scaled values in [0,1] range
        """
        if len(values) == 0:
            return values
            
        # Cap values at specified percentile if less than 100
        if percentile_cap < 100:
            cap_value = np.percentile(values, percentile_cap)
            values = np.minimum(values, cap_value)
            
        # Min-max scale to [0,1]
        min_val = np.min(values)
        max_val = np.max(values)
        
        if max_val == min_val:
            return np.ones_like(values)
            
        return (values - min_val) / (max_val - min_val)


# ------------------------------------------------------------------------
# Configuration and Data Loading Functions
# ------------------------------------------------------------------------

def load_config(config_path: str) -> Tuple[DataSnapshot, SimulationConfig]:
    """
    Loads configuration from a YAML file.

    Args:
        config_path (str): Path to the YAML configuration file.

    Returns:
        Tuple[DataSnapshot, SimulationConfig]: A tuple containing the DataSnapshot and SimulationConfig objects.
    """
    with open(config_path, 'r') as f:
        ycfg = yaml.safe_load(f)

    yaml_name = config_path.split('/')[-1]
    ds = DataSnapshot(
        data_dir=ycfg['data_snapshot'].get('data_dir', "eval-algos/S8/data/onchain_testing"),
        projects_file=ycfg['data_snapshot'].get('projects_file', "projects_v1.csv"),
        metrics_file=ycfg['data_snapshot'].get('metrics_file', "onchain_metrics_by_project.csv"),
        yaml_name=yaml_name
    )

    sim = ycfg.get('simulation', {})
    sc = SimulationConfig(
        periods=sim.get('periods', {}),
        chains=sim.get('chains', {}),
        metrics=sim.get('metrics', {}),
        metric_variants=sim.get('metric_variants', {}),
        tvl_minimum=sim.get('tvl_minimum', 0),
        tvl_maximum=sim.get('tvl_maximum', 0),
        eligibility_filter=sim.get('eligibility_filter', False),
        percentile_cap=sim.get('percentile_cap', 100)
    )

    return ds, sc


def load_data(ds: DataSnapshot) -> pd.DataFrame:
    """
    Loads raw CSV data and merges it with project metadata if available.

    Args:
        ds (DataSnapshot): DataSnapshot object with file location details.

    Returns:
        pd.DataFrame: Merged DataFrame containing raw metrics data.
    """
    def path(filename: str) -> str:
        return os.path.join(ds.data_dir, filename)

    try:
        df_projects = pd.read_csv(path(ds.projects_file))
        df_metrics = pd.read_csv(path(ds.metrics_file))
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Error loading data files: {e}")

    # Derive measurement_period if not present
    if 'measurement_period' not in df_metrics.columns:
        df_metrics['measurement_period'] = pd.to_datetime(df_metrics['sample_date']).dt.strftime('%b %Y')
    
    cols = [c for c in df_projects.columns
            if c in ['project_id', 'is_eligible']]
    df_merged = df_metrics.merge(df_projects[cols], on='project_id', how='left')
    return df_merged

# ------------------------------------------------------------------------
# Main Pipeline Entry-Point and Serialization
# ------------------------------------------------------------------------

def run_simulation(config_path: str) -> Dict[str, Any]:
    """
    Runs the complete simulation pipeline.

    Args:
        config_path (str): Path to the YAML configuration file.

    Returns:
        Dict[str, Any]: Analysis dictionary containing all intermediate outputs and final results.
    """
    ds, sim_cfg = load_config(config_path)
    df_data = load_data(ds)
    
    calculator = OnchainBuildersCalculator(sim_cfg)
    analysis = calculator.run_analysis(df_data)

    # Store configuration references in analysis
    analysis["data_snapshot"] = ds
    analysis["simulation_config"] = sim_cfg

    return analysis


def save_results(analysis: Dict[str, Any]) -> None:
    """
    Saves the final results to a CSV file and logs the output.

    Args:
        analysis (Dict[str, Any]): Analysis dictionary containing the final results.
    """
    ds = analysis.get("data_snapshot")
    if ds is None:
        print("No DataSnapshot found; skipping file output.")
        return

    # Use the actual YAML name from the data snapshot
    yaml_base = ds.yaml_name.replace('.yaml', '')
    out_path = f"{ds.data_dir}/{yaml_base}_results.csv"
    try:
        analysis["final_results"].to_csv(out_path, index=True)
        print(f"[INFO] Saved onchain builders results to {out_path}")
    except Exception as e:
        print(f"[ERROR] Failed to save results: {str(e)}")


def main():
    """
    Test the onchain builders analysis pipeline.
    """
    config_path = f'results/S8/test/weights/onchain__goldilocks.yaml'
    try:
        analysis = run_simulation(config_path)
        save_results(analysis)
    except Exception as e:
        print(f"[ERROR] Error during simulation: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    main()