#!/bin/bash

set -eo pipefail


SCRIPT_DIR="$(dirname "$0")"
source "$SCRIPT_DIR"/../../.env

SCENARIO="scenario1"
OS_USER=$TEST_GEN_OPENSEARCH_USERNAME
OS_PW=$TEST_GEN_OPENSEARCH_PASSWORD


print_usage() {
    printf "Usage: ./create_all_indices.sh -s [scenario_name] [-h for usage] \n"
}


while getopts 's:h' flag; do
    case "${flag}" in
        s) SCENARIO="${OPTARG}" ;;
        h) print_usage
           exit 0 ;;
        *) print_usage
           exit 1 ;;
    esac
done

echo "Removing test event index"
curl -XDELETE --insecure -u "$OS_USER":"$OS_PW" https://localhost:9200/test_event_index
echo "Indexing event data"
./scripts/index_data.sh -n test_event_index -i "$SCRIPT_DIR"/../functional_test_generation/index_data/"$SCENARIO"/test_event_index.ndjson -s "$SCRIPT_DIR"/../functional_test_generation/index_data/event_index_schema.json

echo "Removing test query index"
curl -XDELETE --insecure -u "$OS_USER":"$OS_PW" https://localhost:9200/test_query_index
echo "Indexing query data"
./scripts/index_data.sh -n test_query_index -i "$SCRIPT_DIR"/../functional_test_generation/index_data/"$SCENARIO"/test_query_index.ndjson -s "$SCRIPT_DIR"/../functional_test_generation/index_data/query_index_schema.json

echo "Removing test doc index"
curl -XDELETE --insecure -u "$OS_USER":"$OS_PW" https://localhost:9200/test_doc_index
echo "Indexing doc data"
./scripts/index_data.sh -n test_doc_index -i "$SCRIPT_DIR"/../functional_test_generation/index_data/"$SCENARIO"/test_doc_index.ndjson -s "$SCRIPT_DIR"/../functional_test_generation/index_data/doc_index_schema.json
