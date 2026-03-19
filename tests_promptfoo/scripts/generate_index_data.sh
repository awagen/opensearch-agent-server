#!/bin/bash

set -eo pipefail

SCRIPT_DIR="$(dirname "$0")"

python "$SCRIPT_DIR"/../functional_test_generation/src/index_gen/index_scenarios.py --scenario_name scenario1
