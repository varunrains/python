import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
from plotly.subplots import make_subplots

def fetch_minute_data(days=30):
    """Fetch minute-level ETH data from Binance API"""
    interval = '1m'
    limit = 1440
    url = "https://api.binance.com/api/v3/klines"
    
    end_time = datetime.now(pytz.utc)
    start_time = end_time - timedelta(days=days)
    start_time = start_time.replace(tzinfo=pytz.utc)
    
    all_data = []
    current_end = end_time
    
    while current_end > start_time:
        params = {
            'symbol': 'ETHUSDT',  # Changed from BTCUSDT to ETHUSDT
            'interval': interval,
            'limit': limit,
            'endTime': int(current_end.timestamp() * 1000)
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
                
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
            df.set_index('timestamp', inplace=True)
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            
            all_data.append(df)
            current_end = df.index[0].to_pydatetime().replace(tzinfo=pytz.utc) - timedelta(minutes=1)
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            break
    
    if not all_data:
        raise ValueError("No data fetched from Binance API")
    
    full_df = pd.concat(all_data).sort_index()
    return full_df[~full_df.index.duplicated(keep='first')]

def calculate_weekly_volatility(df):
    """Calculate weekly volatility from Thursday 12PM to next Friday 12PM"""
    results = []
    
    if df.index.tz is None:
        df = df.tz_localize(pytz.utc)
    elif str(df.index.tz) != 'UTC':
        df = df.tz_convert(pytz.utc)
    
    # Find all Thursdays in the data
    thursdays = df[df.index.dayofweek == 3]  # 3 is Thursday
    
    for thursday_date in thursdays.index.normalize().unique():
        # Get Thursday 12PM UTC
        thursday_start = thursday_date + timedelta(hours=12)
        
        # Get next Friday 12PM UTC (7 days later)
        friday_end = thursday_start + timedelta(days=7)
        
        # Get data for this weekly period
        weekly_data = df[(df.index >= thursday_start) & (df.index <= friday_end)]
        
        if len(weekly_data) > 10:
            open_price = weekly_data.iloc[0]['close']
            high_price = weekly_data['high'].max()
            low_price = weekly_data['low'].min()
            close_price = weekly_data.iloc[-1]['close']
            
            # Calculate both upward and downward volatility
            upward_vol = ((high_price - open_price) / open_price) * 100
            downward_vol = ((open_price - low_price) / open_price) * 100
            
            # True volatility is the maximum deviation from open
            true_volatility = max(upward_vol, downward_vol)
            direction = "up" if upward_vol > downward_vol else "down"
            
            # Get date range
            start_date = weekly_data.index[0].date()
            end_date = weekly_data.index[-1].date()
            
            results.append({
                'start_date': start_date,
                'end_date': end_date,
                'date_range': f"{start_date} to {end_date}",
                'open_time': thursday_start,
                'close_time': friday_end,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'true_volatility_pct': true_volatility,
                'direction': direction,
                'upward_vol_pct': upward_vol,
                'downward_vol_pct': downward_vol,
                'net_change_pct': ((close_price - open_price) / open_price) * 100,
                'range_abs': high_price - low_price,
                'data_points': len(weekly_data)
            })
    
    return pd.DataFrame(results).sort_values('start_date')

def create_interactive_plot(results_df, min_volatility=None):
    """Create interactive plot with Plotly"""
    # Filter by minimum volatility if specified
    if min_volatility is not None:
        results_df = results_df[results_df['true_volatility_pct'] >= min_volatility]
        if results_df.empty:
            print(f"No weeks found with volatility >= {min_volatility}%")
            return None
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add date range to hover text
    results_df['hover_text'] = results_df['date_range']
    
    # Add volatility bars with color based on direction
    colors = ['green' if x == 'up' else 'red' for x in results_df['direction']]
    fig.add_trace(
        go.Bar(
            x=results_df['hover_text'],
            y=results_df['true_volatility_pct'],
            name='True Volatility %',
            marker_color=colors,
            opacity=0.7,
            hovertemplate=(
                "<b>Date Range:</b> %{x}<br>"
                "<b>Max Volatility:</b> %{y:.2f}%<br>"
                "<b>Direction:</b> %{customdata[0]}<br>"
                "<b>Open:</b> $%{customdata[1]:.2f}<br>"
                "<b>High:</b> $%{customdata[2]:.2f}<br>"
                "<b>Low:</b> $%{customdata[3]:.2f}<br>"
                "<b>Close:</b> $%{customdata[4]:.2f}<br>"
                "<b>Up Move:</b> %{customdata[5]:.2f}%<br>"
                "<b>Down Move:</b> %{customdata[6]:.2f}%<br>"
                "<b>Net Change:</b> %{customdata[7]:.2f}%"
            ),
            customdata=results_df[[
                'direction', 'open', 'high', 'low', 'close', 
                'upward_vol_pct', 'downward_vol_pct', 'net_change_pct'
            ]],
        ),
        secondary_y=False,
    )
    
    # Add net change line
    fig.add_trace(
        go.Scatter(
            x=results_df['hover_text'],
            y=results_df['net_change_pct'],
            name='Net Change %',
            mode='lines+markers',
            line=dict(color='blue', width=2),
            hovertemplate="<b>Date Range:</b> %{x}<br><b>Net Change:</b> %{y:.2f}%"
        ),
        secondary_y=True,
    )
    
    # Add zero line reference
    fig.add_hline(y=0, line_dash="dot", line_color="gray", secondary_y=True)
    
    # Update layout
    title_suffix = f" (Volatility ≥ {min_volatility}%)" if min_volatility is not None else ""
    fig.update_layout(
        title=f'ETH Weekly Volatility (Thursday 12PM to Friday 12PM UTC){title_suffix}',
        xaxis_title='Date Range',
        yaxis_title='Max Volatility %',
        yaxis2_title='Net Change %',
        hovermode="x unified",
        xaxis=dict(
            tickangle=45,
            type='category',
            tickmode='auto',
            nticks=min(30, len(results_df))
        ),
        height=600,
        showlegend=True
    )
    
    # Add annotation for max volatility week
    if not results_df.empty:
        max_vol_idx = results_df['true_volatility_pct'].idxmax()
        fig.add_annotation(
            x=results_df.loc[max_vol_idx, 'hover_text'],
            y=results_df.loc[max_vol_idx, 'true_volatility_pct'],
            text=f"Max: {results_df.loc[max_vol_idx, 'true_volatility_pct']:.2f}%",
            showarrow=True,
            arrowhead=1
        )
    
    return fig

def main():
    print("Fetching minute-level ETH data...")
    try:
        days = int(input("Enter number of days to analyze (minimum 7 recommended): "))
        if days < 7:
            print("Warning: For weekly analysis, at least 7 days of data is recommended")
        eth_data = fetch_minute_data(days=days)
        print(f"Fetched data from {eth_data.index[0]} to {eth_data.index[-1]}")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
    
    print("\nCalculating weekly volatility (Thursday 12PM to Friday 12PM UTC)...")
    results = calculate_weekly_volatility(eth_data)
    
    if results.empty:
        print("No results calculated - check your data")
        return
    
    print("\n=== Statistics Summary ===")
    print(f"Average max weekly volatility: {results['true_volatility_pct'].mean():.2f}%")
    print(f"Maximum volatility week: {results['true_volatility_pct'].max():.2f}% from {results.loc[results['true_volatility_pct'].idxmax(), 'date_range']}")
    print(f"Minimum volatility week: {results['true_volatility_pct'].min():.2f}%")
    
    try:
        min_volatility = float(input("\nEnter minimum volatility percentage to filter (or press Enter to show all): ") or 0)
    except ValueError:
        min_volatility = 0
    
    fig = create_interactive_plot(results, min_volatility if min_volatility > 0 else None)
    if fig:
        fig.show()
    
    save_csv = input("\nDo you want to save the results to CSV? (y/n): ").lower()
    if save_csv == 'y':
        filename = f"eth_weekly_volatility_{days}days.csv"
        results.to_csv(filename, index=False)
        print(f"Results saved to {filename}")

if __name__ == "__main__":
    main()