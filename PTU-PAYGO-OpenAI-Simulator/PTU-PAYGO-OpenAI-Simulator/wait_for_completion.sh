#!/bin/bash
# Completion notification script
# Checks if parallel processing is complete and sends notification

LOG_FILE="analysis_output/parallel_processing_with_versions.log"
CHECK_INTERVAL=300  # Check every 5 minutes

echo "=================================="
echo "COMPLETION MONITOR STARTED"
echo "=================================="
echo "Monitoring: $LOG_FILE"
echo "Check interval: $CHECK_INTERVAL seconds (5 minutes)"
echo "Started at: $(date)"
echo ""

while true; do
    # Check if processing is complete
    if grep -q "PROCESSING COMPLETE" "$LOG_FILE" 2>/dev/null; then
        echo ""
        echo "=================================="
        echo "🎉 PROCESSING COMPLETE!"
        echo "=================================="
        date
        echo ""
        
        # Show summary
        echo "SUMMARY:"
        grep -A 20 "PROCESSING COMPLETE" "$LOG_FILE"
        
        # Check for output files
        echo ""
        echo "OUTPUT FILES:"
        ls -lh analysis_output/*complete_analysis_with_models* 2>/dev/null
        
        # Send system notification (macOS)
        osascript -e 'display notification "Azure log processing complete! 120,124 blobs processed with model versions." with title "PTU Analysis Ready" sound name "Glass"'
        
        # Play a sound
        afplay /System/Library/Sounds/Glass.aiff 2>/dev/null
        
        echo ""
        echo "=================================="
        echo "NEXT STEPS:"
        echo "=================================="
        echo "1. Review the report:"
        echo "   cat analysis_output/nvstrgitentint_complete_analysis_with_models_report.txt"
        echo ""
        echo "2. Run batch analysis on all models:"
        echo "   python3 batch_analyze_models.py --csv analysis_output/nvstrgitentint_complete_analysis_with_models.csv"
        echo ""
        echo "3. Or analyze specific models in the Streamlit app"
        echo "=================================="
        
        break
    fi
    
    # Show progress update
    LAST_PROGRESS=$(tail -20 "$LOG_FILE" 2>/dev/null | grep "Progress:" | tail -1)
    if [ -n "$LAST_PROGRESS" ]; then
        echo "[$(date +%H:%M:%S)] $LAST_PROGRESS"
    else
        echo "[$(date +%H:%M:%S)] Processing... (no progress update yet)"
    fi
    
    # Wait before next check
    sleep $CHECK_INTERVAL
done

echo ""
echo "Monitor exiting at: $(date)"
