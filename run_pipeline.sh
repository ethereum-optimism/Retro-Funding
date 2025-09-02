#!/bin/bash

# Function to show usage
show_usage() {
    echo "Usage: ./run_pipeline.sh <season> <period> [options]"
    echo ""
    echo "Required arguments:"
    echo "  season              Season number (7 or 8)"
    echo "  period              Measurement period (e.g., M1, M2)"
    echo ""
    echo "Options:"
    echo "  --algo <type>       Run only specific algorithm (devtooling or onchain)"
    echo "  --weights <name>    Weights file name (e.g., arcturus, goldilocks)"
    echo "  --skip-fetch        Skip the data fetching step"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run_pipeline.sh 8 M5                                    # Run both models"
    echo "  ./run_pipeline.sh 8 M5 --algo devtooling --weights arcturus  # Run only devtooling"
    echo "  ./run_pipeline.sh 8 M5 --skip-fetch                       # Skip data fetching"
    echo "  ./run_pipeline.sh 7 M3 --algo onchain --weights goldilocks --skip-fetch"
}

# Parse command line arguments
SEASON=""
PERIOD=""
ALGO=""
WEIGHTS=""
SKIP_FETCH=false

# Check if help is requested
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    show_usage
    exit 0
fi

# Check if we have at least 2 arguments
if [ $# -lt 2 ]; then
    echo "Error: Missing required arguments"
    show_usage
    exit 1
fi

SEASON=$1
PERIOD=$2
shift 2

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --algo)
            ALGO="$2"
            shift 2
            ;;
        --weights)
            WEIGHTS="$2"
            shift 2
            ;;
        --skip-fetch)
            SKIP_FETCH=true
            shift
            ;;
        *)
            echo "Error: Unknown option $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$SEASON" || -z "$PERIOD" ]]; then
    echo "Error: Season and period are required"
    show_usage
    exit 1
fi

# Validate season
if [[ "$SEASON" != "7" && "$SEASON" != "8" ]]; then
    echo "Error: Season must be 7 or 8"
    exit 1
fi

# Validate algo and weights if provided
if [[ -n "$ALGO" && -z "$WEIGHTS" ]]; then
    echo "Error: --weights is required when --algo is specified"
    exit 1
fi

if [[ -n "$WEIGHTS" && -z "$ALGO" ]]; then
    echo "Error: --algo is required when --weights is specified"
    exit 1
fi

if [[ -n "$ALGO" && "$ALGO" != "devtooling" && "$ALGO" != "onchain" ]]; then
    echo "Error: --algo must be 'devtooling' or 'onchain'"
    exit 1
fi

echo "🚀 Starting Retro Funding pipeline for S${SEASON} - ${PERIOD}"

# 1. Fetch data (unless skipped)
if [[ "$SKIP_FETCH" == false ]]; then
    echo "📥 Fetching data..."
    (cd eval-algos && poetry run python -m core.utils.data_fetcher --season $SEASON --period $PERIOD)
    if [ $? -ne 0 ]; then
        echo "❌ Data fetching failed"
        exit 1
    fi
else
    echo "⏭️ Skipping data fetch..."
fi

# 2. Process models
echo "⚙️ Processing models..."
if [[ -n "$ALGO" && -n "$WEIGHTS" ]]; then
    # Run single model
    echo "  Running ${ALGO} model with ${WEIGHTS} weights..."
    poetry run python -m eval-algos.core.utils.process_models --algo $ALGO --weights $WEIGHTS --season $SEASON --period $PERIOD
else
    # Run both models
    echo "  Running both devtooling and onchain models..."
    poetry run python -m eval-algos.core.utils.process_models --algo devtooling --weights devtooling__arcturus --season $SEASON --period $PERIOD
    poetry run python -m eval-algos.core.utils.process_models --algo onchain --weights onchain__goldilocks --season $SEASON --period $PERIOD
fi

if [ $? -ne 0 ]; then
    echo "❌ Model processing failed"
    exit 1
fi

# 3. Consolidate rewards
echo "📊 Consolidating rewards..."
(cd eval-algos && poetry run python -m core.utils.consolidate_rewards --season $SEASON --period $PERIOD)
if [ $? -ne 0 ]; then
    echo "❌ Rewards consolidation failed"
    exit 1
fi

# 4. Serialize results
echo "💾 Serializing results..."
(cd eval-algos && poetry run python -m core.utils.serialize --season $SEASON --period $PERIOD)
if [ $? -ne 0 ]; then
    echo "❌ Results serialization failed"
    exit 1
fi

echo "✅ Pipeline completed for S${SEASON} - ${PERIOD}"
echo "Results can be found in results/S${SEASON}/${PERIOD}/outputs/" 