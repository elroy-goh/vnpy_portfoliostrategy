from datetime import datetime

from vnpy.trader.utility import ArrayManager
from vnpy.trader.object import TickData, BarData
from vnpy.trader.constant import Direction

from vnpy_portfoliostrategy import StrategyTemplate, StrategyEngine
from vnpy_portfoliostrategy.utility import PortfolioBarGenerator


class MeanReversionStrategy(StrategyTemplate):
    """EWMA Mean Reversion"""

    author = "EG"

    fast_span = 5
    slow_span = 60
    signal_vol_window = 30

    trailing_percent = 0.8
    portfolioVaR = 5_000

    entry_lbound = 0.3
    entry_ubound = 0.7

    price_add = 10 # Essentially market order

    parameters = [
        "fast_span",
        "slow_span",
        "signal_vol_window",
        "trailing_percent",
        "portfolioVaR",
        "entry_lbound",
        "entry_ubound",
    ]
    variables = [
        "ema_slow",
        "ema_fast",
        "emacd",
    ]

    def __init__(
        self,
        strategy_engine: StrategyEngine,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict
    ) -> None:
        """构造函数"""
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

        self.emacd_data: dict[str, float] = {}
        self.signal_strength: dict[str, float] = {}
        
        self.last_tick_time: datetime = None

        self.ams: dict[str, ArrayManager] = {}
        for vt_symbol in self.vt_symbols:
            self.ams[vt_symbol] = ArrayManager()

        self.pbg = PortfolioBarGenerator(self.on_bars)

    def on_init(self) -> None:
        """Initialize strategy"""
        self.write_log(f"Portfolio Strategy {self.strategy_name} initialized")

        self.rsi_buy = 50 + self.rsi_entry
        self.rsi_sell = 50 - self.rsi_entry

        self.load_bars(10)

    def calculate_unit_var(self) -> float:
        """Calculate VaR if total portfolio weight sums to 1"""
        
        
        for vt_symbol, target in self.signal_strength.items():
            
            pass
        
        # return self.portfolioVaR

    def on_start(self) -> None:
        """策略启动回调"""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止回调"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """行情推送回调"""
        self.pbg.update_tick(tick)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """K线切片回调"""
        # 更新K线计算RSI数值
        for vt_symbol, bar in bars.items():
            am: ArrayManager = self.ams[vt_symbol]
            am.update_bar(bar)

        for vt_symbol, bar in bars.items():
            am: ArrayManager = self.ams[vt_symbol]
            if not am.inited:
                return

            atr_array = am.atr(self.atr_window, array=True)
            self.atr_data[vt_symbol] = atr_array[-1]
            self.atr_ma[vt_symbol] = atr_array[-self.atr_ma_window:].mean()
            self.rsi_data[vt_symbol] = am.rsi(self.rsi_window)

            current_pos = self.get_pos(vt_symbol)
            if current_pos == 0:
                self.intra_trade_high[vt_symbol] = bar.high_price
                self.intra_trade_low[vt_symbol] = bar.low_price

                if self.atr_data[vt_symbol] > self.atr_ma[vt_symbol]:
                    if self.rsi_data[vt_symbol] > self.rsi_buy:
                        self.set_target(vt_symbol, self.fixed_size)
                    elif self.rsi_data[vt_symbol] < self.rsi_sell:
                        self.set_target(vt_symbol, -self.fixed_size)
                    else:
                        self.set_target(vt_symbol, 0)

            elif current_pos > 0:
                self.intra_trade_high[vt_symbol] = max(self.intra_trade_high[vt_symbol], bar.high_price)
                self.intra_trade_low[vt_symbol] = bar.low_price

                long_stop = self.intra_trade_high[vt_symbol] * (1 - self.trailing_percent / 100)

                if bar.close_price <= long_stop:
                    self.set_target(vt_symbol, 0)

            elif current_pos < 0:
                self.intra_trade_low[vt_symbol] = min(self.intra_trade_low[vt_symbol], bar.low_price)
                self.intra_trade_high[vt_symbol] = bar.high_price

                short_stop = self.intra_trade_low[vt_symbol] * (1 + self.trailing_percent / 100)

                if bar.close_price >= short_stop:
                    self.set_target(vt_symbol, 0)

        self.rebalance_portfolio(bars)

        self.put_event()

    def calculate_price(self, vt_symbol: str, direction: Direction, reference: float) -> float:
        """计算调仓委托价格（支持按需重载实现）"""
        if direction == Direction.LONG:
            price: float = reference + self.price_add
        else:
            price: float = reference - self.price_add

        return price
