#!/usr/bin/env bash
# semehr_fix_vm_settings.sh
set -e

# -----------------------------------------------------------------------------
# Fix Linux virtual memory settings
# -----------------------------------------------------------------------------

TARGET_VM_SIZE=262144


echo "- vm.max_map_count is:"
sysctl vm.max_map_count  # read

echo "- Setting vm.max_map_count to: ${TARGET_VM_SIZE}"
sudo sysctl -w vm.max_map_count=${TARGET_VM_SIZE}  # write

echo "- vm.max_map_count is now:"
sysctl vm.max_map_count  # re-read, should have changed
