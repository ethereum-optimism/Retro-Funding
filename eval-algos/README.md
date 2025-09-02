# Retro Funding Evaluation Algorithms

This directory contains the refactored evaluation algorithms for Retro Funding, designed to eliminate code duplication and improve maintainability.

## New Structure

### `core/` - Shared Core Functionality
- **`config.py`** - Unified configuration management for all seasons
- **`allocator.py`** - Shared allocation logic for funding distribution
- **`utils/`** - Shared utility functions
  - **`data_fetcher.py`** - Generic data fetching from OSO
  - **`rewards_consolidator.py`** - Generic rewards consolidation

### `seasons/` - Season-Specific Implementations
- **`base.py`** - Abstract base class for seasons
- **`s7.py`** - Season 7 specific configuration and logic
- **`s8.py`** - Season 8 specific configuration and logic

### `scripts/` - Unified CLI Scripts
- **`fetch_data.py`** - Fetch data for any season
- **`process_devtools.py`** - Process devtools for any season
- **`process_onchain.py`** - Process onchain builders for any season
- **`consolidate_rewards.py`** - Consolidate rewards for any season
- **`serialize.py`** - Serialize results for any season

### `models/` - Shared Model Implementations
- **`allocator.py`** - Funding allocation algorithms

## Usage

### Running the Pipeline

The pipeline now supports both seasons:

```bash
# For Season 8
./run_pipeline.sh 8 M5

# For Season 7
./run_pipeline.sh 7 M3
```

### Individual Scripts

Each script can be run independently with season specification:

```bash
# Fetch data
poetry run python eval-algos/scripts/fetch_data.py --season 8 --measurement-period M5

# Process devtools
poetry run python eval-algos/scripts/process_devtools.py --season 8 --measurement-period M5 --model devtooling__arcturus

# Consolidate rewards
poetry run python eval-algos/scripts/consolidate_rewards.py --season 8 --measurement-period M5
```

## Benefits of Refactoring

1. **Eliminated Duplication**: No more duplicate code between S7 and S8
2. **Single Source of Truth**: Core logic is defined once in `core/`
3. **Easier Maintenance**: Changes only need to be made in one place
4. **Season Flexibility**: Easy to add new seasons without duplicating code
5. **Better Testing**: Shared components can be tested once
6. **Cleaner Architecture**: Clear separation of concerns

## Migration Status

- ✅ **Phase 1**: New core structure created
- ✅ **Phase 2**: Unified scripts created
- ✅ **Phase 3**: Pipeline updated
- 🔄 **Phase 4**: Testing and validation needed
- ⏳ **Phase 5**: Old duplicated code removal (after validation)

## Adding New Seasons

To add a new season (e.g., S9):

1. Create `eval-algos/seasons/s9.py` extending `BaseSeason`
2. Implement required abstract methods
3. Add season choice to script argument parsers
4. Update season factory functions

## Backward Compatibility

The refactoring maintains backward compatibility by:
- Keeping existing S7 and S8 directories intact during migration
- Providing convenience functions in core config
- Allowing gradual migration of existing code

## Testing

Before removing old code, test the new structure:

```bash
# Test Season 8
./run_pipeline.sh 8 test

# Test Season 7
./run_pipeline.sh 7 test
```

## Future Improvements

- Add proper logging throughout the pipeline
- Implement centralized error handling
- Add input validation and type hints
- Create unit tests for shared components
- Add environment-based configuration
