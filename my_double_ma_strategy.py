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

from vnpy.trader.constant import Interval

class MyDoubleMaStrategy(CtaTemplate):
    author = "Wechat: JackC0001"

    fast_window = 20
    slow_window = 80

    fast_ma0 = 0.0
    fast_ma1 = 0.0

    slow_ma0 = 0.0
    slow_ma1 = 0.0

    parameters = ["fast_window", "slow_window"]
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg_1hour = BarGenerator(self.on_bar, 1, self.on_1hour_bar, Interval.HOUR)
        self.am_1hour = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(2)

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
        self.bg_1hour.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg_1hour.update_bar(bar)
    
    def on_1hour_bar(self, bar):
        """"""
        am = self.am_1hour
        am.update_bar(bar)
        if not am.inited:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 < self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 > self.slow_ma1

        k_cross_below = bar.close_price < fast_ma[-1] and am.close[-2] > fast_ma[-2]
        k_cross_over = bar.close_price > fast_ma[-1] and am.close[-2] < fast_ma[-2]

        if self.pos == 0:
            if cross_over:
                self.buy(bar.close_price, 1)
            elif cross_below:
                self.short(bar.close_price, 1)
        
        elif self.pos > 0:
            if k_cross_below:
                self.sell(bar.close_price, abs(self.pos))
        
        elif self.pos < 0:
            if k_cross_over:
                self.cover(bar.close_price, abs(self.pos))
                

        # if cross_over:
        #     if self.pos == 0:
        #         self.buy(bar.close_price, 1)
        #     elif self.pos < 0:
        #         self.cover(bar.close_price, 1)
        #         self.buy(bar.close_price, 1)

        # elif cross_below:
        #     if self.pos == 0:
        #         self.short(bar.close_price, 1)
        #     elif self.pos > 0:
        #         self.sell(bar.close_price, 1)
        #         self.short(bar.close_price, 1)

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
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
