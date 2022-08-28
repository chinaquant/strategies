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

from vnpy.trader.constant import Direction, Offset

class Scalping5MinuteStrategy(CtaTemplate):

    author = "用Python的交易员"



    parameters = []
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(1)

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
        """"""

        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 指标计算
        mid = am.sma(20, True)
        up, down = am.boll(20, 2, True)

        rsi = am.rsi(7, True)

        # slowk, slowd = STOCH(high, low, close, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
        slowk, slowd = talib.STOCH(am.high, am.low, am.close, fastk_period=7, slowk_period=3, slowd_period=3)

        # 信号计算
        isat_bolldown = bar.close_price < down[-1]
        isat_bollup = bar.close_price > down[-1]

        rsi_overbought = rsi[-1] > 70
        rsi_oversell = rsi[-1] < 30

        stoch_crossup = slowk[-1] > slowd[-1] and slowk[-2] < slowd[-2]
        stoch_crossdown = slowk[-1] < slowd[-1] and slowk[-2] > slowd[-2]

        # 仓位操作
        if self.pos == 0:
            if isat_bolldown and rsi_oversell and stoch_crossup:
                self.buy(bar.close_price, 1)
            elif isat_bollup and rsi_overbought and stoch_crossdown:
                self.short(bar.close_price, 1)
        
        elif self.pos > 0:
            if bar.close_price > mid[-1]:
                self.sell(bar.close_price, abs(self.pos))
            else:
                self.sell(self.low, abs(self.pos), True)

        elif self.pos < 0:

            if bar.close_price < mid[-1]:
                self.cover(bar.close_price, abs(self.pos))
            else:
                self.cover(self.high, abs(self.pos), True)


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
            self.low = self.am.low[-2]
            self.high = self.am.high[-2]

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
