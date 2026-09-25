#!/bin/bash
set -e
echo "Starting Case 2..."
PYTHONPATH=src python3 -m project_audit --target ../../../auditoring/test3/case2_full_no_fix/smartserv --phase full --allow-external > ../../../auditoring/test3/case2_full_no_fix/execution.log 2>&1
echo "Case 2 Finished."

echo "Starting Case 3..."
PYTHONPATH=src python3 -m project_audit --target ../../../auditoring/test3/case3_full_autofix/smartserv --phase full --auto-fix-p1 --allow-external > ../../../auditoring/test3/case3_full_autofix/execution.log 2>&1
echo "Case 3 Finished."
