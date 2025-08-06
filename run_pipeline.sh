#!/bin/bash

# Check if measurement period is provided
if [ -z "$1" ]; then
    echo "Usage: ./run_pipeline.sh <measurement_period>"
    echo "Example: ./run_pipeline.sh M5"
    exit 1
fi

MEASUREMENT_PERIOD=$1

echo "🚀 Starting Retro Funding pipeline for $MEASUREMENT_PERIOD"

# 1. Fetch data
echo "📥 Fetching data..."
poetry run python eval-algos/S7/utils/fetch_data.py --measurement-period $MEASUREMENT_PERIOD

# 2. Process onchain builders
echo "⚙️ Processing onchain builders..."
poetry run python eval-algos/S7/utils/process_onchain_builders.py --measurement-period $MEASUREMENT_PERIOD --model onchain__goldilocks

# 3. Process devtools
echo "⚙️ Processing devtools..."
poetry run python eval-algos/S7/utils/process_devtools.py --measurement-period $MEASUREMENT_PERIOD --model devtooling__arcturus

# 4. Consolidate rewards
echo "📊 Consolidating rewards..."
poetry run python eval-algos/S7/utils/consolidate_rewards.py --measurement-period $MEASUREMENT_PERIOD

# 5. Serialize results
echo "💾 Serializing results..."
poetry run python eval-algos/S7/utils/serialize.py --measurement-period $MEASUREMENT_PERIOD

echo "✅ Pipeline completed for $MEASUREMENT_PERIOD"
echo "Results can be found in results/S7/$MEASUREMENT_PERIOD/outputs/" 