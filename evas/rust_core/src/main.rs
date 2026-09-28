use evas_kernel::{ir::Error, run};
use std::io::{self, Read, Write};

fn main() {
    let mut input = String::new();
    let result = io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| Error::new("input_io", e.to_string()))
        .and_then(|_| {
            serde_json::from_str(&input).map_err(|e| Error::new("invalid_request", e.to_string()))
        })
        .and_then(run);
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
