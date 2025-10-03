import json
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
from datetime import datetime, timedelta
import pandas as pd

class SensorVisualizer:
    def __init__(self, db_path="sensor_data.db", config_path="Data/waveLengths.json"):
        self.db_path = db_path
        self.config_path = config_path
        self.config = self.load_config()
    
    def load_config(self):
        """Load visualization configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def get_sensor_data(self, hours=1, sensor_type=None, measurement_type=None):
        """Get sensor data with optional filtering"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM sensor_readings 
            WHERE datetime(timestamp) > datetime('now', '-{} hours')
        '''.format(hours)
        
        params = []
        if sensor_type:
            query += ' AND sensor_type = ?'
            params.append(sensor_type)
        if measurement_type:
            query += ' AND measurement_type = ?'
            params.append(measurement_type)
        
        query += ' ORDER BY timestamp DESC'
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def get_map_data(self):
        """Get data formatted for map visualization"""
        data = self.get_sensor_data(hours=24)
        
        # Group data by sensor type and position
        map_data = {
            'environmental': [],
            'proximity': [],
            'movement': []
        }
        
        for reading in data:
            layer_type = self.config.get('sensors_definition', {}).get(
                reading['sensor_type'], {}
            ).get('type', 'other')
            
            if layer_type in map_data:
                map_data[layer_type].append({
                    'x': reading['x_position'],
                    'y': reading['y_position'],
                    'z': reading['z_position'],
                    'value': reading['value'],
                    'measurement': reading['measurement_type'],
                    'sensor': reading['sensor_type'],
                    'timestamp': reading['timestamp']
                })
        
        return map_data
    
    def get_stats(self):
        """Get basic statistics about collected data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total readings
        cursor.execute('SELECT COUNT(*) FROM sensor_readings')
        total_readings = cursor.fetchone()[0]
        
        # Readings by sensor type
        cursor.execute('''
            SELECT sensor_type, COUNT(*) as count 
            FROM sensor_readings 
            GROUP BY sensor_type
        ''')
        sensor_counts = dict(cursor.fetchall())
        
        # Latest reading timestamp
        cursor.execute('SELECT MAX(timestamp) FROM sensor_readings')
        latest_reading = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_readings': total_readings,
            'sensor_counts': sensor_counts,
            'latest_reading': latest_reading,
            'active_sensors': len(sensor_counts)
        }

    def create_2d_map(self, hours=1, save_path="sensor_map.png"):
        """Create a 2D map visualization"""
        data = self.get_sensor_data(hours)
        if not data:
            print("No data available for visualization")
            return
        
        df = pd.DataFrame(data)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle(f'Sensor Map - Last {hours} Hours', fontsize=16)
        
        # Temperature map
        temp_data = df[df['measurement_type'] == 'temperature']
        if not temp_data.empty:
            scatter = axes[0,0].scatter(temp_data['x_position'], temp_data['y_position'], 
                                      c=temp_data['value'], cmap='coolwarm', s=100, alpha=0.7)
            axes[0,0].set_title('Temperature Distribution')
            axes[0,0].set_xlabel('X Position (m)')
            axes[0,0].set_ylabel('Y Position (m)')
            plt.colorbar(scatter, ax=axes[0,0], label='Temperature (°C)')
        
        # Pressure map
        pressure_data = df[df['measurement_type'] == 'pressure']
        if not pressure_data.empty:
            scatter = axes[0,1].scatter(pressure_data['x_position'], pressure_data['y_position'], 
                                      c=pressure_data['value'], cmap='viridis', s=100, alpha=0.7)
            axes[0,1].set_title('Pressure Distribution')
            axes[0,1].set_xlabel('X Position (m)')
            axes[0,1].set_ylabel('Y Position (m)')
            plt.colorbar(scatter, ax=axes[0,1], label='Pressure (hPa)')
        
        # Obstacle detection
        obstacle_data = df[df['measurement_type'] == 'obstacle_detected']
        if not obstacle_data.empty:
            colors = ['green' if x == 0 else 'red' for x in obstacle_data['value']]
            axes[1,0].scatter(obstacle_data['x_position'], obstacle_data['y_position'], 
                            c=colors, s=100, alpha=0.7)
            axes[1,0].set_title('Obstacle Detection')
            axes[1,0].set_xlabel('X Position (m)')
            axes[1,0].set_ylabel('Y Position (m)')
            axes[1,0].legend(['Clear', 'Obstacle'])
        
        # Activity heatmap
        activity_map = df.groupby(['x_position', 'y_position']).size().reset_index(name='count')
        if not activity_map.empty:
            scatter = axes[1,1].scatter(activity_map['x_position'], activity_map['y_position'], 
                                      c=activity_map['count'], cmap='hot', s=200, alpha=0.7)
            axes[1,1].set_title('Sensor Activity Heatmap')
            axes[1,1].set_xlabel('X Position (m)')
            axes[1,1].set_ylabel('Y Position (m)')
            plt.colorbar(scatter, ax=axes[1,1], label='Reading Count')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"Map saved as {save_path}")
    
    def create_3d_map(self, hours=1, save_path="sensor_map_3d.png"):
        """Create a 3D map visualization"""
        data = self.get_sensor_data(hours)
        if not data:
            print("No data available for visualization")
            return
        
        fig = plt.figure(figsize=(15, 10))
        
        # 3D scatter plot
        ax1 = fig.add_subplot(221, projection='3d')
        df = pd.DataFrame(data)
        
        # Color by sensor type
        sensor_types = df['sensor_type'].unique()
        colors = plt.cm.tab10(np.linspace(0, 1, len(sensor_types)))
        color_map = dict(zip(sensor_types, colors))
        
        for sensor_type in sensor_types:
            sensor_data = df[df['sensor_type'] == sensor_type]
            ax1.scatter(sensor_data['x_position'], sensor_data['y_position'], 
                       sensor_data['z_position'], c=[color_map[sensor_type]], 
                       label=sensor_type, s=60, alpha=0.7)
        
        ax1.set_xlabel('X Position (m)')
        ax1.set_ylabel('Y Position (m)')
        ax1.set_zlabel('Z Position (m)')
        ax1.set_title('3D Sensor Positions')
        ax1.legend()
        
        # Temperature over time
        ax2 = fig.add_subplot(222)
        temp_data = df[df['measurement_type'] == 'temperature']
        if not temp_data.empty:
            temp_data['timestamp'] = pd.to_datetime(temp_data['timestamp'])
            ax2.plot(temp_data['timestamp'], temp_data['value'], 'r-', marker='o')
            ax2.set_title('Temperature Over Time')
            ax2.set_ylabel('Temperature (°C)')
            ax2.tick_params(axis='x', rotation=45)
        
        # Pressure over time
        ax3 = fig.add_subplot(223)
        pressure_data = df[df['measurement_type'] == 'pressure']
        if not pressure_data.empty:
            pressure_data['timestamp'] = pd.to_datetime(pressure_data['timestamp'])
            ax3.plot(pressure_data['timestamp'], pressure_data['value'], 'b-', marker='o')
            ax3.set_title('Pressure Over Time')
            ax3.set_ylabel('Pressure (hPa)')
            ax3.tick_params(axis='x', rotation=45)
        
        # Statistics
        ax4 = fig.add_subplot(224)
        stats = self.get_stats()
        stat_labels = list(stats['sensor_counts'].keys())
        stat_values = list(stats['sensor_counts'].values())
        ax4.pie(stat_values, labels=stat_labels, autopct='%1.1f%%')
        ax4.set_title('Sensor Data Distribution')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"3D Map saved as {save_path}")
    
    def create_live_dashboard(self, update_interval=5):
        """Create a live updating dashboard"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('Live Sensor Dashboard', fontsize=16)
        
        def update_plots(frame):
            for ax in axes.flat:
                ax.clear()
            
            data = self.get_sensor_data(hours=1)
            if not data:
                return
            
            df = pd.DataFrame(data)
            
            # Temperature trend
            temp_data = df[df['measurement_type'] == 'temperature']
            if not temp_data.empty:
                temp_data['timestamp'] = pd.to_datetime(temp_data['timestamp'])
                temp_data = temp_data.sort_values('timestamp')
                axes[0,0].plot(temp_data['timestamp'], temp_data['value'], 'r-o')
                axes[0,0].set_title('Temperature Trend')
                axes[0,0].set_ylabel('Temperature (°C)')
                axes[0,0].tick_params(axis='x', rotation=45)
            
            # Pressure trend
            pressure_data = df[df['measurement_type'] == 'pressure']
            if not pressure_data.empty:
                pressure_data['timestamp'] = pd.to_datetime(pressure_data['timestamp'])
                pressure_data = pressure_data.sort_values('timestamp')
                axes[0,1].plot(pressure_data['timestamp'], pressure_data['value'], 'b-o')
                axes[0,1].set_title('Pressure Trend')
                axes[0,1].set_ylabel('Pressure (hPa)')
                axes[0,1].tick_params(axis='x', rotation=45)
            
            # Real-time sensor positions
            for sensor_type in df['sensor_type'].unique():
                sensor_data = df[df['sensor_type'] == sensor_type]
                latest_data = sensor_data.iloc[-1] if not sensor_data.empty else None
                if latest_data is not None:
                    axes[1,0].scatter(latest_data['x_position'], latest_data['y_position'], 
                                    s=100, label=sensor_type, alpha=0.7)
            axes[1,0].set_title('Current Sensor Positions')
            axes[1,0].set_xlabel('X Position (m)')
            axes[1,0].set_ylabel('Y Position (m)')
            axes[1,0].legend()
            
            # Statistics
            stats = self.get_stats()
            stat_text = f"Total Readings: {stats['total_readings']}\n"
            stat_text += f"Active Sensors: {stats['active_sensors']}\n"
            if stats['latest_reading']:
                latest_time = datetime.fromisoformat(stats['latest_reading'])
                stat_text += f"Last Update: {latest_time.strftime('%H:%M:%S')}"
            axes[1,1].text(0.1, 0.5, stat_text, fontsize=12, transform=axes[1,1].transAxes)
            axes[1,1].set_title('System Statistics')
            axes[1,1].axis('off')
            
            plt.tight_layout()
        
        ani = animation.FuncAnimation(fig, update_plots, interval=update_interval*1000)
        plt.show()
        return ani
    

if __name__ == '__main__':
    visualizer = SensorVisualizer()
    
    print("Sensor Map Visualizer")
    print("1. Create 2D Map")
    print("2. Create 3D Map") 
    print("3. Live Dashboard")
    print("4. Show Statistics")
    
    choice = input("Enter choice (1-4): ")
    
    if choice == '1':
        hours = int(input("Hours of data to display (default 1): ") or 1)
        visualizer.create_2d_map(hours=hours)
    elif choice == '2':
        hours = int(input("Hours of data to display (default 1): ") or 1)
        visualizer.create_3d_map(hours=hours)
    elif choice == '3':
        print("Starting live dashboard... Close the window to stop.")
        ani = visualizer.create_live_dashboard()
        input("Press Enter to stop...")
    elif choice == '4':
        stats = visualizer.get_stats()
        print("\nSystem Statistics:")
        print(f"Total Readings: {stats['total_readings']}")
        print(f"Active Sensors: {stats['active_sensors']}")
        print(f"Latest Reading: {stats['latest_reading']}")
        print("Sensor Counts:")
        for sensor, count in stats['sensor_counts'].items():
            print(f"  {sensor}: {count}")
    else:
        print("Invalid choice")