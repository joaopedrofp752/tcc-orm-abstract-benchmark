#!/usr/bin/env bash
# Enforce strict execution mode: exit on error (-e), undefined vars (-u), or pipe failures (-o pipefail)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INITIAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
STRATEGIES=("hibernate" "hibernate-dto" "jdbc")
INTER_STRATEGY_COOLDOWN=180 # 3 minutes cooldown for CPU thermal equilibrium

# Trap handler: ensure environment teardown and Git branch restore on SIGINT/SIGTERM
cleanup_on_interrupt() {
    echo ""
    echo "  ! Interruption detected (SIGINT/SIGTERM)."
    echo "  ! Cleaning up lab environment before exit..."
    "$ROOT_DIR/down-lab.sh" > /dev/null 2>&1 || true
    git switch "$INITIAL_BRANCH" > /dev/null 2>&1 || true
    echo "  ! Environment safely restored to initial branch [$INITIAL_BRANCH]."
    exit 130
}
trap cleanup_on_interrupt SIGINT SIGTERM

echo "Master benchmark orchestrator initialized"
echo "Target strategies: ${STRATEGIES[*]}"
echo "Workload sequence: nominal (300 RPS) -> saturation (1,200 RPS)"

# Abort if uncommitted files exist to prevent merge or checkout conflicts
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Error: Working directory has uncommitted changes." >&2
    echo "Commit or stash changes before running orchestrator." >&2
    git status -s
    exit 1
fi

# Execute experimental batteries sequentially across all persistence strategies
for i in "${!STRATEGIES[@]}"; do
    STRATEGY="${STRATEGIES[$i]}"
    
    echo ""
    echo "Starting experimental block [$((i + 1))/${#STRATEGIES[@]}]: Strategy [$STRATEGY]"
    
    # Switch Git branch to targeted persistence implementation
    git switch "$STRATEGY"
    
    # Initialize database container and launch Spring Boot backend
    ./up-lab.sh
    
    # Execute nominal workload battery (300 RPS - 10 runs)
    ./run-battery.sh --nominal "$STRATEGY"
    
    # Execute saturation workload battery (1,200 RPS - 10 runs)
    ./run-battery.sh --saturation "$STRATEGY"
    
    # Stop application and destroy database container and volume
    ./down-lab.sh
    
    # Apply hardware cooldown between strategies to minimize thermal throttling
    if [[ $((i + 1)) -lt ${#STRATEGIES[@]} ]]; then
        echo ""
        echo "Cooling down hardware between strategies ($INTER_STRATEGY_COOLDOWN seconds)..."
        for ((sec=INTER_STRATEGY_COOLDOWN; sec>0; sec--)); do
            printf "\r  - Thermal settling: %3ds remaining..." "$sec"
            sleep 1
        done
        printf "\r  - Hardware cooled down and ready.                                  \n"
    fi
done

# Restore original Git branch
echo ""
echo "Returning to initial branch [$INITIAL_BRANCH]..."
git switch "$INITIAL_BRANCH"

# Execute data analysis pipeline across all collected raw metrics
echo ""
echo "Triggering consolidated data analysis pipeline..."
./run-analysis.sh

echo ""
echo "All benchmarks and analyses completed successfully."
echo "  - Final Dataset: data-analysis/processed-data/dataset_final.csv"
echo "  - Visualizations: data-analysis/figures/"
