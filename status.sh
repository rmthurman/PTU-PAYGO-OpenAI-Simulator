#!/bin/bash
# Quick status check for parallel processing

echo "========================================"
echo "PTU ANALYSIS STATUS DASHBOARD"
echo "========================================"
date
echo ""

# Check if process is running
PROCESS_COUNT=$(ps aux | grep -c "[p]ython.*download_azure_logs_parallel")
if [ $PROCESS_COUNT -gt 0 ]; then
    echo "✅ Processing: RUNNING ($PROCESS_COUNT workers active)"
else
    echo "❌ Processing: NOT RUNNING"
fi

echo ""
echo "========================================"
echo "CURRENT PROGRESS:"
echo "========================================"

if [ -f "analysis_output/parallel_processing_with_versions.log" ]; then
    # Get latest progress line
    PROGRESS=$(tail -100 analysis_output/parallel_processing_with_versions.log | grep "Progress:" | tail -1)
    
    if [ -n "$PROGRESS" ]; then
        echo "$PROGRESS"
        
        # Extract numbers for calculations
        CURRENT=$(echo "$PROGRESS" | grep -oE '[0-9,]+/[0-9,]+' | head -1 | cut -d'/' -f1 | tr -d ',')
        TOTAL=$(echo "$PROGRESS" | grep -oE '[0-9,]+/[0-9,]+' | head -1 | cut -d'/' -f2 | tr -d ',')
        
        if [ -n "$CURRENT" ] && [ -n "$TOTAL" ]; then
            REMAINING=$((TOTAL - CURRENT))
            PCT=$((CURRENT * 100 / TOTAL))
            
            echo ""
            echo "Processed:  $CURRENT / $TOTAL blobs"
            echo "Remaining:  $REMAINING blobs"
            echo "Complete:   $PCT%"
            
            # Extract ETA if available
            ETA=$(echo "$PROGRESS" | grep -oE 'ETA: [0-9.]+h' | grep -oE '[0-9.]+')
            if [ -n "$ETA" ]; then
                # Calculate completion time
                COMPLETION_TIME=$(date -v+${ETA}H "+%I:%M %p" 2>/dev/null || date -d "+${ETA} hours" "+%I:%M %p" 2>/dev/null)
                echo "ETA:        ${ETA}h (~$COMPLETION_TIME)"
            fi
        fi
    else
        echo "⏳ Initializing... (waiting for first progress update)"
    fi
    
    # Show entry count
    ENTRIES=$(tail -100 analysis_output/parallel_processing_with_versions.log | grep "Entries:" | tail -1 | grep -oE 'Entries: [0-9,]+' | grep -oE '[0-9,]+' | tr -d ',')
    if [ -n "$ENTRIES" ]; then
        echo ""
        echo "Log Entries: $(printf "%'d" $ENTRIES)"
    fi
else
    echo "Log file not found yet..."
fi

echo ""
echo "========================================"
echo "OUTPUT FILES:"
echo "========================================"
ls -lh analysis_output/*complete_analysis_with_models* 2>/dev/null || echo "No output files yet..."

echo ""
echo "========================================"
echo "SYSTEM RESOURCES:"
echo "========================================"
echo "CPU Usage:"
top -l 1 | grep "CPU usage" | head -1
echo ""
echo "Memory:"
top -l 1 | grep "PhysMem" | head -1

echo ""
echo "========================================"
echo "Monitor logs: tail -f completion_monitor.log"
echo "Live progress: tail -f analysis_output/parallel_processing_with_versions.log | grep Progress"
echo "========================================"
