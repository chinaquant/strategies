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

from vnpy.trader.constant import Interval, Direction, Offset

class BollStrategy(CtaTemplate):
    author = "用Python的交易员"

    last_bar = None
    trade_bar = None
    long_sl = None
    short_sl = None

    short_entry = None
    long_entry = None

    long_entry_dt = None
    short_entry_dt = None

    parameters = []
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg_4hour = BarGenerator(self.on_bar, 4, self.on_4hour_bar, Interval.HOUR)
        self.am_4hour = ArrayManager(51)


    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(10)

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
        self.bg_4hour.update_bar(bar)

    def on_4hour_bar(self, bar):


        self.cancel_all()

        am = self.am_4hour
        am.update_bar(bar)
        if not am.inited:
            return

        # 上下轨
        up, down = am.boll(50, 2, True)
        sma = am.sma(50, True)

        # k穿均线
        k_crossbelow = bar.close_price < sma[-1] and am.close[-2] > sma[-2]
        k_crossabove = bar.close_price > sma[-1] and am.close[-2] < sma[-2]

        # 计算当前价格突破布林轨道的亮度大小
        # 用最后两个k线的实体振幅之和衡量
        a = (am.close[-3] - am.open[-3])/am.open[-3] 
        b = (am.close[-2] - am.open[-2])/am.open[-2]
        c = (am.close[-1] - am.open[-1])/am.open[-2]

        if self.pos == 0:
            if a+b+c > 0.05:
                if bar.close_price > up[-1]:
                    self.buy(bar.close_price, 1)
            
            if a+b+c < -0.05:
                if bar.close_price < down[-1]:
                    self.short(bar.close_price, 1)
        
        elif self.pos > 0:

            if (bar.datetime - self.long_entry_dt).total_seconds() / (60*60) <= 12 and \
                bar.close_price - self.long_entry < 0:
                    if bar.open_price < up[-1]:
                        self.sell(bar.close_price, abs(self.pos))

            elif bar.close_price - self.long_entry > 0:
                sl = max(self.long_entry, bar.close_price*(1-0.01))
                self.long_sl = max(self.long_sl, sl)
                self.sell(self.long_sl, abs(self.pos), True)

                if k_crossbelow:
                    self.sell(bar.close_price, abs(self.pos))
            


        elif self.pos < 0:

            if (bar.datetime - self.short_entry_dt).total_seconds() / (60*60) <= 12 and \
                self.short_entry - bar.close_price < 0:
                    if bar.close_price > down[-1]:
                        self.cover(bar.close_price, abs(self.pos))
            
            elif self.short_entry - bar.close_price > 0:

                sl = min(self.short_entry, bar.close_price * (1+0.01))
                self.short_sl = min(self.short_sl,  sl)
                self.cover(self.short_sl, abs(self.pos), True)

                if k_crossabove:
                    self.cover(bar.close_price, abs(self.pos))

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
                self.long_sl = trade.price * (1-0.01)
                self.long_entry = trade.price
                self.long_entry_dt = trade.datetime

            elif trade.direction == Direction.SHORT:
                self.short_sl = trade.price * (1+0.01)

                self.short_entry = trade.price
                self.short_entry_dt = trade.datetime

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
