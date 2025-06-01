import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
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

def calculate_daily_stats(df):
    """Calculate daily volatility statistics"""
    results = []
    
    for date, row in df.iterrows():
        open_price = row['Open']
        high_price = row['High']
        low_price = row['Low']
        close_price = row['Price']
        
        # Calculate both upward and downward volatility
        upward_vol = ((high_price - open_price) / open_price) * 100
        downward_vol = ((open_price - low_price) / open_price) * 100
        
        # True volatility is the maximum deviation from open
        true_volatility = max(upward_vol, downward_vol)
        direction = "up" if upward_vol > downward_vol else "down"
        
        # Get day of week
        day_of_week = date.strftime('%A')
        
        results.append({
            'date': date.date(),
            'date_str': date.strftime('%Y-%m-%d'),
            'day_of_week': day_of_week,
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
            'change_pct': row['Change %']
        })
    
    return pd.DataFrame(results).sort_values('date')

def create_interactive_plot(results_df, min_volatility=None):
    """Create interactive plot with Plotly"""
    # Filter by minimum volatility if specified
    if min_volatility is not None:
        results_df = results_df[results_df['true_volatility_pct'] >= min_volatility]
        if results_df.empty:
            print(f"No days found with volatility >= {min_volatility}%")
            return None
    
    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Add day of week to hover text
    results_df['hover_text'] = results_df.apply(
        lambda row: f"{row['date_str']} ({row['day_of_week']})", axis=1)
    
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
                "<b>Date:</b> %{x}<br>"
                "<b>Max Volatility:</b> %{y:.2f}%<br>"
                "<b>Direction:</b> %{customdata[0]}<br>"
                "<b>Open:</b> %{customdata[1]:.2f}<br>"
                "<b>High:</b> %{customdata[2]:.2f}<br>"
                "<b>Low:</b> %{customdata[3]:.2f}<br>"
                "<b>Close:</b> %{customdata[4]:.2f}<br>"
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
            hovertemplate="<b>Date:</b> %{x}<br><b>Net Change:</b> %{y:.2f}%"
        ),
        secondary_y=True,
    )
    
    # Add zero line reference
    fig.add_hline(y=0, line_dash="dot", line_color="gray", secondary_y=True)
    
    # Update layout
    title_suffix = f" (Volatility ≥ {min_volatility}%)" if min_volatility is not None else ""
    fig.update_layout(
        title=f'Nifty 50 Daily Price Moves{title_suffix}',
        xaxis_title='Date (Day of Week)',
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
    
    # Add annotation for max volatility day
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
    
    print("\nCalculating daily statistics...")
    results = calculate_daily_stats(nifty_data)
    
    if results.empty:
        print("No results calculated - check your data")
        return
    
    print("\n=== Statistics Summary ===")
    print(f"Average max volatility: {results['true_volatility_pct'].mean():.2f}%")
    print(f"Maximum volatility day: {results['true_volatility_pct'].max():.2f}% on {results.loc[results['true_volatility_pct'].idxmax(), 'day_of_week']}")
    print(f"Minimum volatility day: {results['true_volatility_pct'].min():.2f}%")
    
    # Print day-of-week distribution
    print("\n=== Day of Week Distribution ===")
    print(results['day_of_week'].value_counts().sort_index())
    
    try:
        min_volatility = float(input("\nEnter minimum volatility percentage to filter (or press Enter to show all): ") or 0)
    except ValueError:
        min_volatility = 0
    
    fig = create_interactive_plot(results, min_volatility if min_volatility > 0 else None)
    if fig:
        fig.show()
    
    save_csv = input("\nDo you want to save the results to CSV? (y/n): ").lower()
    if save_csv == 'y':
        filename = f"nifty_true_volatility_{nifty_data.index[0].date()}_to_{nifty_data.index[-1].date()}.csv"
        results.to_csv(filename, index=False)
        print(f"Results saved to {filename}")

if __name__ == "__main__":
    main()