use rust_stock_harness::{benchmark_suite_json, run_benchmark_suite};

fn main() {
    let pretty = std::env::args().any(|arg| arg == "--pretty");
    let suite = run_benchmark_suite();
    println!("{}", benchmark_suite_json(&suite, pretty));
    if !suite.all_passed {
        std::process::exit(1);
    }
}
