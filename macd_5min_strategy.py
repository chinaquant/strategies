from tkinter import N
from scipy.stats import linregress
import numpy as np

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

class Macd5minStrategy(CtaTemplate):
    author = "用Python的交易员"

    atr_value = None
    ema_value = None
    signal_dt = None
    hist_signal = 0

    positive_count = 0
    nagetive_count = 0

    parameters = []
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar, Interval.MINUTE)
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
        


      


    def on_5min_bar(self, bar):

        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        rsi = am.rsi(14)

        self.atr_value = am.atr(20)
        self.ema_value = ema = am.ema(20, True)
        macd, signal, hist = am.macd(12, 26, 9, True)


        kcross_above = bar.close_price > ema[-1] and am.close[-2] < ema[-2]
        kcross_below = bar.close_price < ema[-1] and am.close[-2] > ema[-2]


        if hist[-1] > 0 and hist[-2] < 0:
            self.hist_signal = 1
            self.signal_dt = bar.datetime
        elif hist[-1] < 0 and hist[-2] > 0:
            self.hist_signal = -1
            self.signal_dt = bar.datetime

        if self.signal_dt and (bar.datetime - self.signal_dt).total_seconds() / 60 > 25:
            self.signal_dt = None
            self.hist_signal = 0

        if self.pos == 0:
 
            
            if kcross_above and self.hist_signal == 1:

                _array = np.flip(hist[:-1])
                idx = np.argmax(_array>0)

                if idx >= 20:
                    self.buy(bar.close_price, 2)

            elif kcross_below and self.hist_signal == -1:

                _array = np.flip(hist[:-1])
                idx = np.argmax(_array<0)

                if idx >= 20:
                    self.short(bar.close_price, 2)
        
        elif self.pos > 0:

            if (bar.close_price - self.long_entry) - self.long_entry * 0.001 > 0:
                
                if self.pos == 2:
                    self.sell(bar.close_price, 1)

                # self.long_sl = self.long_entry * (1+0.001)
                self.long_sl = ema[-1]
                self.sell(self.long_sl, 1, True) 

            else:
                self.sell(self.long_sl, abs(self.pos), True)

        elif self.pos < 0:

            if (self.short_entry - bar.close_price) - self.short_entry * 0.001 > 0:
                
                if self.pos == -2:
                    self.cover(bar.close_price, 1)

                # self.short_sl = self.short_entry * (1-0.001)
                self.short_sl = ema[-1]
                self.cover(self.short_sl, 1, True) 


            else:
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
                self.long_sl = trade.price - self.atr_value

                self.sell(self.long_sl, trade.volume, True)

            elif trade.direction == Direction.SHORT:

                self.short_entry = trade.price
                self.short_sl = trade.price + self.atr_value
                
                self.cover(self.short_sl, trade.volume, True)

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
