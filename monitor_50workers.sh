#!/bin/bash
# Monitor the 50-worker parallel processing run

LOG_FILE="analysis_output/parallel_processing_50workers.log"
MONITOR_INTERVAL=300  # 5 minutes

echo "=========================================="
echo "50-Worker Processing Monitor"
echo "Started: $(date)"
echo "Monitoring: $LOG_FILE"
echo "Update interval: ${MONITOR_INTERVAL}s (5 min)"
echo "=========================================="
echo ""

while true; do
    clear
    echo "=========================================="
    echo "PROGRESS UPDATE - $(date)"
    echo "=========================================="
    echo ""
    
    # Check if process is still running
    if ps aux | grep -v grep | grep "download_azure_logs_parallel.py.*50.*workers" > /dev/null; then
        echo "✅ Process Status: RUNNING"
    else
        echo "❌ Process Status: NOT RUNNING"
        echo ""
        echo "Process may have completed or crashed. Check log file."
        break
    fi
    
    echo ""
    echo "--- Latest Progress ---"
    grep -E "Progress:|ETA:" "$LOG_FILE" | tail -5
    
    echo ""
    echo "--- Log File Size ---"
    ls -lh "$LOG_FILE" | awk '{print $5}'
    
    echo ""
    echo "--- Recent Errors (last 10) ---"
    grep "Failed:" "$LOG_FILE" | tail -10 | cut -d'/' -f9- | cut -c1-80
    
    echo ""
    echo "--- System Load ---"
    uptime
    
    echo ""
    echo "--- Memory Usage ---"
    vm_stat | perl -ne '/page size of (\d+)/ and $size=$1; /Pages\s+([^:]+)[^\d]+(\d+)/ and printf("%-16s % 16.2f Mi\n", "$1:", $2 * $size / 1048576);'
    
    echo ""
    echo "=========================================="
    echo "Next update in ${MONITOR_INTERVAL}s..."
    echo "Press Ctrl+C to stop monitoring"
    echo "=========================================="
    
    sleep $MONITOR_INTERVAL
done

echo ""
echo "Monitoring stopped at $(date)"
