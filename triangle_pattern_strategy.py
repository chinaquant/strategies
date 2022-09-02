import numpy as np
from enum import Enum

from datetime import datetime
import pytz
from tzlocal import get_localzone_name

from scipy.stats import linregress

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


china_tz = pytz.timezone(get_localzone_name())

class Point:

    def __init__(self, x, y):
        self.x = x
        self.y = y

class MathTool:

    def get_pointA(self, k1, b1):
        """
        """
        x = 1
        y = k1*x + b1

        return Point(1, y)
    
    def get_pointB(self, k2, b2):
        """ 
        """
        x = 1
        y = k2*x + b2

        return Point(1, y)

    def get_pointO(self, k1, b1, k2, b2):
        """
        cross point
        """

        # 计算交点
        # k1 = slmin
        # b1 = intercmin

        # k2 = slmax
        # b2 = intercmax

        cross_x = (b2-b1)/(k1-k2)
        cross_y = k1*cross_x + b1

        return Point(cross_x, cross_y)

    def isInRegion(self, O, A, B, P):
        """
        if isInRegion(O, A, B) is true, P is in the first region.
        otherwise, isInRegion(O, B, A) will be true.
        """
        return self.isCCW(O, A, P) and not self.isCCW(O, B, P)
    
    def isCCW(self, a, b, c):
        """    
        ref: http://www.cs.cmu.edu/%7Equake/robust.html
        For more robust methods, see the link.
        """
        return ((a.x - c.x)*(b.y - c.y) - (a.y - c.y)*(b.x - c.x)) > 0

class TrianglePattern(Enum):

    REGULAR = "正收敛三角形"
    UPPER = "向上收敛三角形"
    DOWN = "向下收敛三角形"

class TrianglePatternStrategy(CtaTemplate):
    author = "用Python的交易员"

    bar_window = 15
    backcandles = 30

    fixed_size = 1

    skip_num = 0
    recalc = False

    k1 = None
    b1 = None
    k2 = None
    b2 = None

    minim = None
    maxim = None

    last_pattern = None
    last_pattern_dt = None

    is_inregion = False
    is_usedenergy = False

    long_entry = None
    short_entry = None

    long_sl = None
    short_sl = None

    parameters = ["bar_window", "backcandles", "fixed_size"]
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

        self.bg_xmin = BarGenerator(self.on_bar, window=self.bar_window, on_window_bar=self.on_xmin_bar, interval=Interval.MINUTE)
        self.am_xmin = ArrayManager(100)

        self.pivots = []    # idx: value --> 1: peak, -1: valley
        self.bars = []

        self.upline_id = 0
        self.downline_id = 0
        self.pine_upline = None
        self.pine_downline = None
        self.line_id = 0

        self.math_tool = MathTool()

        self.log_file = open("/Users/apple/Downloads/triangle_pattern_strategy_log.txt", mode='w')

        self.pattern_open = None

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
        self.bg_xmin.update_bar(bar)

    def on_xmin_bar(self, bar: BarData):
        """"""
        am = self.am_xmin
        am.update_bar(bar)
        if not am.inited:
            return

        # self.movement_monitor(bar)
        self.generate_pattern(bar)
        self.place_order(bar)

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
                # self.long_sl = min(self.minim)
                self.long_sl = min(self.am_xmin.low_array[-self.backcandles:])

                self.pattern_open = self.last_pattern

            elif trade.direction == Direction.SHORT:

                self.short_entry = trade.price
                self.short_sl = max(self.am_xmin.high_array[-self.backcandles:])
                
                self.pattern_open = self.last_pattern

            # 开仓后，是否用过能量设为True。
            self.is_usedenergy = True

        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

    def generate_pattern(self, bar):
        """
        分析和计算箱体
        """   
        self.bars.append(bar)
        if len(self.bars) < 6:
            return

        pividlow = 1
        pividhigh = 1
        check_bar = self.bars[-3]

        for i in range(-6, 0):

            if check_bar.high_price < self.bars[i].high_price:
                pividhigh = 0
            
            if check_bar.low_price > self.bars[i].low_price:
                pividlow = 0


        if pividlow and not pividhigh:
            self.pivots.append((-1,(check_bar.datetime, check_bar.low_price)))
            self.recalc = True
        elif pividhigh and not pividlow:
            self.pivots.append((1,(check_bar.datetime, check_bar.high_price)))
            self.recalc = True
        else:
            self.pivots.append((0,(check_bar.datetime, check_bar.close_price)))
            self.recalc = False

        if len(self.pivots) < self.backcandles:
            return
        
        # 防止在一个箱体内多次计算。
        if self.recalc and self.last_pattern is not None and self.skip_num < 3:  
            self.skip_num += 1
  
        elif self.recalc:
            self.skip_num = 0

            maxim = np.array([])
            minim = np.array([])
            xxmin = np.array([])
            xxmax = np.array([])

            for i in range(-self.backcandles, 0):

                num = (bar.datetime - self.pivots[i][1][0]) / (self.bars[-1].datetime - self.bars[-2].datetime)
                if num < self.backcandles:

                    if self.pivots[i][0] == -1:

                        xxmin = np.append(xxmin, self.pivots[i][1][0].timestamp()) 
                        minim = np.append(minim, self.pivots[i][1][1])

                    elif self.pivots[i][0] == 1:

                        xxmax = np.append(xxmax, self.pivots[i][1][0].timestamp())    
                        maxim = np.append(maxim, self.pivots[i][1][1])
            

            if xxmax.size >= 3 and xxmin.size >= 3:

                slmax, intercmax, rmax, _, _ = linregress(xxmax, maxim)
                slmin, intercmin, rmin, _, _ = linregress(xxmin, minim)

                if abs(rmax) >= 0.6 and abs(rmin) >= 0.6:

                    pattern = None

                    if (slmax < 0 and slmax > -0.03) and (slmin > 0 and slmin < 0.03):
                        pattern = TrianglePattern.REGULAR
                        # print(f"{bar.datetime} 正收敛三角形")

                    elif 0 < slmax*1.5 < slmin:
                        pattern = TrianglePattern.UPPER
                        # print(f"{bar.datetime} 向上收敛三角形 zuli_jiage {minim[-1]}")

                    elif 0 > slmin > slmax/1.5:
                        pattern = TrianglePattern.DOWN
                        # print(f"{bar.datetime} 向下收敛三角形 ")   

                    self.last_pattern = pattern
                    self.last_pattern_dt = bar.datetime

                    self.k1 = slmin
                    self.b1 = intercmin
                    self.k2 = slmax
                    self.b2 = intercmax

                    self.minim = minim
                    self.maxim = maxim

                    if pattern:
                        # 新箱体形成，则是否用过能量设为False
  
                        upline = f"line.new({int(xxmin[0]*1000)}, {xxmin[0]*slmin+intercmin}, {int(xxmin[-1]*1000)}, {xxmin[-1]*slmin+intercmin}, extend = extend.none, xloc = xloc.bar_time)"
                        downline = f"line.new({int(xxmax[0]*1000)}, {xxmax[0]*slmax+intercmax}, {int(xxmax[-1]*1000)}, {xxmax[-1]*slmax+intercmax}, extend = extend.none, xloc = xloc.bar_time)"

                        self.upline_id = self.line_id
                        self.downline_id = self.line_id + 1
                        self.line_id += 2

                        self.pine_upline = f"line_{self.upline_id} = {upline}"
                        self.pine_downline = f"line_{self.downline_id} = {downline}"

                        # print(self.pine_upline)
                        # print(self.pine_downline)

                        self.log_file.write(self.pine_upline)
                        self.log_file.write('\n')
                        self.log_file.write(self.pine_downline)
                        self.log_file.write('\n')
                        
    def movement_monitor(self, bar):
        """"""
        if self.last_pattern:
            # print(f"{bar.datetime} 当前箱体是: {self.last_pattern.value}")
        
            # A是上趋势线的点，B是下趋势线的点，O是A与B的焦点
            O = self.math_tool.get_pointO(self.k1, self.b1, self.k2, self.b2)
            A = self.math_tool.get_pointA(self.k2, self.b2)
            B = self.math_tool.get_pointB(self.k1, self.b1)

            P = Point(bar.datetime.timestamp(), bar.close_price)

            pattern_end_dt = datetime.fromtimestamp(int(O.x), tz = china_tz)
            # print(f"{self.last_pattern.value} 箱体形成时间：{self.last_pattern_dt}，箱体结束位置：{pattern_end_dt}")
            
            is_inregion = self.math_tool.isInRegion(O, A, B, P)

            if is_inregion:
                delta_minutes = int((O.x-P.x)/60)
                # print(f"{bar.datetime} K线处于: {self.last_pattern.value}，距离箱体结束还剩(分钟): {delta_minutes}")
        
                # print(self.pine_upline)
                # print(self.pine_downline)
     
            elif not is_inregion and self.is_inregion:
                # print(f"{bar.datetime} K线突破 >>>>>>> {self.last_pattern.value}")

                pass 

            self.is_inregion = is_inregion
                

    def place_order(self, bar):
        """"""
        self.cancel_all()

        if self.pos == 0:

            if self.last_pattern == TrianglePattern.UPPER:

                zuli_jiage = self.minim[-1] # 跌破最近波谷做空
                self.short(zuli_jiage, self.fixed_size, True)

            elif self.last_pattern == TrianglePattern.DOWN:
                
                zuli_jiage = self.maxim[-1] # 突破最近波峰做多
                self.buy(zuli_jiage, self.fixed_size, True)

            elif self.last_pattern == TrianglePattern.REGULAR:

                NotImplemented
                # zuli_jiage = self.maxim[-1]
                # zhicheng_jiage = self.minim[-1]

                # self.short(zhicheng_jiage, self.fixed_size, True)
                # self.buy(zuli_jiage, self.fixed_size, True)

        
        elif self.pos > 0:

            # if self.last_pattern is not None and self.last_pattern != self.pattern_open:
            #     self.sell(bar.close_price, abs(self.pos))

            # else:
                if (bar.high_price - self.long_entry) / self.long_entry >= 0.04:
                    sl = bar.high_price * (1 - 0.005)
                    self.long_sl = max(self.long_sl, sl)

                self.sell(self.long_sl, abs(self.fixed_size), True)

        
        elif self.pos < 0:
            
            # if self.last_pattern is not None and self.last_pattern != self.pattern_open:
            #     self.cover(bar.close_price, abs(self.pos))

            # else:
                if (self.short_entry - bar.low_price) / bar.low_price >= 0.04:
                    sl = bar.low_price * (1 + 0.005)
                    self.short_sl = min(self.short_sl, sl)

                self.cover(self.short_sl, abs(self.fixed_size), True)

            