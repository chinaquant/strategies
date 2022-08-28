from csv import Dialect
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

class AvgBarData(BarData):
    """"""
    pass

class UpDownStrategy(CtaTemplate):
    author = "用Python的交易员"

    fixed_size = 1

    sma_window = 20

    atr_window = 20
    rsi_window = 14

    rsi_up = 70
    rsi_down = 30

    hour_trend = 0 # 0无趋势， -1 空，1 多

    sma_value = None

    long_entry = None
    short_entry = None

    parameters = ["fixed_size", "sma_window", "atr_window","rsi_window", "rsi_up", "rsi_down"]
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.am = ArrayManager()

        self.bg_hour = BarGenerator(self.on_bar, 1, self.on_hour_bar, Interval.HOUR)
        self.am_hour = ArrayManager()

        self.left_avgbar = None
        self.right_avgbar = None


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
        self.bg_hour.update_bar(bar)
        self.bg.update_bar(bar)

    def on_hour_bar(self, bar):
        """"""
        am = self.am_hour
        am.update_bar(bar)
        if not am.inited:
            return
        
        self.sma_value = sma = am.sma(self.sma_window)

        if bar.close_price > sma:
            self.hour_trend = 1
        
        elif bar.close_price < sma:
            self.hour_trend = -1


    def on_15min_bar(self, bar):
        """
        开盘价=（前期开盘价+前期收盘价）/ 2
        收盘价=（当期开盘价+当期收盘价+当期最高价+当期最低价）/ 4
        高价= 最高值（高点，开市价，收市价）
        低价=最低值（低点，开市价，收市价）
        """
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        self.atr_value = am.atr(self.atr_window)

        rsi_value = am.rsi(self.rsi_window)

        self.left_avgbar = AvgBarData(symbol=bar.symbol, gateway_name=bar.gateway_name, exchange=bar.exchange, datetime=bar.datetime)

        self.left_avgbar.open_price = (am.open[-3] + am.close[-3])/2
        self.left_avgbar.close_price = (am.open[-2] + am.close[-2] + am.high[-2] + am.low[-2]) /4
        self.left_avgbar.high_price = max(am.high[-2], am.open[-2], am.close[-2])
        self.left_avgbar.low_price = min(am.low[-2], am.open[-2], am.close[-2])

        self.right_avgbar = AvgBarData(symbol=bar.symbol, gateway_name=bar.gateway_name, exchange=bar.exchange, datetime=bar.datetime)

        self.right_avgbar.open_price = (am.open[-2] + am.close[-2])/2
        self.right_avgbar.close_price = (am.open[-1] + am.close[-1] + am.high[-1] + am.low[-1]) /4
        self.right_avgbar.high_price = max(am.high[-1], am.open[-1], am.close[-1])
        self.right_avgbar.low_price = min(am.low[-1], am.open[-1], am.close[-1])


        # print(self.right_avgbar)

        up = False
        down = False

        green_2_red = False
        red_2_green = False

        if self.right_avgbar.close_price > self.right_avgbar.open_price and self.left_avgbar.close_price > self.left_avgbar.open_price:
            # print("左右K同为阳线")
            if self.right_avgbar.close_price > self.left_avgbar.high_price:
                # print(f"{bar.datetime} 上梯")
                up = True
        elif self.right_avgbar.close_price < self.right_avgbar.open_price and self.left_avgbar.close_price < self.left_avgbar.open_price:
            # print("左右K同为阴线")
            if self.right_avgbar.close_price < self.left_avgbar.low_price:
                # print(f"{bar.datetime} 下梯")
                down = True
        
        if self.right_avgbar.close_price < self.right_avgbar.open_price and \
            self.left_avgbar.close_price > self.left_avgbar.open_price and \
            self.right_avgbar.close_price < self.left_avgbar.low_price:

            green_2_red = True
        
        elif self.right_avgbar.close_price > self.right_avgbar.open_price and \
            self.left_avgbar.close_price < self.left_avgbar.open_price and \
            self.right_avgbar.close_price > self.left_avgbar.high_price:

            red_2_green = True

      

        # 开平仓操作
        if self.pos == 0:
            if self.hour_trend == 1:
                if up:
                    if rsi_value > self.rsi_up:
                        self.buy(bar.close_price, 1)
            
            elif self.hour_trend == -1:
                if down:
                    if rsi_value < self.rsi_down:
                        self.short(bar.close_price, 1)
        
        elif self.pos > 0:
            
            # if green_2_red:
            #     self.sell(bar.close_price, abs(self.pos))

            if bar.close_price < self.sma_value:
                self.sell(bar.close_price, abs(self.pos))
            
            # 红变绿加仓
            elif red_2_green:

                # if (bar.close_price - self.long_entry)/self.long_entry >= 0.02:
                #     self.buy(bar.close_price, 1)
                self.send_buy_orders(bar.close_price)
        
        elif self.pos < 0:
            # if red_2_green:
            #     self.cover(bar.close_price, abs(self.pos))

            if bar.close_price > self.sma_value:
                self.cover(bar.close_price, abs(self.pos))

            elif green_2_red:

                # if (self.short_entry - bar.close_price)/bar.close_price >= 0.02:
                #     self.short(bar.close_price, 1)
                self.send_short_orders(bar.close_price)

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
            if trade.direction == Direction.LONG:
                self.short_entry = None
            elif trade.direction == Direction.SHORT:
                self.long_entry = None

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

    def send_buy_orders(self, price):
        """"""
        t = self.pos / self.fixed_size

        # if t < 1:
        #     self.buy(price, self.fixed_size, True)


        if t < 2:
            if price > self.long_entry + self.atr_value * 0.5:
                self.buy(price, self.fixed_size)

        if t < 3:
            if price > self.long_entry + self.atr_value * 1:
                self.buy(price, self.fixed_size)

        if t < 4:
            if price > self.long_entry + self.atr_value * 1.5:
                self.buy(price, self.fixed_size)


    def send_short_orders(self, price):
        """"""
        t = self.pos / self.fixed_size

        # if t > -1:
        #     self.short(price, self.fixed_size, True)

        if t < -2:
            if price < self.short_entry - self.atr_value * 0.5:
                self.short(price, self.fixed_size)

        if t < -3:
            if price < self.short_entry - self.atr_value * 1:
                self.short(price, self.fixed_size)

        if t < -4:
            if price < self.short_entry - self.atr_value * 1.5:
                self.short(price, self.fixed_size)