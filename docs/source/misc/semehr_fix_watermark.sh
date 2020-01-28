#!/usr/bin/env bash
# semehr_fix_watermark.sh
set -e

# -----------------------------------------------------------------------------
# Fix an Elasticsearch error (needed once only, but no harm in repeating):
# -----------------------------------------------------------------------------

echo "- Fixing watermark for Elasticsearch (which should be running already)..."
curl -X PUT "localhost:8200/_cluster/settings" -H 'Content-Type: application/json' -d'
    {
      "transient": {
        "cluster.routing.allocation.disk.watermark.low": "2gb",
        "cluster.routing.allocation.disk.watermark.high": "1gb",
        "cluster.routing.allocation.disk.watermark.flood_stage": "500mb",
        "cluster.info.update.interval": "1m"
      }
    }
'
