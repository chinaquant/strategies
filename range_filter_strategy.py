from csv import Dialect
import numpy as np

import talib



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

from vnpy.trader.constant import Offset, Direction



class RangeFilterStrategy(CtaTemplate):

    author = "用Python的交易员"

    bar_window = 15
    fixed_size = 1

    n = 20
    qty = 3.5

    atr_value = 0
    long_entry = None
    short_entry = None

    parameters = ["bar_window", "fixed_size"]
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, self.bar_window, self.on_xmin_bar)
        self.am = ArrayManager()

        self.rfilt = [0, 0]

        self.hist_filt = []

        self.CondIni = 0

        self.klines_std = []

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
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.bg.update_bar(bar)


    def on_xmin_bar(self, bar):
        """"""
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        sec_filter = self.secret_filter(bar)
        if not sec_filter:
            return

        rsi_value = am.rsi(7)

        # rng_size
        wper = (self.n*2) - 1
        avrng = talib.EMA(np.abs(np.diff(am.close)), self.n)
        AC = talib.EMA(avrng, wper)*self.qty
        rng_size = AC[-1]

        # rng_filt
        self.rfilt[1] = self.rfilt[0]

        if bar.close_price - rng_size > self.rfilt[1]:
            self.rfilt[0] = bar.close_price - rng_size
        
        if bar.close_price + rng_size < self.rfilt[1]:
            self.rfilt[0] = bar.close_price + rng_size

        rng_filt1 = self.rfilt[0]

        hi_band   = rng_filt1 + rng_size
        lo_band   = rng_filt1 - rng_size
        rng_filt  = rng_filt1

    
        # Direction Conditions

        self.hist_filt.append(rng_filt)

        upward = 0
        downward = 0

        if len(self.hist_filt) > 1:

            if self.hist_filt[-1] > self.hist_filt[-2]:
                upward = 1
            elif self.hist_filt[-1] < self.hist_filt[-2]:
                downward = 1

        # //Trading Condition
        longCond = bar.close_price > rng_filt and bar.close_price > am.close_array[-2] and upward > 0 or \
                   bar.close_price > rng_filt and bar.close_price < am.close_array[-2] and upward > 0 
        
        shortCond = bar.close_price < rng_filt and bar.close_price < am.close_array[-2] and downward > 0 or \
                    bar.close_price < rng_filt and bar.close_price > am.close_array[-2] and downward > 0

        longCondition = longCond# and self.CondIni == -1
        shortCondition = shortCond# and self.CondIni == 1 

        if longCond:
            self.CondIni = 1
        elif shortCond:
            self.CondIni = -1
        else:
            self.CondIni = 0


        if self.pos == 0:

            self.long_entry = None
            self.short_entry = None
   
            self.atr_value = self.am.atr(20)

            if longCondition and rsi_value > 80:
                
                if sec_filter < 20:
                    self.buy(bar.close_price, self.fixed_size)

            elif shortCondition and rsi_value < 20:
                
                if sec_filter < 20:
                    self.short(bar.close_price, self.fixed_size)
        
        elif self.pos > 0:
      
            self.send_buy_orders(self.long_entry)

            
            _stop = self.long_entry - self.atr_value
            
            long_stop = max(_stop, rng_filt)

            self.sell(rng_filt, abs(self.pos), True)

        elif self.pos < 0:
            
            self.send_short_orders(self.short_entry)

            _stop = self.short_entry  + self.atr_value

            short_stop = min(_stop, rng_filt)
            
            self.cover(rng_filt, abs(self.pos), True)

        

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
        if Offset.OPEN == trade.offset:
            if Direction.LONG == trade.direction:
        
                    self.long_entry = trade.price
            
            elif Direction.SHORT == trade.direction:
           
                    self.short_entry = trade.price
        
        # elif Offset.CLOSE == trade.offset:
        #     if Direction.LONG == trade.direction:
        #         self.short_entry = None
        #     elif Direction.SHORT == trade.direction:
        #         self.long_entry = None

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

    def send_buy_orders(self, price):
        """"""
        t = self.pos / self.fixed_size
          
        if t < 1:
            self.buy(price, self.fixed_size, True)

        if t < 2:
            self.buy(price + self.atr_value * 2, self.fixed_size, True)

        if t < 3:
            self.buy(price + self.atr_value * 2.5, self.fixed_size, True)

        if t < 4:
            self.buy(price + self.atr_value * 3, self.fixed_size, True)

    def send_short_orders(self, price):
        """"""
        t = self.pos / self.fixed_size

        if t > -1:
            self.short(price, self.fixed_size, True)

        if t > -2:
            self.short(price - self.atr_value * 2, self.fixed_size, True)

        if t > -3:
            self.short(price - self.atr_value * 2.5, self.fixed_size, True)

        if t > -4:
            self.short(price - self.atr_value * 3, self.fixed_size, True)



























    def secret_filter(self, bar):
        """"""
        kline_std = talib.STDDEV(np.array([bar.open_price, bar.high_price, bar.low_price, bar.close_price]), 4, 2)

        # print(bar.datetime, kline_std)
        self.klines_std.append(kline_std[-1])
        if len(self.klines_std) < 30:
            return

        mean_std = sum(self.klines_std[-30:]) / len(self.klines_std[-30:]) 
        
        return mean_std