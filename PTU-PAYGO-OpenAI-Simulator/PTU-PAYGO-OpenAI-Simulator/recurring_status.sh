#!/bin/bash
# Recurring status updates every 30 minutes

INTERVAL=1800  # 30 minutes in seconds
LOG_FILE="status_updates.log"

echo "========================================"
echo "RECURRING STATUS MONITOR"
echo "========================================"
echo "Update interval: 30 minutes"
echo "Started at: $(date)"
echo "Log file: $LOG_FILE"
echo ""
echo "Press Ctrl+C to stop monitoring"
echo "========================================"
echo ""

# Function to show status
show_status() {
    echo "" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "STATUS UPDATE: $(date)" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    
    # Check if process is running
    if ps aux | grep -q "[d]ownload_azure_logs_parallel.py"; then
        echo "✅ Status: RUNNING" | tee -a "$LOG_FILE"
        
        # Get latest progress
        PROGRESS=$(tail -100 analysis_output/parallel_processing_with_versions.log 2>/dev/null | grep "Progress:" | tail -1)
        
        if [ -n "$PROGRESS" ]; then
            echo "" | tee -a "$LOG_FILE"
            echo "$PROGRESS" | tee -a "$LOG_FILE"
            
            # Extract and calculate
            CURRENT=$(echo "$PROGRESS" | grep -oE '[0-9,]+/[0-9,]+' | head -1 | cut -d'/' -f1 | tr -d ',')
            TOTAL=$(echo "$PROGRESS" | grep -oE '[0-9,]+/[0-9,]+' | head -1 | cut -d'/' -f2 | tr -d ',')
            
            if [ -n "$CURRENT" ] && [ -n "$TOTAL" ]; then
                REMAINING=$((TOTAL - CURRENT))
                PCT=$((CURRENT * 100 / TOTAL))
                
                echo "" | tee -a "$LOG_FILE"
                echo "Progress:   $PCT% complete" | tee -a "$LOG_FILE"
                echo "Processed:  $(printf "%'d" $CURRENT) blobs" | tee -a "$LOG_FILE"
                echo "Remaining:  $(printf "%'d" $REMAINING) blobs" | tee -a "$LOG_FILE"
                
                # Extract ETA
                ETA=$(echo "$PROGRESS" | grep -oE 'ETA: [0-9.]+h' | grep -oE '[0-9.]+')
                if [ -n "$ETA" ]; then
                    # Calculate completion time (macOS compatible)
                    COMPLETION_TIME=$(date -v+${ETA}H "+%I:%M %p" 2>/dev/null)
                    echo "ETA:        ${ETA}h (~$COMPLETION_TIME)" | tee -a "$LOG_FILE"
                fi
                
                # Extract entry count
                ENTRIES=$(echo "$PROGRESS" | grep -oE 'Entries: [0-9,]+' | grep -oE '[0-9,]+' | tr -d ',')
                if [ -n "$ENTRIES" ]; then
                    echo "Entries:    $(printf "%'d" $ENTRIES)" | tee -a "$LOG_FILE"
                fi
            fi
        else
            echo "⏳ Initializing..." | tee -a "$LOG_FILE"
        fi
        
        # System resources
        echo "" | tee -a "$LOG_FILE"
        echo "System Resources:" | tee -a "$LOG_FILE"
        top -l 1 | grep "CPU usage" | head -1 | tee -a "$LOG_FILE"
        top -l 1 | grep "PhysMem" | head -1 | tee -a "$LOG_FILE"
        
    else
        echo "❌ Status: NOT RUNNING" | tee -a "$LOG_FILE"
        
        # Check if completed
        if grep -q "PROCESSING COMPLETE" analysis_output/parallel_processing_with_versions.log 2>/dev/null; then
            echo "" | tee -a "$LOG_FILE"
            echo "🎉 PROCESSING COMPLETE!" | tee -a "$LOG_FILE"
            echo "" | tee -a "$LOG_FILE"
            echo "Output files:" | tee -a "$LOG_FILE"
            ls -lh analysis_output/*complete_analysis_with_models* 2>/dev/null | tee -a "$LOG_FILE"
            
            echo "" | tee -a "$LOG_FILE"
            echo "Next step: Run batch analysis" | tee -a "$LOG_FILE"
            echo "  python3 batch_analyze_models.py --csv analysis_output/nvstrgitentint_complete_analysis_with_models.csv" | tee -a "$LOG_FILE"
            
            # Exit monitor since we're done
            echo "" | tee -a "$LOG_FILE"
            echo "Monitor stopping - processing complete!" | tee -a "$LOG_FILE"
            exit 0
        else
            echo "⚠️  Process may have stopped unexpectedly" | tee -a "$LOG_FILE"
        fi
    fi
    
    echo "========================================" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
}

# Show initial status immediately
show_status

# Then show every 30 minutes
while true; do
    sleep $INTERVAL
    show_status
    
    # Optional: Send notification every 2 hours (4 cycles)
    CYCLE_COUNT=$((CYCLE_COUNT + 1))
    if [ $((CYCLE_COUNT % 4)) -eq 0 ]; then
        if ps aux | grep -q "[d]ownload_azure_logs_parallel.py"; then
            osascript -e 'display notification "Processing still running. Check status_updates.log for details." with title "PTU Analysis Update"' 2>/dev/null
        fi
    fi
done
