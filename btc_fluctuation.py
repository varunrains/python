import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
from plotly.subplots import make_subplots

def fetch_minute_data(days=30):
    """Fetch minute-level BTC data from Binance API"""
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
            'symbol': 'BTCUSDT',
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

def calculate_precise_session_stats(df):
    """Calculate statistics with precise time windows"""
    results = []
    
    if df.index.tz is None:
        df = df.tz_localize(pytz.utc)
    elif str(df.index.tz) != 'UTC':
        df = df.tz_convert(pytz.utc)
    
    unique_dates = pd.to_datetime(df.index.date).unique()
    
    for date in unique_dates:
        open_time = datetime.combine(date, datetime.strptime("18:30", "%H:%M").time()).replace(tzinfo=pytz.utc)
        close_time = open_time + timedelta(hours=17, minutes=30)
        
        session_mask = (df.index >= open_time) & (df.index <= close_time)
        session_data = df[session_mask]
        
        if len(session_data) > 10:
            open_price = session_data.iloc[0]['close']
            close_price = session_data.iloc[-1]['close']
            high_price = session_data['high'].max()
            low_price = session_data['low'].min()
            
            pct_change = ((close_price - open_price) / open_price) * 100
            volatility_pct = ((high_price - low_price) / open_price) * 100
            max_gain_pct = ((high_price - open_price) / open_price) * 100
            max_loss_pct = ((low_price - open_price) / open_price) * 100
            
            # Calculate direction for coloring
            direction = "up" if close_price > open_price else "down"
            
            results.append({
                'date': date.date(),
                'date_str': date.strftime('%Y-%m-%d'),
                'open_time': open_time,
                'close_time': close_time,
                'open': open_price,
                'close': close_price,
                'high': high_price,
                'low': low_price,
                'pct_change': pct_change,
                'volatility_pct': volatility_pct,
                'max_gain_pct': max_gain_pct,
                'max_loss_pct': max_loss_pct,
                'range_abs': high_price - low_price,
                'data_points': len(session_data),
                'direction': direction
            })
    
    return pd.DataFrame(results).sort_values('date')

def create_interactive_plot(results_df):
    """Create interactive plot with Plotly"""
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add volatility bars with color based on direction
    colors = ['green' if x == 'up' else 'red' for x in results_df['direction']]
    fig.add_trace(
        go.Bar(
            x=results_df['date_str'],
            y=results_df['volatility_pct'],
            name='Volatility %',
            marker_color=colors,
            opacity=0.6,
            hovertemplate=(
                "<b>Date:</b> %{x}<br>"
                "<b>Volatility:</b> %{y:.2f}%<br>"
                "<b>Open:</b> $%{customdata[0]:.2f}<br>"
                "<b>Close:</b> $%{customdata[1]:.2f}<br>"
                "<b>High:</b> $%{customdata[2]:.2f}<br>"
                "<b>Low:</b> $%{customdata[3]:.2f}<br>"
                "<b>Change:</b> %{customdata[4]:.2f}%"
            ),
            customdata=results_df[['open', 'close', 'high', 'low', 'pct_change']],
        ),
        secondary_y=False,
    )
    
    # Add price change line
    fig.add_trace(
        go.Scatter(
            x=results_df['date_str'],
            y=results_df['pct_change'],
            name='Price Change %',
            mode='lines+markers',
            line=dict(color='blue', width=2),
            hovertemplate=(
                "<b>Date:</b> %{x}<br>"
                "<b>Price Change:</b> %{y:.2f}%<br>"
            )
        ),
        secondary_y=True,
    )
    
    # Add zero line reference
    fig.add_hline(
        y=0, 
        line_dash="dot",
        line_color="gray",
        secondary_y=True
    )
    
    # Update layout
    fig.update_layout(
        title='BTC 6:30PM-12PM UTC: Volatility and Price Changes',
        xaxis_title='Date',
        yaxis_title='Volatility %',
        yaxis2_title='Price Change %',
        hovermode="x unified",
        xaxis=dict(
            tickangle=45,
            type='category',
            tickmode='auto',
            nticks=min(30, len(results_df))  # Show max 30 ticks
        ),
        height=600,
        showlegend=True
    )
    
    return fig

def main():
    print("Fetching minute-level BTC data...")
    try:
        # Start with 30 days for testing, can increase to 365 after verifying
        btc_data = fetch_minute_data(days=365)
        print(f"Fetched data from {btc_data.index[0]} to {btc_data.index[-1]}")
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
    
    print("\nCalculating session statistics...")
    results = calculate_precise_session_stats(btc_data)
    
    if results.empty:
        print("No results calculated - check your data")
        return
    
    print("\n=== Latest 5 Sessions ===")
    print(results[['date', 'open', 'close', 'volatility_pct', 'pct_change']].tail(5))
    
    # Analyze specific date (May 21 example)

    
    # Create and show interactive plot
    fig = create_interactive_plot(results)
    fig.show()

if __name__ == "__main__":
    main()