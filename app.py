from __future__ import annotations
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time
import json

# Set page configuration (must be the first Streamlit command)
st.set_page_config(
    page_title="AIOps Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
PROMETHEUS_URL = "http://localhost:9091"
REFRESH_INTERVAL = 15  # seconds

# Custom CSS for modern look
st.markdown("""
<style>
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #1a1a1a;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #ffffff;
    }
    
    /* Make sidebar headers bright */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .stButton button {
        background-color: #2c3e50;
        color: white;
        border: 1px solid #34495e;
    }
    
    [data-testid="stSidebar"] .stSlider {
        color: white;
    }
    
    [data-testid="stSidebar"] .stCheckbox {
        color: white;
    }
    
    [data-testid="stSidebar"] .stSelectbox {
        color: white;
    }
    
    /* Main container */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Cards */
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    
    /* Titles */
    h1 {
        color: #2c3e50;
    }
    
    /* Sidebar */
    .sidebar .sidebar-content {
        background-color: #2c3e50;
        color: white;
    }
    
    /* Custom progress bars */
    .progress-container {
        height: 20px;
        background-color: #e9ecef;
        border-radius: 10px;
        margin: 10px 0;
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 10px;
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        transition: width 0.5s ease;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Prometheus client
class PrometheusClient:
    def __init__(self, url: str):
        self.url = url.rstrip('/')
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def query(self, query: str) -> dict:
        try:
            response = self.session.get(
                f"{self.url}/api/v1/query",
                params={'query': query},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            st.error(f"Prometheus query failed: {str(e)}")
            return None

prom_client = PrometheusClient(PROMETHEUS_URL)

# Metric definitions
METRICS = {
    'cpu_usage': '100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)',
    'memory_usage': '(node_memory_MemTotal_bytes - node_memory_MemFree_bytes) / node_memory_MemTotal_bytes * 100',
    'cpu_by_mode': 'rate(node_cpu_seconds_total[1m]) * 100',
    'network_in': 'sum by (device) (rate(node_network_receive_bytes_total{device!="lo"}[1m]))',
    'network_out': 'sum by (device) (rate(node_network_transmit_bytes_total{device!="lo"}[1m]))',
    'network_errors': 'sum by (device) (rate(node_network_receive_errs_total{device!="lo"}[1m]) + rate(node_network_transmit_errs_total{device!="lo"}[1m]))',
    'disk_reads': 'sum by (device) (rate(node_disk_reads_completed_total[1m]))',
    'disk_writes': 'sum by (device) (rate(node_disk_writes_completed_total[1m]))',
    'disk_io_time': 'sum by (device) (rate(node_disk_io_time_seconds_total[1m]) * 100)',  # As percentage
    'disk_space': '(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100'
}

def process_metric(result: dict) -> pd.DataFrame:
    """Convert Prometheus result to DataFrame"""
    if not result or 'data' not in result or not result['data']['result']:
        return pd.DataFrame()
    
    records = []
    for item in result['data']['result']:
        try:
            metric_info = item.get('metric', {})
            records.append({
                'timestamp': datetime.fromtimestamp(item['value'][0]),
                'value': float(item['value'][1]),
                'metric': metric_info,
                'mode': str(metric_info.get('mode', 'unknown')),
                'device': str(metric_info.get('device', 'unknown'))
            })
        except Exception as e:
            st.warning(f"Error processing metric: {e}")
            continue
            
    return pd.DataFrame(records)

def fetch_metrics():
    """Fetch all defined metrics"""
    results = {}
    for name, query in METRICS.items():
        raw_data = prom_client.query(query)
        results[name] = process_metric(raw_data)
        time.sleep(0.1)  # Be nice to Prometheus
    return results

def create_gauge(value, title, min_val=0, max_val=100):
    """Create a modern gauge chart"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        title = {'text': title},
        gauge = {
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': "#4b6cb7"},
            'steps': [
                {'range': [0, 50], 'color': "lightgray"},
                {'range': [50, 75], 'color': "gray"},
                {'range': [75, 100], 'color': "darkgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

def setup_page():
    """Setup the page layout without page config"""
    # Custom header
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image("https://via.placeholder.com/150x50?text=AIOps", width=150)
    with col2:
        st.title("AIOPS Dashboard")
    
    st.markdown("---")

def format_bytes(bytes_value):
    """Format bytes to human readable format"""
    for unit in ['B/s', 'KB/s', 'MB/s', 'GB/s']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB/s"

def display_metrics(data):
    """Display metrics with modern visualizations"""
    # KPI Cards
    st.subheader("Key Performance Indicators")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        if not data.get('cpu_usage', pd.DataFrame()).empty:
            current_cpu = data['cpu_usage'].iloc[-1]['value']
            st.plotly_chart(create_gauge(current_cpu, "CPU Usage (%)"), use_container_width=True)
    
    with kpi2:
        if not data.get('memory_usage', pd.DataFrame()).empty:
            current_mem = data['memory_usage'].iloc[-1]['value']
            st.plotly_chart(create_gauge(current_mem, "Memory Usage (%)"), use_container_width=True)
    
    with kpi3:
        if not data.get('network_in', pd.DataFrame()).empty:
            current_net_in = data['network_in'].iloc[-1]['value']
            st.metric("Network In", f"{(current_net_in/1e6):.2f} Mbps", delta="5% from avg")
    
    with kpi4:
        if not data.get('network_out', pd.DataFrame()).empty:
            current_net_out = data['network_out'].iloc[-1]['value']
            st.metric("Network Out", f"{(current_net_out/1e6):.2f} Mbps", delta="-2% from avg")
    
    # Main charts
    col1, col2 = st.columns(2)
    
    with col1:
        # CPU Usage Over Time
        if not data.get('cpu_usage', pd.DataFrame()).empty:
            fig = px.line(
                data['cpu_usage'],
                x='timestamp',
                y='value',
                title="<b>CPU Usage Trend</b>",
                template="plotly_white",
                labels={'value': 'Usage %', 'timestamp': 'Time'}
            )
            fig.update_layout(
                hovermode="x unified",
                showlegend=False,
                height=300,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            fig.update_traces(line=dict(color='#4b6cb7', width=2.5))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Memory Usage Over Time
        if not data.get('memory_usage', pd.DataFrame()).empty:
            fig = px.area(
                data['memory_usage'],
                x='timestamp',
                y='value',
                title="<b>Memory Usage Trend</b>",
                template="plotly_white",
                labels={'value': 'Usage %', 'timestamp': 'Time'}
            )
            fig.update_layout(
                hovermode="x unified",
                showlegend=False,
                height=300,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            fig.update_traces(fillcolor='rgba(75, 108, 183, 0.2)', line=dict(color='#4b6cb7', width=2.5))
            st.plotly_chart(fig, use_container_width=True)
    
    # CPU by Mode
    if not data.get('cpu_by_mode', pd.DataFrame()).empty:
        st.subheader("CPU Utilization by Mode")
        df = data['cpu_by_mode'].copy()
        
        if 'mode' not in df.columns:
            df['mode'] = df['metric'].apply(
                lambda x: x.get('mode', 'unknown') if isinstance(x, dict) else 'unknown'
            )
        
        df_agg = df.groupby(['timestamp', 'mode'])['value'].mean().reset_index()
        
        try:
            pivot_df = df_agg.pivot(index='timestamp', columns='mode', values='value')
            
            fig = px.line(
                pivot_df,
                title="<b>CPU Usage by Mode (%)</b>",
                template="plotly_white",
                labels={'value': 'Usage %', 'timestamp': 'Time'},
                color_discrete_sequence=px.colors.qualitative.Plotly
            )
            fig.update_layout(
                hovermode="x unified",
                height=350,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error displaying CPU modes: {str(e)}")
    
    # Network and Disk I/O
    st.subheader("Network & Disk Performance")
    
    # Network Performance in an expander
    with st.expander("🌐 Network Performance", expanded=False):
        net1, net2, net3 = st.columns(3)
        
        with net1:
            if not data.get('network_in', pd.DataFrame()).empty:
                df_net = data['network_in']
                for device in df_net['device'].unique():
                    device_data = df_net[df_net['device'] == device]
                    if not device_data.empty:
                        current_value = device_data.iloc[-1]['value']
                        st.metric(
                            f"Network In ({device})", 
                            format_bytes(current_value),
                            delta=f"{((current_value / device_data['value'].mean() - 1) * 100):.1f}%"
                        )
        
        with net2:
            if not data.get('network_out', pd.DataFrame()).empty:
                df_net = data['network_out']
                for device in df_net['device'].unique():
                    device_data = df_net[df_net['device'] == device]
                    if not device_data.empty:
                        current_value = device_data.iloc[-1]['value']
                        st.metric(
                            f"Network Out ({device})",
                            format_bytes(current_value),
                            delta=f"{((current_value / device_data['value'].mean() - 1) * 100):.1f}%"
                        )
        
        with net3:
            if not data.get('network_errors', pd.DataFrame()).empty:
                df_errors = data['network_errors']
                for device in df_errors['device'].unique():
                    device_data = df_errors[df_errors['device'] == device]
                    if not device_data.empty:
                        current_value = device_data.iloc[-1]['value']
                        st.metric(
                            f"Network Errors ({device})",
                            f"{current_value:.0f}/s",
                            delta=f"{current_value:.0f} errors/s",
                            delta_color="inverse"
                        )

        # Add network throughput chart inside expander
        if (not data.get('network_in', pd.DataFrame()).empty and 
            not data.get('network_out', pd.DataFrame()).empty):
            st.markdown("#### Network Throughput Over Time")
            fig = go.Figure()
            
            # Network In
            fig.add_trace(go.Scatter(
                x=data['network_in']['timestamp'],
                y=data['network_in']['value']/1e6,
                name="Network In",
                line=dict(color='#4b6cb7', width=2)
            ))
            
            # Network Out
            fig.add_trace(go.Scatter(
                x=data['network_out']['timestamp'],
                y=data['network_out']['value']/1e6,
                name="Network Out",
                line=dict(color='#182848', width=2)
            ))
            
            fig.update_layout(
                title="<b>Network Throughput (Mbps)</b>",
                template="plotly_white",
                height=250,
                margin=dict(l=20, r=20, t=50, b=20),
                xaxis_title="Time",
                yaxis_title="Mbps",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Disk Performance in an expander
    with st.expander("💾 Disk Performance", expanded=False):
        disk1, disk2, disk3 = st.columns(3)
        
        with disk1:
            if not data.get('disk_reads', pd.DataFrame()).empty:
                df_disk = data['disk_reads']
                for device in df_disk['device'].unique():
                    if 'loop' not in device:  # Skip loop devices
                        device_data = df_disk[df_disk['device'] == device]
                        if not device_data.empty:
                            current_value = device_data.iloc[-1]['value']
                            st.metric(
                                f"Disk Reads ({device})",
                                f"{current_value:.0f} IOPS",
                                delta=f"{((current_value / device_data['value'].mean() - 1) * 100):.1f}%"
                            )
        
        with disk2:
            if not data.get('disk_writes', pd.DataFrame()).empty:
                df_disk = data['disk_writes']
                for device in df_disk['device'].unique():
                    if 'loop' not in device:  # Skip loop devices
                        device_data = df_disk[df_disk['device'] == device]
                        if not device_data.empty:
                            current_value = device_data.iloc[-1]['value']
                            st.metric(
                                f"Disk Writes ({device})",
                                f"{current_value:.0f} IOPS",
                                delta=f"{((current_value / device_data['value'].mean() - 1) * 100):.1f}%"
                            )
        
        with disk3:
            if not data.get('disk_io_time', pd.DataFrame()).empty:
                df_io = data['disk_io_time']
                for device in df_io['device'].unique():
                    if 'loop' not in device:  # Skip loop devices
                        device_data = df_io[df_io['device'] == device]
                        if not device_data.empty:
                            current_value = device_data.iloc[-1]['value']
                            st.metric(
                                f"Disk Utilization ({device})",
                                f"{current_value:.1f}%",
                                delta=f"{((current_value / device_data['value'].mean() - 1) * 100):.1f}%"
                            )

        # Add disk I/O chart inside expander
        if not data.get('disk_reads', pd.DataFrame()).empty and not data.get('disk_writes', pd.DataFrame()).empty:
            st.markdown("#### Disk I/O Over Time")
            fig = go.Figure()
            
            # Disk Reads
            fig.add_trace(go.Scatter(
                x=data['disk_reads']['timestamp'],
                y=data['disk_reads']['value'],
                name="Reads",
                line=dict(color='#4b6cb7', width=2)
            ))
            
            # Disk Writes
            fig.add_trace(go.Scatter(
                x=data['disk_writes']['timestamp'],
                y=data['disk_writes']['value'],
                name="Writes",
                line=dict(color='#182848', width=2)
            ))
            
            fig.update_layout(
                title="<b>Disk I/O Operations</b>",
                template="plotly_white",
                height=250,
                margin=dict(l=20, r=20, t=50, b=20),
                xaxis_title="Time",
                yaxis_title="IOPS",
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Disk Space Usage in an expander
    with st.expander("💾 Storage Usage Overview", expanded=False):
        # Add a description
        st.markdown("""
            <div style='margin-bottom: 20px'>
                Monitor storage utilization across different mount points. Values show current usage percentage and trend.
            </div>
        """, unsafe_allow_html=True)
        
        df_space = data.get('disk_space', pd.DataFrame())
        if not df_space.empty:
            # Storage Usage Summary
            total_mounts = 0
            critical_mounts = 0
            
            # First show the bar chart for all mount points
            fig_bar = go.Figure()
            mount_data = []
            
            for mountpoint in df_space['metric'].apply(lambda x: x.get('mountpoint', '')).unique():
                if mountpoint and mountpoint != '/boot':  # Skip boot partition
                    mount_data = df_space[df_space['metric'].apply(lambda x: x.get('mountpoint', '') == mountpoint)]
                    if not mount_data.empty:
                        current_value = mount_data.iloc[-1]['value']
                        total_mounts += 1
                        if current_value > 85:  # Critical threshold
                            critical_mounts += 1
                            
                        # Add bar with color based on usage
                        color = '#4b6cb7' if current_value < 85 else '#ff4b5c'
                        fig_bar.add_trace(go.Bar(
                            x=[mountpoint],
                            y=[current_value],
                            name=mountpoint,
                            text=[f"{current_value:.1f}%"],
                            textposition='auto',
                            marker_color=color,
                        ))
            
            # Update bar chart layout
            fig_bar.update_layout(
                title="<b>Storage Usage by Mount Point</b>",
                template="plotly_white",
                height=250,
                margin=dict(l=20, r=20, t=50, b=20),
                yaxis_title="Usage %",
                yaxis_range=[0, 100],
                showlegend=False,
                bargap=0.3
            )
            
            # Show summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Mount Points", f"{total_mounts}")
            with col2:
                st.metric("Critical (>85%)", f"{critical_mounts}", 
                         delta=f"{critical_mounts} needs attention" if critical_mounts > 0 else "All OK",
                         delta_color="inverse")
            with col3:
                avg_usage = df_space['value'].mean()
                st.metric("Average Usage", f"{avg_usage:.1f}%",
                         delta=f"{avg_usage - 70:.1f}% from target" if avg_usage > 70 else "Within target",
                         delta_color="inverse" if avg_usage > 70 else "normal")
            
            # Show the bar chart
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Detailed metrics in a clean grid
            st.markdown("#### Detailed Mount Point Usage")
            cols = st.columns(3)
            col_idx = 0
            
            for mountpoint in df_space['metric'].apply(lambda x: x.get('mountpoint', '')).unique():
                if mountpoint and mountpoint != '/boot':
                    mount_data = df_space[df_space['metric'].apply(lambda x: x.get('mountpoint', '') == mountpoint)]
                    if not mount_data.empty:
                        current_value = mount_data.iloc[-1]['value']
                        with cols[col_idx % 3]:
                            st.metric(
                                f"📁 {mountpoint}",
                                f"{current_value:.1f}%",
                                delta=f"{((current_value / mount_data['value'].mean() - 1) * 100):.1f}%",
                                delta_color="inverse" if current_value > 85 else "normal"
                            )
                        col_idx += 1

def main():
    setup_page()
    
    # Sidebar
    with st.sidebar:
        st.header("System Status")
        
        # Test connection
        if st.button("Prometheus"):
            test_result = prom_client.query("up")
            if test_result and test_result.get('data'):
                st.success("✅ Connected to Prometheus")
            else:
                st.error("❌ Connection failed")
        
        st.markdown("---")
        st.header("Settings")
        auto_refresh = st.checkbox("Auto Refresh", value=True)
        refresh_rate = st.slider("Refresh Rate (seconds)", 5, 60, REFRESH_INTERVAL)
    
    # Main display
    placeholder = st.empty()
    last_refresh = st.empty()
    
    while True:
        with placeholder.container():
            data = fetch_metrics()
            display_metrics(data)
        
        last_refresh.text(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        if auto_refresh:
            time.sleep(refresh_rate)
        else:
            time.sleep(1)  # Sleep briefly even when not auto-refreshing

if __name__ == "__main__":
    main()