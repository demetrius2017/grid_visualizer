import dash
from dash import dcc, html
import plotly.graph_objs as go
import pandas as pd
from dash.dependencies import Input, Output
import random
import time

# Создание данных для графика
start_time = time.time()
df = pd.DataFrame({
    'Open': [100, 105, 103, 106, 105],
    'High': [107, 110, 108, 109, 108],
    'Low': [99, 104, 102, 105, 103],
    'Close': [105, 107, 104, 107, 106],
    'Time': [time.time() - start_time for _ in range(5)]  # Время с начала
})

app = dash.Dash(__name__)

app.layout = html.Div([
    dcc.Graph(
        id='candlestick-chart',
        config={'scrollZoom': True, 'responsive': True},
        style={'height': '80vh', 'width': '100%'}  # Увеличенная высота и ширина графика
    ),
    dcc.Interval(
        id='interval-component',
        interval=1*100,  # обновление каждые 0.1 секунды
        n_intervals=0
    ),
    dcc.Store(id='viewstate', data={'xaxis.range': None, 'yaxis.range': None})
])

@app.callback(
    Output('viewstate', 'data'),
    Input('candlestick-chart', 'relayoutData')
)
def update_viewstate(relayoutData):
    if relayoutData is None:
        return dash.no_update
    return {
        'xaxis.range': relayoutData.get('xaxis.range', None),
        'yaxis.range': relayoutData.get('yaxis.range', None)
    }

@app.callback(
    Output('candlestick-chart', 'figure'),
    [Input('interval-component', 'n_intervals'),
     Input('viewstate', 'data')]
)
def update_graph(n, viewstate):
    global df
    # Генерация новой свечи с рандомными значениями
    last_close = df['Close'].iloc[-1]
    open_price = last_close
    close_price = open_price + random.uniform(-5, 5)
    high_price = max(open_price, close_price) + random.uniform(0, 3)
    low_price = min(open_price, close_price) - random.uniform(0, 3)
    
    new_candle = pd.DataFrame({
        'Open': [open_price], 'High': [high_price], 'Low': [low_price], 'Close': [close_price],
        'Time': [time.time() - start_time]
    })
    df = pd.concat([df, new_candle], ignore_index=True)

    if len(df) > 50:  # Ограничение на количество свечей
        df = df.iloc[1:]

    fig = go.Figure(data=[go.Candlestick(
        x=df['Time'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close']
    )])

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        autosize=True,
        responsive=True
    )

    # Применение сохраненного состояния
    if viewstate:
        xaxis_range = viewstate.get('xaxis.range')
        yaxis_range = viewstate.get('yaxis.range')
        if xaxis_range:
            fig.update_layout(xaxis=dict(range=xaxis_range))
        if yaxis_range:
            fig.update_layout(yaxis=dict(range=yaxis_range))
    else:
        # Установить диапазон оси X, чтобы отображать последние 50 свечей
        max_time = df['Time'].max()
        fig.update_layout(xaxis=dict(range=[max_time - 10, max_time]))

    return fig

if __name__ == '__main__':
    app.run_server(debug=True)
