"""
update on: 2022/3/9 假设不一定正确，缺少其他指标的结合。也有一定的作用。

volatility 策略

需要解决的问题：
1，在区间内的价格策略，为什么胜率比较高（>60%）？因为自然？
2，胜率高，为什么还是不怎么赚钱？因为盈亏比降低。损失主要是因为几个大的盈亏比造成。
3，为什么添加止损，反而胜率变低，且效果变差？因为当前价格与止损距离非常近，所以胜率变低。

一、交易逻辑
1，假设价格“随机”波动。
2，假设价格”通常“在“区间”随机波动。
3，假设价格"突破"“区间”，则形成“新区间”。
4，假设价格"跌破"“区间”，则形成“新区间”。
5，假设价格在”新区间“波动。
6，重复1-5。

注：假设价格"通常"在“区间”波动，即使在“新区间”亦如此。
注：假设价格“很难”“逃脱”“区间”。

一、开仓逻辑
    取30分钟周期的Bollinger Bands(BB).
    DEL: 取30分钟周期的sma与stddev，确定“上边界”与“下边界”。

1，价格“接近” BB down band，则开多仓。
2，价格“接近” BB upper band，则开空仓。

二、平仓逻辑

1，若持多仓，价格接近 BB upper band，则平多、开空。
2，若持空仓，价格接近 BB down band，则平空、开多。

三、盈利原理
    因为 BB 的 upper band 和 down band 对于价格启动一定的“支撑”和“阻力”，
    所以概率上价格会再此“区间”波动。

四、策略变量

1，上边界
    upper band

2，下边界
    down band

3，区间：
    upper band - down band。

5，接近
    当前价格 < (上边界+下边界)/2，则价格接近于下边界。
    当前价格 > (上边界+下边界)/2，则价格接近于上边界。

注：period 30 BB
注：标准差
    在实际应用上，常考虑一组数据具有近似于正态分布的概率分布。
    若其假设正确，则约68%数值分布在距离平均值有1个标准差之内的范围，
    约95%数值分布在距离平均值有2个标准差之内的范围，
    以及约99.7%数值分布在距离平均值有3个标准差之内的范围。
    称为“68-95-99.7法则”。
注：
   比特币一个
   标准差取150，则胜率最高（80%），应该是比特币的特点所致。比特币的涨跌平均值为300？
   但是靠标准差提高胜率，则意味着无非细粒度交易。
   标准差取值没有最好的，主要是看整个交易规则。
"""


from tkinter.messagebox import NO
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

from vnpy.trader.constant import Interval, Direction, Offset, Exchange
from vnpy.app.cta_strategy.base import EngineType

class QCTWXStrategy(CtaTemplate):

    author = "CQ"

    bar_window = 15
    sma_window = 120
    boll_window = 120 
    fixed_size = 1.0
    cross_ratio = 1/10  # 交数

    price_add = 0.0005

    last_cross_price = None
    last_cross_dt = None
    closed_loop_tag = -1
    closed_loop_dt = None
    cross_minutes = 0
    virtual_pnl_rate = 0
    may_entry_consolidate = False

    boll_up = None
    boll_down = None

    long_entry_price = None
    short_entry_price = None

    long_entry_dt = None
    short_entry_dt = None

    near_up_signal = False
    near_down_signal = False

    long_signal = False
    short_signal = False

    long_sl = None
    short_sl = None

    parameters = [
        "bar_window",
        "sma_window",
        "boll_window",
        "fixed_size",
        "cross_ratio",
    ]


    variables = ["boll_up", "boll_down"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar, self.bar_window, self.on_xmin_bar)

        self.am = ArrayManager(121)

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

    def on_xmin_bar(self, bar: BarData):
        """"""
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        ## 指标计算
        sma = am.sma(self.sma_window, array=True)

        self.boll_up, self.boll_down = am.boll(self.boll_window, 2, array=True)

        ## 信号计算

        self.boll_long_signal = False
        self.boll_short_signal = False
        
        if bar.close_price > self.boll_up[-1]:

            self.boll_long_signal = True

        elif bar.close_price < self.boll_down[-1]:

            self.boll_short_signal = True


        # 延长信号时间
        if self.is_near_upper(bar.close_price):

            self.near_up_signal = True
            self.near_down_signal = False

        elif self.is_near_down(bar.close_price):

            self.near_down_signal = True
            self.near_up_signal = False

        self.long_signal = False
        self.short_signal = False

        if self.near_up_signal:

            self.short_signal = True

        elif self.near_down_signal:

            self.long_signal = True

        # 15分钟
        bar15min_stand_over = bar.close_price > sma[-1] and am.close_array[-2] < sma[-2]
        bar15min_stand_below = bar.close_price < sma[-1] and am.close_array[-2] > sma[-2]

        ## 检测下一个震荡区间
        # 根据K上下穿越一次均线的时长。若超过20小时，则预测从此开始会有一定时长的震荡行情。
        if bar15min_stand_over or bar15min_stand_below:
            
            self.closed_loop_tag *= -1

            pnl = 0

            if not self.last_cross_price:
                self.last_cross_price = bar.close_price
                self.last_cross_dt = bar.datetime
            else:
                pnl = bar.close_price - self.last_cross_price
            

            self.virtual_pnl_rate = abs(pnl / self.last_cross_price) * 100
            self.cross_minutes = (bar.datetime - self.last_cross_dt).total_seconds()/60
                
            self.last_cross_price = bar.close_price
            self.last_cross_dt = bar.datetime


        # 可能进入盘整行情
        if self.closed_loop_tag == 1:

            self.closed_loop_tag = -1   # NOTE 开合是无缝连接的，所以马上又设置为-1。

            # if self.cross_minutes >= 10*60 and self.virtual_pnl_rate >= 0.5:
            if self.virtual_pnl_rate * self.cross_minutes >= 1200:

                # print(f"可能进入震荡行情 {bar.datetime} >>> virtual_pnl_rate {self.virtual_pnl_rate}") 

                self.closed_loop_dt = bar.datetime
                self.may_entry_consolidate = True
        

        # 可能突破盘整
        if self.boll_long_signal or self.boll_short_signal:

            self.may_entry_consolidate = False 
        

        ## 仓位执行
        if self.pos == 0:

            if (self.boll_up[-1] - self.boll_down[-1]) / self.boll_down[-1] < 0.04:
                return

            if self.may_entry_consolidate:
                
                if self.long_signal:

                        price = bar.close_price * (1 + self.price_add)

                        self.buy(price, self.fixed_size)

                elif self.short_signal:
                    
                        price = bar.close_price * (1 - self.price_add)

                        self.short(price, self.fixed_size)

        elif self.pos > 0:

            price = bar.close_price * (1 - self.price_add)

            if self.is_near_upper(bar.close_price):

                self.sell(price, abs(self.pos))

            elif (bar.datetime - self.long_entry_dt).total_seconds() / 60 > 60*2:
                if (self.long_entry_price-bar.close_price)/bar.close_price > 0.01:
                    self.sell(bar.close_price, abs(self.pos))

        elif self.pos < 0:

            price = bar.close_price * (1 + self.price_add)

            if self.is_near_down(bar.close_price):

                self.cover(price, abs(self.pos))

            elif (bar.datetime - self.short_entry_dt).total_seconds() / 60 > 60*2:
                if (bar.close_price - self.short_entry_price)/self.short_entry_price > 0.01:
                    self.cover(bar.close_price, abs(self.pos))

        self.put_event()

    def is_near_upper(self, price) -> bool:
        """
        在区间之内，接近上边界。
        """
        if self.boll_up[-1] == self.boll_down[-1]:
            return False

        weigth = self.boll_up[-1] - self.boll_down[-1]

        return (abs(price - self.boll_up[-1]) / weigth) < self.cross_ratio

    def is_near_down(self, price) -> bool:
        """
        在区间之内，接近下边界。
        """

        if self.boll_up[-1] == self.boll_down[-1]:
            return False

        weigth = self.boll_up[-1] - self.boll_down[-1]

        return (abs(price - self.boll_down[-1]) / weigth) < self.cross_ratio

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """

        # NOTE: 因为Bybit/FTX为单向净持仓，trade回报没有Offset参数，所以需要先确定offset。
        # 猜测offset

        # if self.get_engine_type() == EngineType.LIVE:

        #     if trade.exchange in [Exchange.BYBIT, Exchange.FTX]:

        #         if self.pos == 0:
        #             trade.offset = Offset.OPEN

        #         elif self.pos > 0:
        #             if trade.direction == Direction.LONG:
        #                 trade.offset = Offset.OPEN
        #             elif trade.direction == Direction.SHORT:
        #                 trade.offset = Offset.CLOSE

        #         elif self.pos < 0:
        #             if trade.direction == Direction.SHORT:
        #                 trade.offset = Offset.OPEN
        #             elif trade.direction == Direction.LONG:
        #                 trade.offset = Offset.CLOSE

        if trade.offset == Offset.CLOSE:

            if trade.direction == Direction.SHORT:
                # 平多
                self.pnl_rate = (trade.price - self.long_entry_price) / self.long_entry_price * 100

            elif trade.direction == Direction.LONG:
                # 平空
                self.pnl_rate = (self.short_entry_price - trade.price) / self.short_entry_price * 100

        elif trade.offset == Offset.OPEN:

            if trade.direction == Direction.LONG:

                self.long_entry_price = trade.price
                self.long_entry_dt = trade.datetime
                self.long_sl = trade.price * (1-0.01)

            elif trade.direction == Direction.SHORT:

                self.short_entry_price = trade.price
                self.short_entry_dt = trade.datetime
                self.short_sl = trade.price * (1+0.01)

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass