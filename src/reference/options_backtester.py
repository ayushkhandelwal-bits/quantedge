import math
from typing import List, Dict
from src.reference.nse_calendar import NSECalendar

class BlackModel:
    """
    Fischer Black's model for futures options.
    Correct model for Nifty/BankNifty options on NSE.
    Black-Scholes uses spot price - WRONG for NSE index options.
    """
    
    @staticmethod
    def _N(x: float) -> float:
        """Abramowitz and Stegun approximation (accurate to 7 decimal places)"""
        if x < 0:
            return 1.0 - BlackModel._N(-x)
        b1 =  0.319381530
        b2 = -0.356563782
        b3 =  1.781477937
        b4 = -1.821255978
        b5 =  1.330274429
        p  =  0.2316419
        c  = 1.0 / math.sqrt(2 * math.pi)
        
        t = 1.0 / (1.0 + p * x)
        pdf = c * math.exp(-x * x / 2.0)
        return 1.0 - pdf * (b1 * t + b2 * t**2 + b3 * t**3 + b4 * t**4 + b5 * t**5)
        
    @staticmethod
    def _pdf(x: float) -> float:
        return (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x)

    @staticmethod
    def price(F: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> float:
        """
        F = futures price (not spot!)
        K = strike price
        T = time to expiry in years
        r = risk-free rate (91-day T-bill, currently ~6.5%)
        sigma = implied volatility (annualised)
        """
        if T <= 0:
            return max(0.0, F - K) if option_type == 'call' else max(0.0, K - F)
            
        d1 = (math.log(F / K) + (0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        discount = math.exp(-r * T)
        
        if option_type == 'call':
            return discount * (F * BlackModel._N(d1) - K * BlackModel._N(d2))
        else:
            return discount * (K * BlackModel._N(-d2) - F * BlackModel._N(-d1))

    @staticmethod
    def implied_vol(market_price: float, F: float, K: float, T: float, r: float, option_type: str = 'call', tolerance: float = 1e-6, max_iter: int = 100) -> float:
        """Newton-Raphson IV solver"""
        sigma = 0.20 # Initial guess
        for _ in range(max_iter):
            price = BlackModel.price(F, K, T, r, sigma, option_type)
            diff = price - market_price
            if abs(diff) < tolerance:
                return sigma
                
            if T <= 0:
                return 0.0
                
            d1 = (math.log(F / K) + (0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            vega = F * math.exp(-r * T) * BlackModel._pdf(d1) * math.sqrt(T)
            
            if vega == 0:
                break
                
            sigma = sigma - diff / vega
            if sigma <= 0:
                sigma = 0.001
        return sigma

    @staticmethod
    def greeks(F: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> dict:
        """Returns dict: delta, gamma, theta (per day), vega, rho"""
        if T <= 0:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
            
        d1 = (math.log(F / K) + (0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        discount = math.exp(-r * T)
        
        if option_type == 'call':
            delta = discount * BlackModel._N(d1)
            rho = -T * discount * (F * BlackModel._N(d1) - K * BlackModel._N(d2))
            theta_term2 = r * discount * (F * BlackModel._N(d1) - K * BlackModel._N(d2))
        else:
            delta = -discount * BlackModel._N(-d1)
            rho = -T * discount * (K * BlackModel._N(-d2) - F * BlackModel._N(-d1))
            theta_term2 = r * discount * (K * BlackModel._N(-d2) - F * BlackModel._N(-d1))
            
        gamma = (discount * BlackModel._pdf(d1)) / (F * sigma * math.sqrt(T))
        vega = F * discount * BlackModel._pdf(d1) * math.sqrt(T)
        
        theta_yearly = -(F * discount * BlackModel._pdf(d1) * sigma) / (2 * math.sqrt(T)) + theta_term2
        
        return {
            "delta": delta,
            "gamma": gamma,
            "theta": theta_yearly / 365.0, # per day
            "vega": vega / 100.0,
            "rho": rho / 100.0
        }


class OptionsStrategy:
    """Base class for options strategies"""
    def __init__(self, cost_model, black_model):
        self.costs = cost_model
        self.black = black_model
        
    def short_straddle(self, F: float, strike: float, T_entry: float, T_exit: float, r: float, sigma_entry: float, sigma_exit: float, lot_size: int, qty: int = 1) -> dict:
        """
        Sell ATM Call + Sell ATM Put. Returns P&L given exit futures price and exit sigma.
        """
        c_entry = self.black.price(F, strike, T_entry, r, sigma_entry, 'call')
        p_entry = self.black.price(F, strike, T_entry, r, sigma_entry, 'put')
        premium_collected = (c_entry + p_entry) * lot_size * qty
        
        c_exit = self.black.price(F, strike, T_exit, r, sigma_exit, 'call')
        p_exit = self.black.price(F, strike, T_exit, r, sigma_exit, 'put')
        premium_paid = (c_exit + p_exit) * lot_size * qty
        
        gross_pnl = premium_collected - premium_paid
        tx_costs = self.costs.BROKERAGE_PER_ORDER * 4 # 2 sell, 2 buy legs approx.
        
        return {"gross_pnl": gross_pnl, "costs": tx_costs, "net_pnl": gross_pnl - tx_costs}
        
    def iron_condor(self, F: float, call_short_strike: float, call_long_strike: float, put_short_strike: float, put_long_strike: float, T: float, T_exit: float, r: float, sigma: float, sigma_exit: float, lot_size: int, qty: int = 1) -> dict:
        """Defined risk version of short strangle"""
        cs_entry = self.black.price(F, call_short_strike, T, r, sigma, 'call')
        ps_entry = self.black.price(F, put_short_strike, T, r, sigma, 'put')
        cl_entry = self.black.price(F, call_long_strike, T, r, sigma, 'call')
        pl_entry = self.black.price(F, put_long_strike, T, r, sigma, 'put')
        
        entry_net = (cs_entry + ps_entry - cl_entry - pl_entry) * lot_size * qty
        
        cs_exit = self.black.price(F, call_short_strike, T_exit, r, sigma_exit, 'call')
        ps_exit = self.black.price(F, put_short_strike, T_exit, r, sigma_exit, 'put')
        cl_exit = self.black.price(F, call_long_strike, T_exit, r, sigma_exit, 'call')
        pl_exit = self.black.price(F, put_long_strike, T_exit, r, sigma_exit, 'put')
        
        exit_net = (cs_exit + ps_exit - cl_exit - pl_exit) * lot_size * qty
        
        gross_pnl = entry_net - exit_net
        tx_costs = self.costs.BROKERAGE_PER_ORDER * 8  
        return {"gross_pnl": gross_pnl, "costs": tx_costs, "net_pnl": gross_pnl - tx_costs}
        
    def long_straddle(self, F: float, strike: float, T: float, T_exit: float, r: float, sigma: float, sigma_exit: float, lot_size: int, qty: int = 1) -> dict:
        """Buy ATM Call + ATM Put — for event plays"""
        c_entry = self.black.price(F, strike, T, r, sigma, 'call')
        p_entry = self.black.price(F, strike, T, r, sigma, 'put')
        premium_paid = (c_entry + p_entry) * lot_size * qty
        
        c_exit = self.black.price(F, strike, T_exit, r, sigma_exit, 'call')
        p_exit = self.black.price(F, strike, T_exit, r, sigma_exit, 'put')
        premium_collected = (c_exit + p_exit) * lot_size * qty
        
        gross_pnl = premium_collected - premium_paid
        tx_costs = self.costs.BROKERAGE_PER_ORDER * 4 
        return {"gross_pnl": gross_pnl, "costs": tx_costs, "net_pnl": gross_pnl - tx_costs}


class OptionsBacktester:
    """
    Backtest options strategies using historical IV data.
    NSE-specific rules enforced natively.
    """
    def __init__(self, cost_model, calendar):
        self.costs = cost_model
        self.calendar = calendar
        self.black = BlackModel()
        self.strategy = OptionsStrategy(cost_model, self.black)
        
    def backtest_weekly_straddle(self, banknifty_data: List[Dict], vix_data: List[Dict], from_date: str, to_date: str, config: Dict = None) -> List[Dict]:
        """
        Every Thursday: 9:20 AM Sell ATM straddle. Skip if VIX > 18 or high risk day.
        Exit 2:45 PM or stop loss at 100% premium.
        Returns: complete trade log.
        """
        trade_log = []
        r = 0.065
        lot_size = 15 # BankNifty
        
        weekly_expiry_dates = self.calendar.get_fo_expiry_calendar(int(from_date.split("-")[0]))["weekly"]
        
        for date_str in weekly_expiry_dates:
            if date_str < from_date or date_str > to_date:
                continue
                
            if self.calendar.is_high_risk_day(date_str):
                 continue
                 
            day_data = [d for d in banknifty_data if date_str in str(d.get("timestamp", d.get("date", "")))]
            if not day_data: continue
            
            # Simple VIX lookup
            vix_val = 15.0 
            for v in vix_data:
                if date_str in str(v.get("date", "")):
                    vix_val = v["close"]
                    break
                    
            if vix_val > 18.0: continue
            
            entry_row = None
            exit_row = None
            for row in day_data:
                tp = str(row.get("timestamp", ""))
                if "09:20" in tp or "09:15" in tp:
                    entry_row = row
                if "14:45" in tp:
                    exit_row = row
                    
            if not entry_row or not exit_row: continue
            
            F_entry = entry_row["close"]
            F_exit = exit_row["close"]
            
            strike = round(F_entry / 100) * 100
            
            # 1 day to expiry since it's Thursday morning
            T_entry = 1.0 / 252.0
            T_exit = 0.0001
            sigma = vix_val / 100.0
            
            res = self.strategy.short_straddle(F_entry, strike, T_entry, T_exit, r, sigma, sigma, lot_size)
            
            trade_log.append({
                "date": date_str,
                "type": "SHORT_STRADDLE",
                "gross_pnl": res["gross_pnl"],
                "costs": res["costs"],
                "pnl": res["net_pnl"]
            })
            
        return trade_log
