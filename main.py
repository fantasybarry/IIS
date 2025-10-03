#!/usr/bin/env python3
"""
Main script for the DataReceiver sensor mapping system.
Run this to start data collection and visualization.
"""

import sys
import time
from initializer.preProcess import dataCollector
from initializer.visualizer import SensorVisualizer
import threading

def main():
    print("🗺️  DataReceiver - Sensor Mapping System")
    print("=" * 50)
    
    try:
        # Initialize data collector
        print("Initializing sensor data collector...")
        collector = dataCollector()
        
        # Initialize visualizer  
        visualizer = SensorVisualizer()
        
        print("✅ System initialized successfully!")
        print(f"✅ Found {len(collector.sensors)} active sensors")
        
        # Show menu
        while True:
            print("\nSelect an option:")
            print("1. Start data collection (continuous)")
            print("2. Collect single data sample")
            print("3. View 2D sensor map")
            print("4. View 3D sensor map") 
            print("5. Start live dashboard")
            print("6. Show system statistics")
            print("7. Export data")
            print("0. Exit")
            
            choice = input("\nEnter choice (0-7): ").strip()
            
            if choice == '0':
                print("Goodbye! 👋")
                break
                
            elif choice == '1':
                print("\nStarting continuous data collection...")
                print("Press Ctrl+C to stop collection")
                try:
                    interval = int(input("Collection interval in seconds (default 5): ") or 5)
                    collector.start_continuous_collection(interval)
                except KeyboardInterrupt:
                    print("\n✅ Data collection stopped")
                    
            elif choice == '2':
                print("\nCollecting single data sample...")
                readings = collector.collect_all_data()
                print(f"✅ Collected {len(readings)} readings:")
                for reading in readings:
                    print(f"  {reading['sensor_type']}.{reading['measurement_type']}: {reading['value']}")
                    
            elif choice == '3':
                hours = int(input("Hours of data to display (default 1): ") or 1)
                print(f"Creating 2D map for last {hours} hours...")
                visualizer.create_2d_map(hours=hours)
                
            elif choice == '4':
                hours = int(input("Hours of data to display (default 1): ") or 1)
                print(f"Creating 3D map for last {hours} hours...")
                visualizer.create_3d_map(hours=hours)
                
            elif choice == '5':
                print("Starting live dashboard...")
                print("Close the plot window to return to menu")
                ani = visualizer.create_live_dashboard()
                input("Press Enter when done...")
                
            elif choice == '6':
                stats = visualizer.get_stats()
                print("\n📊 System Statistics:")
                print("-" * 30)
                print(f"Total Readings: {stats['total_readings']:,}")
                print(f"Active Sensors: {stats['active_sensors']}")
                print(f"Latest Reading: {stats['latest_reading'] or 'No data'}")
                print("\nSensor Data Counts:")
                for sensor, count in stats['sensor_counts'].items():
                    print(f"  📡 {sensor}: {count:,} readings")
                    
            elif choice == '7':
                print("\n📁 Export Options:")
                print("1. Export as CSV")
                print("2. Export as JSON")
                export_choice = input("Choose format (1-2): ")
                hours = int(input("Hours of data to export (default 24): ") or 24)
                
                data = visualizer.get_sensor_data(hours)
                if not data:
                    print("❌ No data available to export")
                    continue
                
                if export_choice == '1':
                    import pandas as pd
                    df = pd.DataFrame(data)
                    filename = f"sensor_data_{hours}h.csv"
                    df.to_csv(filename, index=False)
                    print(f"✅ Data exported to {filename}")
                    
                elif export_choice == '2':
                    import json
                    filename = f"sensor_data_{hours}h.json"
                    with open(filename, 'w') as f:
                        json.dump(data, f, indent=2)
                    print(f"✅ Data exported to {filename}")
                    
            else:
                print("❌ Invalid choice. Please try again.")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your sensor connections and configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())