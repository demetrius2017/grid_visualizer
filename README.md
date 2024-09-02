# Trading Simulator

## Overview

Trading Simulator is a Python-based application that provides a visual and interactive environment for simulating grid trading strategies. It offers real-time market price simulation, dynamic grid order placement, and comprehensive performance tracking.

## Features

- **Real-time Market Simulation**: Simulates market price movements with adjustable volatility.
- **Dynamic Grid Trading**: Implements a grid trading strategy with adaptive grid sizing based on market conditions.
- **Interactive GUI**: Built with PyQt5 for a responsive and user-friendly interface.
- **Live Charts**: Utilizes pyqtgraph for real-time visualization of price movements, order placements, and performance metrics.
- **Performance Tracking**: Monitors and displays key metrics such as balance, profit, free margin, and commissions.
- **Position Management**: Provides detailed views of open and closed positions.
- **Price Distribution Analysis**: Includes a histogram of price distribution with normal distribution overlay.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/trading-simulator.git
   cd trading-simulator
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

To start the Trading Simulator:

```
python main.py
```

## Project Structure

- `main.py`: Entry point of the application.
- `graph.py`: Handles the visualization of market data and trading activities.
- `trading.py`: Contains the core logic for the trading simulation.
- `orders.py`: Manages order creation, execution, and position tracking.
- `menu.py`: Implements the main window and user interface controls.
- `positions_window.py`: Provides a detailed view of open and closed positions.

## Configuration

You can adjust various parameters of the simulation:

1. Open the "Grid" menu in the application.
2. Select "Grid Settings" to modify:
   - Grid Step Percentage
   - Market Volatility

## Contributing

Contributions to the Trading Simulator project are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes with clear, descriptive messages.
4. Push the branch to your fork.
5. Submit a pull request with a detailed description of your changes.

## License

[Include your chosen license here]

## Disclaimer

This software is for educational and simulation purposes only. It does not constitute financial advice, and should not be used for real trading without proper risk management and understanding of the financial markets.

## Contact

[demetrius2017]
[@demetrius_i]

---

Happy Trading Simulation!