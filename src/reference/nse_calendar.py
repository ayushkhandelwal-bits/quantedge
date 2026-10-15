from datetime import datetime, timedelta

class NSECalendar:
    """
    NSE trading calendar with all India-specific dates.
    Critical for correct T (time to expiry) calculation.
    """
    
    MARKET_HOLIDAYS_2024 = [
        "2024-01-26",  # Republic Day
        "2024-03-25",  # Holi
        "2024-04-14",  # Dr. Ambedkar Jayanti
        "2024-04-17",  # Ram Navami
        "2024-04-21",  # Mahavir Jayanti
        "2024-05-23",  # Buddha Purnima
        "2024-06-17",  # Bakri Id
        "2024-07-17",  # Muharram
        "2024-08-15",  # Independence Day
        "2024-10-02",  # Mahatma Gandhi Jayanti
        "2024-10-24",  # Dussehra
        "2024-11-01",  # Diwali (Laxmi Puja)
        "2024-11-15",  # Gurunanak Jayanti
        "2024-12-25",  # Christmas
    ]
    
    RBI_POLICY_DATES_2024 = [
        "2024-02-08", "2024-04-05", "2024-06-07",
        "2024-08-08", "2024-10-09", "2024-12-06"
    ]
    
    @classmethod
    def _parse(cls, d: str) -> datetime:
        d_str = d.split(" ")[0] if " " in d else d
        return datetime.strptime(d_str, "%Y-%m-%d")
        
    def is_trading_day(self, date: str) -> bool:
        """Returns False for weekends and NSE holidays"""
        dt = self._parse(date)
        if dt.weekday() >= 5: # 5=Sat, 6=Sun
            return False
        if dt.strftime("%Y-%m-%d") in self.MARKET_HOLIDAYS_2024:
            return False
        return True
    
    def next_trading_day(self, date: str) -> str:
        dt = self._parse(date) + timedelta(days=1)
        while not self.is_trading_day(dt.strftime("%Y-%m-%d")):
            dt += timedelta(days=1)
        return dt.strftime("%Y-%m-%d")
    
    def days_to_expiry(self, from_date: str, expiry_date: str) -> int:
        """Count only trading days - critical for theta calculation"""
        current_dt = self._parse(from_date)
        exp_dt = self._parse(expiry_date)
        
        days_count = 0
        while current_dt < exp_dt:
            if self.is_trading_day(current_dt.strftime("%Y-%m-%d")):
                days_count += 1
            current_dt += timedelta(days=1)
        return days_count
    
    def get_weekly_expiry(self, date: str) -> str:
        """Returns next Thursday expiry date"""
        dt = self._parse(date)
        # Thursday is weekday 3
        days_ahead = 3 - dt.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target = dt + timedelta(days=days_ahead)
        
        # If Thursday is a holiday, NSE shifts expiry to previous trading day
        t_str = target.strftime("%Y-%m-%d")
        while not self.is_trading_day(t_str):
            target -= timedelta(days=1)
            t_str = target.strftime("%Y-%m-%d")
            
        return t_str
    
    def get_monthly_expiry(self, year: int, month: int) -> str:
        """Returns last Thursday of the month"""
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
            
        last_day = next_month - timedelta(days=1)
        days_back = (last_day.weekday() - 3) % 7
        target = last_day - timedelta(days=days_back)
        
        t_str = target.strftime("%Y-%m-%d")
        while not self.is_trading_day(t_str):
            target -= timedelta(days=1)
            t_str = target.strftime("%Y-%m-%d")
            
        return t_str
    
    def is_rbi_day(self, date: str) -> bool:
        """True on RBI policy announcement days"""
        dt = self._parse(date)
        return dt.strftime("%Y-%m-%d") in self.RBI_POLICY_DATES_2024
    
    def is_high_risk_day(self, date: str) -> bool:
        """
        True on: RBI policy days, Budget day (Feb 1), Election results, etc.
        """
        dt = self._parse(date)
        d_str = dt.strftime("%Y-%m-%d")
        
        if self.is_rbi_day(d_str):
            return True
            
        # Approximation for Budget day
        if dt.month == 2 and dt.day == 1:
            return True
            
        # Election Result day 2024
        if d_str == "2024-06-04":
            return True
            
        return False
    
    def get_fo_expiry_calendar(self, year: int) -> dict:
        """
        Returns dict of all F&O expiry dates for the year.
        Weekly: every Thursday (or prior)
        Monthly: last Thursday
        Quarterly: March, June, September, December last Thursday
        """
        cal = {"weekly": [], "monthly": [], "quarterly": []}
        
        for m in range(1, 13):
            cal["monthly"].append(self.get_monthly_expiry(year, m))
            
        cal["quarterly"] = [cal["monthly"][2], cal["monthly"][5], cal["monthly"][8], cal["monthly"][11]]
        
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        
        curr = start_date
        while curr <= end_date:
            if curr.weekday() == 3: # Thursday
                d_str = curr.strftime("%Y-%m-%d")
                adjusted = d_str
                while not self.is_trading_day(adjusted):
                    parsed_adj = self._parse(adjusted) - timedelta(days=1)
                    adjusted = parsed_adj.strftime("%Y-%m-%d")
                if adjusted not in cal["weekly"]:
                    cal["weekly"].append(adjusted)
            curr += timedelta(days=1)
            
        return cal
