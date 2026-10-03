use evas_kernel::{
    ir::{parse_request, Error},
    run_with_threads,
};
use std::io::{self, Read, Write};

fn main() {
    let mut input = String::new();
    let result = io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| Error::new("input_io", e.to_string()))
        .and_then(|_| parse_request(&input))
        .and_then(|request| {
            let threads = match std::env::var("EVAS_STATIC_THREADS") {
                Ok(value) => value.parse::<usize>().map_err(|_| {
                    Error::new(
                        "invalid_config",
                        "EVAS_STATIC_THREADS must be an integer between 1 and 64",
                    )
                })?,
                Err(std::env::VarError::NotPresent) => 1,
                Err(error) => return Err(Error::new("invalid_config", error.to_string())),
            };
            run_with_threads(request, threads)
        });
    match result {
        Ok(response) => {
            let stdout = io::stdout();
            let mut output = stdout.lock();
            if serde_json::to_writer(&mut output, &response).is_err() || writeln!(output).is_err() {
                eprintln!("failed to write kernel response");
                std::process::exit(1);
            }
        }
        Err(error) => {
            eprintln!("{}", serde_json::to_string(&error).unwrap());
            std::process::exit(2);
        }
    }
}
