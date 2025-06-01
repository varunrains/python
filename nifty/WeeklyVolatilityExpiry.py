import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from plotly.subplots import make_subplots

def load_nifty_data(file_path):
    """Load Nifty historical data from CSV"""
    df = pd.read_csv(file_path)
    
    # Clean and convert data
    df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
    df.set_index('Date', inplace=True)
    
    # Convert string values to numeric
    df['Price'] = df['Price'].str.replace(',', '').astype(float)
    df['Open'] = df['Open'].str.replace(',', '').astype(float)
    df['High'] = df['High'].str.replace(',', '').astype(float)
    df['Low'] = df['Low'].str.replace(',', '').astype(float)
    df['Change %'] = df['Change %'].str.replace('%', '').astype(float)
    
    return df.sort_index()

def calculate_expiry_week_stats(df):
    """Calculate weekly expiry period statistics (Friday after expiry to next Thursday)"""
    results = []
    
    # Find all Thursdays (expiry days) in the data
    thursdays = df[df.index.weekday == 3].index
    
    for i in range(len(thursdays)-1):
        expiry_date = thursdays[i]
        next_expiry = thursdays[i+1]
        
        # Start on Friday after expiry
        start_date = expiry_date + timedelta(days=1)
        
        # If Friday isn't a trading day, find the next trading day
        while start_date not in df.index and start_date < next_expiry:
            start_date += timedelta(days=1)
            
        # End on next expiry Thursday
        end_date = next_expiry
        
        # Get all trading days in this period
        period_data = df.loc[start_date:end_date]
        
        if len(period_data) < 3:  # Skip very short periods
            continue
            
        start_open = period_data.iloc[0]['Open']
        start_close = period_data.iloc[0]['Price']
        end_close = period_data.iloc[-1]['Price']
        period_high = period_data['High'].max()
        period_low = period_data['Low'].min()
        
        # Calculate volatility measures
        upward_vol = ((period_high - start_open) / start_open) * 100
        downward_vol = ((start_open - period_low) / start_open) * 100
        true_volatility = max(upward_vol, downward_vol)
        direction = "up" if upward_vol > downward_vol else "down"
        
        # Calculate net change for the period
        net_change_pct = ((end_close - start_open) / start_open) * 100
        
        # Calculate actual trading days (excluding holidays)
        trading_days = len(period_data)
        
        results.append({
            'expiry_date': expiry_date.date(),
            'period_start': start_date.date(),
            'period_end': end_date.date(),
            'duration_days': (end_date - start_date).days,
            'trading_days': trading_days,
            'start_open': start_open,
            'start_close': start_close,
            'end_close': end_close,
            'period_high': period_high,
            'period_low': period_low,
            'true_volatility_pct': true_volatility,
            'direction': direction,
            'upward_vol_pct': upward_vol,
            'downward_vol_pct': downward_vol,
            'net_change_pct': net_change_pct,
            'range_abs': period_high - period_low
        })
    
    return pd.DataFrame(results).sort_values('period_start')

def create_expiry_volatility_plot(results_df, min_volatility=None):
    """Create interactive plot for expiry period volatility"""
    # Filter by minimum volatility if specified
    if min_volatility is not None:
        results_df = results_df[results_df['true_volatility_pct'] >= min_volatility]
        if results_df.empty:
            print(f"No periods found with volatility >= {min_volatility}%")
            return None
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Create hover text with date range and expiry date
    results_df['hover_text'] = results_df.apply(
        lambda row: f"Exp {row['expiry_date']} | Period {row['period_start']} to {row['period_end']}", axis=1)
    
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
                "<b>Expiry Date:</b> %{customdata[0]}<br>"
                "<b>Period:</b> %{customdata[1]} to %{customdata[2]}<br>"
                "<b>Trading Days:</b> %{customdata[3]}<br>"
                "<b>Max Volatility:</b> %{y:.2f}%<br>"
                "<b>Direction:</b> %{customdata[4]}<br>"
                "<b>Start Open:</b> %{customdata[5]:.2f}<br>"
                "<b>Period High:</b> %{customdata[6]:.2f}<br>"
                "<b>Period Low:</b> %{customdata[7]:.2f}<br>"
                "<b>End Close:</b> %{customdata[8]:.2f}<br>"
                "<b>Up Move:</b> %{customdata[9]:.2f}%<br>"
                "<b>Down Move:</b> %{customdata[10]:.2f}%<br>"
                "<b>Net Change:</b> %{customdata[11]:.2f}%"
            ),
            customdata=results_df[[
                'expiry_date', 'period_start', 'period_end', 'trading_days',
                'direction', 'start_open', 'period_high', 'period_low', 'end_close',
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
            hovertemplate="<b>Period:</b> %{x}<br><b>Net Change:</b> %{y:.2f}%"
        ),
        secondary_y=True,
    )
    
    # Add zero line reference
    fig.add_hline(y=0, line_dash="dot", line_color="gray", secondary_y=True)
    
    # Update layout
    title_suffix = f" (Volatility ≥ {min_volatility}%)" if min_volatility is not None else ""
    fig.update_layout(
        title=f'Nifty Expiry Period Volatility (Friday to Thursday){title_suffix}',
        xaxis_title='Expiry Period',
        yaxis_title='Max Volatility %',
        yaxis2_title='Net Change %',
        hovermode="x unified",
        xaxis=dict(
            tickangle=45,
            type='category',
            tickmode='auto',
            nticks=min(20, len(results_df))
        ),
        height=600,
        showlegend=True
    )
    
    # Add annotation for max volatility period
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
    print("Loading Nifty 50 historical data...")
    try:
        nifty_data = load_nifty_data("HistoricalDataNifty.csv")
        print(f"Loaded data from {nifty_data.index[0].date()} to {nifty_data.index[-1].date()}")
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    print("\nCalculating expiry period statistics (Friday to Thursday)...")
    results = calculate_expiry_week_stats(nifty_data)
    
    if results.empty:
        print("No results calculated - check your data")
        return
    
    print("\n=== Expiry Period Statistics Summary ===")
    print(f"Average max volatility: {results['true_volatility_pct'].mean():.2f}%")
    print(f"Maximum volatility period: {results['true_volatility_pct'].max():.2f}%")
    print(f"Minimum volatility period: {results['true_volatility_pct'].min():.2f}%")
    print(f"Average trading days per period: {results['trading_days'].mean():.1f}")
    
    try:
        min_volatility = float(input("\nEnter minimum volatility percentage to filter (or press Enter to show all): ") or 0)
    except ValueError:
        min_volatility = 0
    
    fig = create_expiry_volatility_plot(results, min_volatility if min_volatility > 0 else None)
    if fig:
        fig.show()
    
    save_csv = input("\nDo you want to save the results to CSV? (y/n): ").lower()
    if save_csv == 'y':
        filename = f"nifty_expiry_period_volatility_{nifty_data.index[0].date()}_to_{nifty_data.index[-1].date()}.csv"
        results.to_csv(filename, index=False)
        print(f"Results saved to {filename}")

if __name__ == "__main__":
    main()