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

class SqueezeStrategy(CtaTemplate):
    author = "用Python的交易员"

    last_y = None

    parameters = []
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 4, self.on_4hour_bar, Interval.HOUR)
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

    def on_4hour_bar(self, bar):

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

    

        # b_up, b_down = am.boll(20, 2, True)
        # k_up, k_down = am.keltner(20, 1.5, True)
        # val = linreg(source  -  avg(avg(highest(high, lengthKC), lowest(low, lengthKC)),sma(close,lengthKC)), 
        #    lengthKC,0)


        #avg(avg(highest(high, lengthKC), lowest(low, lengthKC)),sma(close,lengthKC))

        a = max(am.high[-20:])
        b = min(am.low[-20:])
        
        avg = ((a+b)/2 + am.sma(20))/2
        # print(avg)

        x = [range(0, 20)]
        y = am.close[-20:] - avg

        # print(y)
        val = linregress(x, y)
        # print(val)
        
        # y = kx+b
        y = val.intercept + val.slope*20
        # print(bar.datetime, y)

        if not self.last_y:
            self.last_y = y
            return

        """
        1、开仓：红绿切换 多：红变绿 空：绿变红
		2、平仓：颜色变深
        """

        if self.pos == 0:
            if y > 0 and self.last_y < 0:
                self.short(bar.close_price, 1)
            
            elif y < 0 and self.last_y > 0:
                self.buy(bar.close_price, 1)

        elif self.pos > 0:
            
            if y < self.last_y:
                self.sell(bar.close_price, 1)


        elif self.pos < 0:
            
            if y > self.last_y:
                self.cover(bar.close_price, 1)

        self.last_y = y

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
