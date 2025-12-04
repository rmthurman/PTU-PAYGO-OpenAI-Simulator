#!/bin/bash
# Monitor the parallel processing progress

echo "Monitoring parallel processing..."
echo "Press Ctrl+C to stop monitoring (processing will continue)"
echo ""

while true; do
    clear
    echo "========================================"
    echo "PARALLEL PROCESSING MONITOR"
    echo "========================================"
    date
    echo ""
    
    # Show last 30 lines of log
    if [ -f "analysis_output/parallel_processing.log" ]; then
        echo "Latest progress:"
        tail -30 analysis_output/parallel_processing.log | grep -E "(Progress:|Entries:|Rate:|ETA:|Processing:|Found|Starting|COMPLETE)"
    else
        echo "Log file not found yet..."
    fi
    
    echo ""
    echo "========================================"
    echo "Press Ctrl+C to exit monitor"
    echo "========================================"
    
    sleep 10
done
