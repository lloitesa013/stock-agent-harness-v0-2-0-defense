use std::collections::HashSet;
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    Keep,
    Reject,
    Iterate,
}

impl Verdict {
    pub fn as_str(self) -> &'static str {
        match self {
            Verdict::Keep => "KEEP",
            Verdict::Reject => "REJECT",
            Verdict::Iterate => "ITERATE",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct HarnessVerdict {
    pub verdict: Verdict,
    pub reasons: Vec<String>,
}

impl HarnessVerdict {
    pub fn keep(reason: impl Into<String>) -> Self {
        Self {
            verdict: Verdict::Keep,
            reasons: vec![reason.into()],
        }
    }

    pub fn reject(reasons: Vec<String>) -> Self {
        Self {
            verdict: Verdict::Reject,
            reasons,
        }
    }

    pub fn iterate(reason: impl Into<String>) -> Self {
        Self {
            verdict: Verdict::Iterate,
            reasons: vec![reason.into()],
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Bar {
    pub date: String,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
    pub adjusted_open: Option<f64>,
    pub adjusted_high: Option<f64>,
    pub adjusted_low: Option<f64>,
    pub adjusted_close: Option<f64>,
}

impl Bar {
    pub fn new(date: impl Into<String>, open: f64, high: f64, low: f64, close: f64, volume: f64) -> Self {
        Self {
            date: date.into(),
            open,
            high,
            low,
            close,
            volume,
            adjusted_open: None,
            adjusted_high: None,
            adjusted_low: None,
            adjusted_close: None,
        }
    }

    pub fn from_close(date: impl Into<String>, close: f64) -> Self {
        Self::new(date, close, close, close, close, 1_000.0)
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DataQualityConfig {
    pub min_bars: usize,
    pub max_zero_volume_ratio: f64,
    pub max_missing_business_days_per_gap: i64,
    pub max_open_gap_ratio: f64,
    pub max_close_jump_ratio: f64,
    pub max_adjusted_ohlc_ratio_spread: f64,
}

impl Default for DataQualityConfig {
    fn default() -> Self {
        Self {
            min_bars: 2,
            max_zero_volume_ratio: 0.0,
            max_missing_business_days_per_gap: 2,
            max_open_gap_ratio: 0.30,
            max_close_jump_ratio: 0.45,
            max_adjusted_ohlc_ratio_spread: 0.001,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct DataQualityIssue {
    pub date: String,
    pub severity: String,
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DataQualityMetrics {
    pub bar_count: usize,
    pub unique_dates: usize,
    pub error_count: usize,
    pub warning_count: usize,
    pub duplicate_dates: usize,
    pub non_monotonic_dates: usize,
    pub missing_business_days: i64,
    pub zero_volume_count: usize,
    pub zero_volume_ratio: f64,
    pub max_open_gap_ratio: f64,
    pub max_close_jump_ratio: f64,
    pub adjusted_ohlc_count: usize,
    pub partial_adjusted_ohlc_count: usize,
    pub max_adjusted_ohlc_ratio_spread: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DataQualityResult {
    pub verdict: HarnessVerdict,
    pub metrics: DataQualityMetrics,
    pub issues: Vec<DataQualityIssue>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BacktestConfig {
    pub initial_capital: f64,
    pub fee_bps: f64,
    pub slippage_bps: f64,
    pub max_allowed_drawdown: f64,
}

impl Default for BacktestConfig {
    fn default() -> Self {
        Self {
            initial_capital: 10_000.0,
            fee_bps: 1.0,
            slippage_bps: 2.0,
            max_allowed_drawdown: 0.20,
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct MovingAverageCashStrategy {
    pub window: usize,
}

impl MovingAverageCashStrategy {
    pub fn new(window: usize) -> Self {
        Self { window }
    }

    pub fn target_exposure(&self, bars: &[Bar], signal_index: usize) -> Option<f64> {
        if self.window == 0 || signal_index + 1 < self.window {
            return None;
        }
        let start = signal_index + 1 - self.window;
        let sum: f64 = bars[start..=signal_index].iter().map(|bar| bar.close).sum();
        let sma = sum / self.window as f64;
        if bars[signal_index].close > sma {
            Some(1.0)
        } else {
            Some(0.0)
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct EquityPoint {
    pub date: String,
    pub equity: f64,
    pub benchmark_equity: f64,
    pub drawdown: f64,
    pub benchmark_drawdown: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Trade {
    pub date: String,
    pub action: String,
    pub price: f64,
    pub shares: f64,
    pub gross_value: f64,
    pub fee: f64,
    pub target_exposure: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct OrderIntent {
    pub date: String,
    pub action: String,
    pub target_exposure: f64,
    pub current_exposure: f64,
    pub desired_shares: f64,
    pub estimated_price: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BacktestMetrics {
    pub total_return: f64,
    pub benchmark_total_return: f64,
    pub final_equity: f64,
    pub max_drawdown: f64,
    pub benchmark_max_drawdown: f64,
    pub exposure_ratio: f64,
    pub turnover: f64,
    pub trade_count: usize,
    pub order_intent_count: usize,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BacktestResult {
    pub verdict: HarnessVerdict,
    pub metrics: BacktestMetrics,
    pub equity_curve: Vec<EquityPoint>,
    pub trades: Vec<Trade>,
    pub order_intents: Vec<OrderIntent>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BenchmarkCase {
    pub name: String,
    pub prices: Vec<f64>,
    pub window: usize,
    pub max_allowed_drawdown: f64,
    pub expected_verdict: Verdict,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BenchmarkCaseResult {
    pub case: BenchmarkCase,
    pub actual_verdict: Verdict,
    pub passed: bool,
    pub total_return: f64,
    pub benchmark_total_return: f64,
    pub max_drawdown: f64,
    pub benchmark_max_drawdown: f64,
    pub trade_count: usize,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BenchmarkSuiteResult {
    pub benchmark: String,
    pub all_passed: bool,
    pub cases: Vec<BenchmarkCaseResult>,
    pub data_quality: DataQualityResult,
}

pub fn load_ohlcv_csv(path: impl AsRef<Path>) -> Result<Vec<Bar>, String> {
    let text = fs::read_to_string(path.as_ref()).map_err(|err| err.to_string())?;
    parse_ohlcv_csv(&text)
}

pub fn parse_ohlcv_csv(text: &str) -> Result<Vec<Bar>, String> {
    let mut lines = text.lines();
    let header_line = lines.next().ok_or_else(|| "csv is empty".to_string())?;
    let headers: Vec<String> = header_line
        .split(',')
        .map(normalize_header)
        .collect();

    let date_idx = required_column(&headers, &["date"])?;
    let open_idx = required_column(&headers, &["open"])?;
    let high_idx = required_column(&headers, &["high"])?;
    let low_idx = required_column(&headers, &["low"])?;
    let close_idx = required_column(&headers, &["close"])?;
    let volume_idx = required_column(&headers, &["volume"])?;
    let adjusted_open_idx = optional_column(&headers, &["adjusted_open", "adj_open"]);
    let adjusted_high_idx = optional_column(&headers, &["adjusted_high", "adj_high"]);
    let adjusted_low_idx = optional_column(&headers, &["adjusted_low", "adj_low"]);
    let adjusted_close_idx = optional_column(&headers, &["adjusted_close", "adj_close", "adjclose"]);

    let mut bars = Vec::new();
    for (line_number, line) in lines.enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let fields: Vec<&str> = line.split(',').map(str::trim).collect();
        let get = |idx: usize| -> Result<&str, String> {
            fields
                .get(idx)
                .copied()
                .ok_or_else(|| format!("row {} is missing column {}", line_number + 2, idx))
        };
        let parse_num = |idx: usize, name: &str| -> Result<f64, String> {
            get(idx)?
                .parse::<f64>()
                .map_err(|_| format!("row {} has invalid {}", line_number + 2, name))
        };
        let parse_optional_num = |idx: Option<usize>, name: &str| -> Result<Option<f64>, String> {
            match idx {
                Some(column) => {
                    let value = get(column)?;
                    if value.is_empty() {
                        Ok(None)
                    } else {
                        value
                            .parse::<f64>()
                            .map(Some)
                            .map_err(|_| format!("row {} has invalid {}", line_number + 2, name))
                    }
                }
                None => Ok(None),
            }
        };

        bars.push(Bar {
            date: get(date_idx)?.to_string(),
            open: parse_num(open_idx, "open")?,
            high: parse_num(high_idx, "high")?,
            low: parse_num(low_idx, "low")?,
            close: parse_num(close_idx, "close")?,
            volume: parse_num(volume_idx, "volume")?,
            adjusted_open: parse_optional_num(adjusted_open_idx, "adjusted_open")?,
            adjusted_high: parse_optional_num(adjusted_high_idx, "adjusted_high")?,
            adjusted_low: parse_optional_num(adjusted_low_idx, "adjusted_low")?,
            adjusted_close: parse_optional_num(adjusted_close_idx, "adjusted_close")?,
        });
    }

    Ok(bars)
}

pub fn run_data_quality_gate(bars: &[Bar], config: &DataQualityConfig) -> DataQualityResult {
    let mut issues = Vec::new();
    let mut seen_dates = HashSet::new();
    let mut duplicate_dates = 0usize;
    let mut non_monotonic_dates = 0usize;
    let mut missing_business_days = 0i64;
    let mut zero_volume_count = 0usize;
    let mut max_open_gap_ratio = 0.0f64;
    let mut max_close_jump_ratio = 0.0f64;
    let mut adjusted_ohlc_count = 0usize;
    let mut partial_adjusted_ohlc_count = 0usize;
    let mut max_adjusted_ohlc_ratio_spread = 0.0f64;
    let mut previous_day: Option<i64> = None;
    let mut previous_close: Option<f64> = None;

    if bars.len() < config.min_bars {
        issues.push(issue("", "error", "too_few_bars", "not enough bars for verification"));
    }

    for bar in bars {
        if !seen_dates.insert(bar.date.clone()) {
            duplicate_dates += 1;
            issues.push(issue(&bar.date, "error", "duplicate_date", "duplicate date"));
        }

        if !bar.open.is_finite()
            || !bar.high.is_finite()
            || !bar.low.is_finite()
            || !bar.close.is_finite()
            || !bar.volume.is_finite()
            || bar.open <= 0.0
            || bar.high <= 0.0
            || bar.low <= 0.0
            || bar.close <= 0.0
            || bar.volume < 0.0
        {
            issues.push(issue(&bar.date, "error", "invalid_ohlcv", "OHLCV values must be finite and non-negative"));
        }

        if bar.high < bar.open.max(bar.close).max(bar.low) || bar.low > bar.open.min(bar.close).min(bar.high) {
            issues.push(issue(&bar.date, "error", "invalid_high_low", "high/low do not contain open/close"));
        }

        if bar.volume == 0.0 {
            zero_volume_count += 1;
        }

        match parse_iso_day(&bar.date) {
            Some(day) => {
                if let Some(prev_day) = previous_day {
                    if day <= prev_day {
                        non_monotonic_dates += 1;
                        issues.push(issue(&bar.date, "error", "non_monotonic_date", "dates must be strictly increasing"));
                    } else {
                        let missing = business_days_between_exclusive(prev_day, day);
                        missing_business_days += missing;
                        if missing > config.max_missing_business_days_per_gap {
                            issues.push(issue(&bar.date, "error", "missing_business_days", "too many missing business days"));
                        }
                    }
                }
                previous_day = Some(day);
            }
            None => {
                issues.push(issue(&bar.date, "warning", "non_iso_date", "calendar checks skipped for non-ISO date"));
            }
        }

        if let Some(prev_close) = previous_close {
            if prev_close > 0.0 {
                let open_gap = ((bar.open / prev_close) - 1.0).abs();
                let close_jump = ((bar.close / prev_close) - 1.0).abs();
                max_open_gap_ratio = max_open_gap_ratio.max(open_gap);
                max_close_jump_ratio = max_close_jump_ratio.max(close_jump);
                if open_gap > config.max_open_gap_ratio {
                    issues.push(issue(&bar.date, "error", "open_gap_too_large", "open gap exceeds configured threshold"));
                }
                if close_jump > config.max_close_jump_ratio {
                    issues.push(issue(&bar.date, "error", "close_jump_too_large", "close jump exceeds configured threshold"));
                }
            }
        }
        previous_close = Some(bar.close);

        let adjusted = [
            bar.adjusted_open,
            bar.adjusted_high,
            bar.adjusted_low,
            bar.adjusted_close,
        ];
        let adjusted_count = adjusted.iter().filter(|value| value.is_some()).count();
        if adjusted_count == 4 {
            adjusted_ohlc_count += 1;
            let ratios = [
                bar.adjusted_open.unwrap() / bar.open,
                bar.adjusted_high.unwrap() / bar.high,
                bar.adjusted_low.unwrap() / bar.low,
                bar.adjusted_close.unwrap() / bar.close,
            ];
            if ratios.iter().all(|ratio| ratio.is_finite() && *ratio > 0.0) {
                let min_ratio = ratios.iter().fold(f64::INFINITY, |acc, value| acc.min(*value));
                let max_ratio = ratios.iter().fold(0.0f64, |acc, value| acc.max(*value));
                let spread = max_ratio - min_ratio;
                max_adjusted_ohlc_ratio_spread = max_adjusted_ohlc_ratio_spread.max(spread);
                if spread > config.max_adjusted_ohlc_ratio_spread {
                    issues.push(issue(&bar.date, "error", "adjusted_ohlc_ratio_spread", "adjusted OHLC ratios are inconsistent"));
                }
            } else {
                issues.push(issue(&bar.date, "error", "invalid_adjusted_ohlc", "adjusted OHLC ratios must be finite and positive"));
            }
        } else if adjusted_count > 0 {
            partial_adjusted_ohlc_count += 1;
            issues.push(issue(&bar.date, "error", "partial_adjusted_ohlc", "adjusted OHLC fields must be complete"));
        }
    }

    let zero_volume_ratio = if bars.is_empty() {
        0.0
    } else {
        zero_volume_count as f64 / bars.len() as f64
    };
    if zero_volume_ratio > config.max_zero_volume_ratio {
        issues.push(issue("", "error", "zero_volume_ratio_too_high", "zero-volume ratio exceeds configured threshold"));
    }

    let error_count = issues.iter().filter(|item| item.severity == "error").count();
    let warning_count = issues.iter().filter(|item| item.severity == "warning").count();
    let verdict = if error_count == 0 {
        HarnessVerdict::keep("data_quality_clean")
    } else {
        HarnessVerdict::reject(vec!["data_quality_errors".to_string()])
    };

    DataQualityResult {
        verdict,
        metrics: DataQualityMetrics {
            bar_count: bars.len(),
            unique_dates: seen_dates.len(),
            error_count,
            warning_count,
            duplicate_dates,
            non_monotonic_dates,
            missing_business_days,
            zero_volume_count,
            zero_volume_ratio,
            max_open_gap_ratio,
            max_close_jump_ratio,
            adjusted_ohlc_count,
            partial_adjusted_ohlc_count,
            max_adjusted_ohlc_ratio_spread,
        },
        issues,
    }
}

pub fn run_backtest(
    bars: &[Bar],
    strategy: &MovingAverageCashStrategy,
    config: &BacktestConfig,
) -> BacktestResult {
    if strategy.window == 0 || bars.len() <= strategy.window {
        return empty_backtest_result(HarnessVerdict::iterate("not_enough_bars_for_strategy"));
    }
    if config.initial_capital <= 0.0 || config.fee_bps < 0.0 || config.slippage_bps < 0.0 {
        return empty_backtest_result(HarnessVerdict::reject(vec!["invalid_backtest_config".to_string()]));
    }

    let mut cash = config.initial_capital;
    let mut shares = 0.0f64;
    let mut current_target_exposure = 0.0f64;
    let mut equity_curve = Vec::with_capacity(bars.len());
    let mut trades = Vec::new();
    let mut order_intents = Vec::new();
    let mut exposure_days = 0usize;
    let mut turnover = 0.0f64;
    let mut peak = config.initial_capital;
    let mut benchmark_peak = config.initial_capital;
    let first_close = bars[0].close;

    for index in 0..bars.len() {
        let bar = &bars[index];
        if index > 0 {
            if let Some(target_exposure) = strategy.target_exposure(bars, index - 1) {
                let estimated_price = bar.open;
                let open_equity = cash + shares * estimated_price;
                if open_equity > 0.0 && (target_exposure - current_target_exposure).abs() > 1e-9 {
                    let current_exposure = (shares * estimated_price) / open_equity;
                    let desired_shares = (open_equity * target_exposure) / estimated_price;
                    let delta_shares = desired_shares - shares;
                    if delta_shares.abs() > 1e-9 {
                        let action = if delta_shares > 0.0 { "buy" } else { "sell" };
                        order_intents.push(OrderIntent {
                            date: bar.date.clone(),
                            action: action.to_string(),
                            target_exposure,
                            current_exposure,
                            desired_shares,
                            estimated_price,
                        });

                        let fill_price = if delta_shares > 0.0 {
                            estimated_price * (1.0 + config.slippage_bps / 10_000.0)
                        } else {
                            estimated_price * (1.0 - config.slippage_bps / 10_000.0)
                        };
                        let gross_value = delta_shares.abs() * fill_price;
                        let fee = gross_value * config.fee_bps / 10_000.0;
                        if delta_shares > 0.0 {
                            cash -= gross_value + fee;
                        } else {
                            cash += gross_value - fee;
                        }
                        shares += delta_shares;
                        turnover += gross_value / open_equity;
                        trades.push(Trade {
                            date: bar.date.clone(),
                            action: action.to_string(),
                            price: fill_price,
                            shares: delta_shares.abs(),
                            gross_value,
                            fee,
                            target_exposure,
                        });
                    }
                    current_target_exposure = target_exposure;
                }
            }
        }

        if shares.abs() > 1e-9 {
            exposure_days += 1;
        }
        let equity = cash + shares * bar.close;
        peak = peak.max(equity);
        let drawdown = if peak > 0.0 { 1.0 - equity / peak } else { 0.0 };
        let benchmark_equity = if first_close > 0.0 {
            config.initial_capital * bar.close / first_close
        } else {
            config.initial_capital
        };
        benchmark_peak = benchmark_peak.max(benchmark_equity);
        let benchmark_drawdown = if benchmark_peak > 0.0 {
            1.0 - benchmark_equity / benchmark_peak
        } else {
            0.0
        };
        equity_curve.push(EquityPoint {
            date: bar.date.clone(),
            equity,
            benchmark_equity,
            drawdown,
            benchmark_drawdown,
        });
    }

    let final_equity = equity_curve
        .last()
        .map(|point| point.equity)
        .unwrap_or(config.initial_capital);
    let max_drawdown = equity_curve
        .iter()
        .map(|point| point.drawdown)
        .fold(0.0f64, f64::max);
    let benchmark_max_drawdown = equity_curve
        .iter()
        .map(|point| point.benchmark_drawdown)
        .fold(0.0f64, f64::max);
    let benchmark_total_return = if first_close > 0.0 {
        bars.last().map(|bar| bar.close / first_close - 1.0).unwrap_or(0.0)
    } else {
        0.0
    };
    let total_return = final_equity / config.initial_capital - 1.0;

    let mut reasons = Vec::new();
    if max_drawdown > config.max_allowed_drawdown {
        reasons.push(format!(
            "max_drawdown_breached: {:.6} > {:.6}",
            max_drawdown, config.max_allowed_drawdown
        ));
    }
    if max_drawdown >= benchmark_max_drawdown {
        reasons.push(format!(
            "downside_protection_failed: {:.6} >= benchmark {:.6}",
            max_drawdown, benchmark_max_drawdown
        ));
    }

    let verdict = if reasons.is_empty() {
        HarnessVerdict {
            verdict: Verdict::Keep,
            reasons: vec![
                "drawdown_within_limit".to_string(),
                "max_drawdown_better_than_benchmark".to_string(),
            ],
        }
    } else {
        HarnessVerdict::reject(reasons)
    };

    BacktestResult {
        verdict,
        metrics: BacktestMetrics {
            total_return,
            benchmark_total_return,
            final_equity,
            max_drawdown,
            benchmark_max_drawdown,
            exposure_ratio: exposure_days as f64 / bars.len() as f64,
            turnover,
            trade_count: trades.len(),
            order_intent_count: order_intents.len(),
        },
        equity_curve,
        trades,
        order_intents,
    }
}

pub fn benchmark_cases() -> Vec<BenchmarkCase> {
    vec![
        BenchmarkCase {
            name: "steady_up".to_string(),
            prices: vec![100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            window: 3,
            max_allowed_drawdown: 0.20,
            expected_verdict: Verdict::Reject,
        },
        BenchmarkCase {
            name: "crash".to_string(),
            prices: vec![100.0, 105.0, 110.0, 115.0, 120.0, 119.0, 118.0, 117.0, 90.0, 80.0, 75.0],
            window: 3,
            max_allowed_drawdown: 0.20,
            expected_verdict: Verdict::Keep,
        },
        BenchmarkCase {
            name: "whipsaw".to_string(),
            prices: vec![100.0, 103.0, 99.0, 104.0, 98.0, 105.0, 97.0, 106.0],
            window: 3,
            max_allowed_drawdown: 0.20,
            expected_verdict: Verdict::Keep,
        },
        BenchmarkCase {
            name: "flat_then_spike".to_string(),
            prices: vec![100.0, 100.0, 100.0, 200.0, 200.0],
            window: 3,
            max_allowed_drawdown: 0.20,
            expected_verdict: Verdict::Reject,
        },
    ]
}

pub fn run_benchmark_suite() -> BenchmarkSuiteResult {
    let cases = benchmark_cases();
    let mut results = Vec::new();
    for case in cases {
        let bars = prices_to_bars(&case.prices);
        let result = run_backtest(
            &bars,
            &MovingAverageCashStrategy::new(case.window),
            &BacktestConfig {
                max_allowed_drawdown: case.max_allowed_drawdown,
                ..BacktestConfig::default()
            },
        );
        let actual_verdict = result.verdict.verdict;
        results.push(BenchmarkCaseResult {
            passed: actual_verdict == case.expected_verdict,
            total_return: result.metrics.total_return,
            benchmark_total_return: result.metrics.benchmark_total_return,
            max_drawdown: result.metrics.max_drawdown,
            benchmark_max_drawdown: result.metrics.benchmark_max_drawdown,
            trade_count: result.metrics.trade_count,
            reasons: result.verdict.reasons,
            actual_verdict,
            case,
        });
    }

    let data_quality_bars = prices_to_bars(&[100.0, 105.0, 110.0, 115.0, 120.0, 119.0, 118.0, 117.0, 90.0, 80.0, 75.0]);
    let data_quality = run_data_quality_gate(&data_quality_bars, &DataQualityConfig::default());
    let all_passed = results.iter().all(|result| result.passed)
        && data_quality.verdict.verdict == Verdict::Keep;

    BenchmarkSuiteResult {
        benchmark: "rust_stock_harness_v0".to_string(),
        all_passed,
        cases: results,
        data_quality,
    }
}

pub fn benchmark_suite_json(suite: &BenchmarkSuiteResult, pretty: bool) -> String {
    if pretty {
        benchmark_suite_json_pretty(suite)
    } else {
        benchmark_suite_json_compact(suite)
    }
}

fn benchmark_suite_json_compact(suite: &BenchmarkSuiteResult) -> String {
    let cases = suite
        .cases
        .iter()
        .map(case_json_compact)
        .collect::<Vec<_>>()
        .join(",");
    format!(
        "{{\"benchmark\":\"{}\",\"all_passed\":{},\"data_quality\":{},\"cases\":[{}]}}",
        json_escape(&suite.benchmark),
        suite.all_passed,
        data_quality_json_compact(&suite.data_quality),
        cases
    )
}

fn benchmark_suite_json_pretty(suite: &BenchmarkSuiteResult) -> String {
    let mut out = String::new();
    out.push_str("{\n");
    out.push_str(&format!("  \"benchmark\": \"{}\",\n", json_escape(&suite.benchmark)));
    out.push_str(&format!("  \"all_passed\": {},\n", suite.all_passed));
    out.push_str(&format!("  \"data_quality\": {},\n", data_quality_json_compact(&suite.data_quality)));
    out.push_str("  \"cases\": [\n");
    for (index, case) in suite.cases.iter().enumerate() {
        out.push_str("    ");
        out.push_str(&case_json_compact(case));
        if index + 1 != suite.cases.len() {
            out.push(',');
        }
        out.push('\n');
    }
    out.push_str("  ]\n");
    out.push('}');
    out
}

fn case_json_compact(result: &BenchmarkCaseResult) -> String {
    format!(
        "{{\"name\":\"{}\",\"expected_verdict\":\"{}\",\"actual_verdict\":\"{}\",\"passed\":{},\"total_return\":{},\"benchmark_total_return\":{},\"max_drawdown\":{},\"benchmark_max_drawdown\":{},\"trade_count\":{},\"reasons\":{}}}",
        json_escape(&result.case.name),
        result.case.expected_verdict.as_str(),
        result.actual_verdict.as_str(),
        result.passed,
        finite_json_number(result.total_return),
        finite_json_number(result.benchmark_total_return),
        finite_json_number(result.max_drawdown),
        finite_json_number(result.benchmark_max_drawdown),
        result.trade_count,
        json_string_array(&result.reasons)
    )
}

fn data_quality_json_compact(result: &DataQualityResult) -> String {
    format!(
        "{{\"verdict\":\"{}\",\"error_count\":{},\"warning_count\":{},\"bar_count\":{},\"duplicate_dates\":{},\"missing_business_days\":{},\"zero_volume_count\":{},\"max_open_gap_ratio\":{},\"max_close_jump_ratio\":{},\"adjusted_ohlc_count\":{},\"partial_adjusted_ohlc_count\":{}}}",
        result.verdict.verdict.as_str(),
        result.metrics.error_count,
        result.metrics.warning_count,
        result.metrics.bar_count,
        result.metrics.duplicate_dates,
        result.metrics.missing_business_days,
        result.metrics.zero_volume_count,
        finite_json_number(result.metrics.max_open_gap_ratio),
        finite_json_number(result.metrics.max_close_jump_ratio),
        result.metrics.adjusted_ohlc_count,
        result.metrics.partial_adjusted_ohlc_count
    )
}

fn prices_to_bars(prices: &[f64]) -> Vec<Bar> {
    prices
        .iter()
        .enumerate()
        .map(|(index, price)| Bar::from_close(format!("2020-01-{:02}", index + 1), *price))
        .collect()
}

fn empty_backtest_result(verdict: HarnessVerdict) -> BacktestResult {
    BacktestResult {
        verdict,
        metrics: BacktestMetrics {
            total_return: 0.0,
            benchmark_total_return: 0.0,
            final_equity: 0.0,
            max_drawdown: 0.0,
            benchmark_max_drawdown: 0.0,
            exposure_ratio: 0.0,
            turnover: 0.0,
            trade_count: 0,
            order_intent_count: 0,
        },
        equity_curve: Vec::new(),
        trades: Vec::new(),
        order_intents: Vec::new(),
    }
}

fn issue(date: &str, severity: &str, code: &str, message: &str) -> DataQualityIssue {
    DataQualityIssue {
        date: date.to_string(),
        severity: severity.to_string(),
        code: code.to_string(),
        message: message.to_string(),
    }
}

fn normalize_header(value: &str) -> String {
    value.trim().to_ascii_lowercase().replace(' ', "_")
}

fn required_column(headers: &[String], aliases: &[&str]) -> Result<usize, String> {
    optional_column(headers, aliases).ok_or_else(|| format!("missing required column: {}", aliases[0]))
}

fn optional_column(headers: &[String], aliases: &[&str]) -> Option<usize> {
    headers
        .iter()
        .position(|header| aliases.iter().any(|alias| header == alias))
}

fn parse_iso_day(value: &str) -> Option<i64> {
    let parts: Vec<&str> = value.split('-').collect();
    if parts.len() != 3 {
        return None;
    }
    let year = parts[0].parse::<i32>().ok()?;
    let month = parts[1].parse::<u32>().ok()?;
    let day = parts[2].parse::<u32>().ok()?;
    if !(1..=12).contains(&month) || !(1..=31).contains(&day) {
        return None;
    }
    Some(days_from_civil(year, month, day))
}

fn days_from_civil(year: i32, month: u32, day: u32) -> i64 {
    let adjusted_year = year - if month <= 2 { 1 } else { 0 };
    let era = if adjusted_year >= 0 {
        adjusted_year
    } else {
        adjusted_year - 399
    } / 400;
    let year_of_era = adjusted_year - era * 400;
    let month_i = month as i32;
    let day_i = day as i32;
    let day_of_year = (153 * (month_i + if month_i > 2 { -3 } else { 9 }) + 2) / 5 + day_i - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    (era * 146_097 + day_of_era - 719_468) as i64
}

fn business_days_between_exclusive(start_day: i64, end_day: i64) -> i64 {
    let mut count = 0;
    let mut day = start_day + 1;
    while day < end_day {
        if weekday_monday_zero(day) < 5 {
            count += 1;
        }
        day += 1;
    }
    count
}

fn weekday_monday_zero(day_since_epoch: i64) -> i64 {
    (day_since_epoch + 3).rem_euclid(7)
}

fn json_escape(value: &str) -> String {
    let mut escaped = String::new();
    for ch in value.chars() {
        match ch {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            ch if ch.is_control() => escaped.push_str(&format!("\\u{:04x}", ch as u32)),
            ch => escaped.push(ch),
        }
    }
    escaped
}

fn json_string_array(values: &[String]) -> String {
    let values = values
        .iter()
        .map(|value| format!("\"{}\"", json_escape(value)))
        .collect::<Vec<_>>()
        .join(",");
    format!("[{}]", values)
}

fn finite_json_number(value: f64) -> String {
    if value.is_finite() {
        format!("{:.12}", value)
    } else {
        "null".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn bars(prices: &[f64]) -> Vec<Bar> {
        prices_to_bars(prices)
    }

    #[test]
    fn csv_loader_reads_ohlcv_rows() {
        let path = std::env::temp_dir().join(format!(
            "rust_stock_harness_test_{}_{}.csv",
            std::process::id(),
            1
        ));
        {
            let mut file = fs::File::create(&path).expect("create temp csv");
            writeln!(file, "date,open,high,low,close,volume").unwrap();
            writeln!(file, "2020-01-01,100,101,99,100,1000").unwrap();
            writeln!(file, "2020-01-02,101,102,100,101,1000").unwrap();
        }
        let loaded = load_ohlcv_csv(&path).expect("load csv");
        let _ = fs::remove_file(&path);
        assert_eq!(loaded.len(), 2);
        assert_eq!(loaded[0].date, "2020-01-01");
        assert_eq!(loaded[1].close, 101.0);
    }

    #[test]
    fn data_quality_rejects_invalid_high_low() {
        let broken = vec![Bar::new("2020-01-01", 100.0, 99.0, 98.0, 100.0, 1000.0)];
        let result = run_data_quality_gate(&broken, &DataQualityConfig::default());
        assert_eq!(result.verdict.verdict, Verdict::Reject);
        assert!(result.issues.iter().any(|issue| issue.code == "invalid_high_low"));
    }

    #[test]
    fn data_quality_accepts_adjusted_ohlc_with_stable_ratio() {
        let mut first = Bar::new("2020-01-01", 100.0, 102.0, 99.0, 101.0, 1000.0);
        first.adjusted_open = Some(50.0);
        first.adjusted_high = Some(51.0);
        first.adjusted_low = Some(49.5);
        first.adjusted_close = Some(50.5);
        let mut second = Bar::new("2020-01-02", 102.0, 104.0, 101.0, 103.0, 1000.0);
        second.adjusted_open = Some(51.0);
        second.adjusted_high = Some(52.0);
        second.adjusted_low = Some(50.5);
        second.adjusted_close = Some(51.5);
        let result = run_data_quality_gate(&[first, second], &DataQualityConfig::default());
        assert_eq!(result.verdict.verdict, Verdict::Keep);
        assert_eq!(result.metrics.adjusted_ohlc_count, 2);
    }

    #[test]
    fn backtest_rejects_steady_up_because_benchmark_has_zero_drawdown() {
        let result = run_backtest(
            &bars(&[100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0]),
            &MovingAverageCashStrategy::new(3),
            &BacktestConfig::default(),
        );
        assert_eq!(result.verdict.verdict, Verdict::Reject);
        assert!(result.metrics.max_drawdown >= result.metrics.benchmark_max_drawdown);
    }

    #[test]
    fn backtest_keeps_crash_case_when_cash_exit_protects_downside() {
        let result = run_backtest(
            &bars(&[100.0, 105.0, 110.0, 115.0, 120.0, 119.0, 118.0, 117.0, 90.0, 80.0, 75.0]),
            &MovingAverageCashStrategy::new(3),
            &BacktestConfig::default(),
        );
        assert_eq!(result.verdict.verdict, Verdict::Keep);
        assert!(result.metrics.max_drawdown < result.metrics.benchmark_max_drawdown);
        assert!(!result.order_intents.is_empty());
    }

    #[test]
    fn benchmark_suite_passes_expected_regime_verdicts() {
        let suite = run_benchmark_suite();
        assert!(suite.all_passed);
        assert_eq!(suite.cases.len(), 4);
        assert!(suite.cases.iter().all(|case| case.passed));
        assert_eq!(suite.data_quality.verdict.verdict, Verdict::Keep);
    }

    #[test]
    fn benchmark_json_includes_claim_relevant_fields() {
        let suite = run_benchmark_suite();
        let json = benchmark_suite_json(&suite, false);
        assert!(json.contains("\"benchmark\":\"rust_stock_harness_v0\""));
        assert!(json.contains("\"all_passed\":true"));
        assert!(json.contains("\"trade_count\""));
        assert!(json.contains("\"data_quality\""));
    }
}
