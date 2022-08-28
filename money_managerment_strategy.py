from scipy.stats import linregress
import numpy as np
import random

from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)

from vnpy.trader.constant import Direction, Offset, Interval

class MoneyManagermentStrategy(CtaTemplate):
    author = "用Python的交易员"

    capital = 10000
    risk = 0.02

    long_entry = None
    short_entry = None
    long_sl = None
    short_sl = None

    parameters = []
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 4, self.on_1hour_bar, Interval.HOUR)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(4)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

        self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)

    def on_1hour_bar(self, bar):

        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        rsi = am.rsi(14)

        _sma = am.sma(20, True)

        sma = _sma[-1]
        sma1 = _sma[-2]

        # signal = random.choice([-1,1])
        # print(self.capital)
        long_signal = bar.close_price > sma and sma > sma1 and rsi > 70
        short_signal = bar.close_price < sma and sma < sma1 and rsi < 30

        kcross_below = bar.close_price < sma and am.close[-2] > sma1
        kcross_above = bar.close_price > sma and am.close[-2] < sma1

        if self.pos == 0:

            volume = round((self.capital * self.risk) / (0.02 * bar.close_price), 2)

            if volume > 0:
                # print(volume)
                if short_signal:
                    self.short(bar.close_price, volume)
                elif long_signal == 1:
                    self.buy(bar.close_price, volume)

        elif self.pos > 0:
            
            pnl_rate = (bar.close_price - self.long_entry) / self.long_entry
            if kcross_below:
                self.sell(bar.close_price, abs(self.pos))
            else:
                self.long_sl = self.long_entry * (1-0.02)
                self.sell(self.long_sl, abs(self.pos), True)

        elif self.pos < 0:

            pnl_rate = (self.short_entry - bar.close_price) / bar.close_price
            if kcross_above:
                self.cover(bar.close_price, abs(self.pos))
            else:
                self.short_sl = self.short_entry * (1+0.02)
                self.cover(self.short_sl, abs(self.pos), True)
        

        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        if trade.offset == Offset.OPEN:
            if trade.direction == Direction.LONG:
                self.long_entry = trade.price
            elif trade.direction == Direction.SHORT:
                self.short_entry = trade.price
        
        elif trade.offset == Offset.CLOSE:
            if trade.direction == Direction.SHORT:
                self.capital += (trade.price - self.long_entry) * trade.volume
            elif trade.direction == Direction.LONG:
                self.capital += (self.short_entry - trade.price) * trade.volume

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
