from typing import List, Dict, Callable, Tuple, Any

class WalkForwardValidator:
    """
    Prevents overfitting by testing on truly unseen data.
    
    Standard split: 70% in-sample (IS), 30% out-of-sample (OOS)
    Walk-forward: Roll the window forward in steps
    
    Example with 5 years of data, 1-year OOS:
        Window 1: Train 2018-2021, Test 2022
        Window 2: Train 2019-2022, Test 2023
        Window 3: Train 2020-2023, Test 2024
    """
    
    def __init__(self, data: List[Dict], strategy_fn: Callable, param_grid: List[Dict], train_pct: float = 0.7, n_splits: int = 5):
        self.data = data
        self.strategy_fn = strategy_fn
        self.param_grid = param_grid
        self.train_pct = train_pct
        self.n_splits = n_splits
        
    def _optimize(self, train_data: List[Dict]) -> Tuple[Dict, float]:
        """
        Optimizes parameters on the training data using raw Sharpe Ratio.
        """
        from src.backtester import run_backtest
        from src.metrics import sharpe_ratio
        
        best_sharpe = -float('inf')
        best_params = None
        
        for params in self.param_grid:
            signals = self.strategy_fn(train_data, params)
            history, _ = run_backtest(train_data, signals, {"initial_capital": 10000.0, "position_size": 10000.0})
            
            # Extract equity curve
            returns_curve = [h["value"] for h in history]
            sharpe = sharpe_ratio(returns_curve)
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params
                
        return best_params, best_sharpe
    
    def run(self) -> Dict[str, Any]:
        """
        For each split:
            1. Optimize params on training data
            2. Test BEST params on unseen test data
            3. Record OOS metrics
        Returns: dict with IS metrics, OOS metrics, degradation ratio
        """
        from src.backtester import run_backtest
        from src.metrics import sharpe_ratio
        
        n = len(self.data)
        
        # Determine total size for a single walk-forward block
        # If n_splits=5, we break the data into overlapping blocks or contiguous chunks.
        # Contiguous chunk mapping:
        # We start testing only after we have at least one train_size available.
        # Let's say test blocks are simple slices of size (n / (n_splits + 1))
        # and train blocks are size (train_pct of total block size).
        
        # Simpler approach matching prompt example:
        # If 5 years data, 1 year OOS. window rolls 1 year.
        test_size = n // (self.n_splits + 1)
        train_size = int((test_size * self.train_pct) / (1.0 - self.train_pct))
        # Ensure we do not exceed data boundaries
        if train_size > n - test_size:
            train_size = n - test_size

        splits = []
        is_sharpes = []
        oos_sharpes = []
        
        for i in range(self.n_splits):
            test_start = n - (self.n_splits - i) * test_size
            test_end = test_start + test_size
            train_start = max(0, test_start - train_size)
            
            train_data = self.data[train_start:test_start]
            test_data = self.data[test_start:test_end]
            
            if not train_data or not test_data:
                continue
                
            best_params, is_sharpe = self._optimize(train_data)
            
            # Test unseen data
            signals = self.strategy_fn(test_data, best_params)
            history, _ = run_backtest(test_data, signals, {"initial_capital": 10000.0, "position_size": 10000.0})
            
            returns_curve = [h["value"] for h in history]
            oos_sharpe = sharpe_ratio(returns_curve)
            
            degradation = self.degradation_ratio(is_sharpe, oos_sharpe)
            
            is_sharpes.append(is_sharpe)
            oos_sharpes.append(oos_sharpe)
            
            splits.append({
                "split": i + 1,
                "train_start": train_data[0].get("date", str(train_start)),
                "train_end": train_data[-1].get("date", str(test_start-1)),
                "test_start": test_data[0].get("date", str(test_start)),
                "test_end": test_data[-1].get("date", str(test_end-1)),
                "best_params": best_params,
                "is_sharpe": is_sharpe,
                "oos_sharpe": oos_sharpe,
                "degradation_ratio": degradation
            })
            
        overall_is = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0.0
        overall_oos = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0.0
        
        return {
            "splits": splits,
            "overall_is_sharpe": overall_is,
            "overall_oos_sharpe": overall_oos,
            "overall_degradation_ratio": self.degradation_ratio(overall_is, overall_oos)
        }
    
    def degradation_ratio(self, is_sharpe: float, oos_sharpe: float) -> float:
        """
        OOS Sharpe / IS Sharpe
        > 0.7: Good - strategy generalises
        0.5-0.7: Acceptable
        < 0.5: Overfit - do not trade
        """
        if is_sharpe <= 0:
            return 0.0
        return max(0.0, oos_sharpe / is_sharpe)


class PurgedKFoldCV:
    """
    De Prado's purged cross-validation for financial time series.
    Prevents leakage from overlapping labels.
    
    Standard k-fold is WRONG for time series - it leaks future data.
    This implementation:
        1. Creates k folds respecting time order
        2. Purges samples whose labels overlap with test set
        3. Adds embargo period after test set
    """
    
    def __init__(self, n_splits: int = 5, purge_pct: float = 0.01, embargo_pct: float = 0.01):
        self.n_splits = n_splits
        self.purge_pct = purge_pct
        self.embargo_pct = embargo_pct
        
    def split(self, X: List[Any], y: List[Any] = None) -> Tuple[List[int], List[int]]:
        """Yields (train_idx, test_idx) pairs"""
        n = len(X)
        split_size = n // self.n_splits
        purge_size = int(n * self.purge_pct)
        embargo_size = int(n * self.embargo_pct)
        
        for i in range(self.n_splits):
            test_start = i * split_size
            test_end = (i + 1) * split_size if i != self.n_splits - 1 else n
            
            test_idx = list(range(test_start, test_end))
            train_idx = []
            
            for j in range(n):
                # 2. Purge Phase (samples immediately before test start)
                if j < test_start - purge_size:
                    train_idx.append(j)
                # 3. Embargo Phase (samples immediately after test end)
                elif j >= test_end + embargo_size:
                    train_idx.append(j)
                    
            yield train_idx, test_idx
