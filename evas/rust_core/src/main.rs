use evas_kernel::{
    diagnostics::{self, Options, Timing},
    ir::{parse_request, Error, Response},
    run_with_threads,
};
use std::{
    io::{self, Read, Write},
    time::Instant,
};

fn execute() -> Result<Response, Error> {
    let mut input = String::new();
    let reading = diagnostics::span("protocol.read");
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| Error::new("input_io", e.to_string()))?;
    drop(reading);
    let decoding = diagnostics::span("protocol.decode");
    let request = parse_request(&input)?;
    drop(decoding);
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
}

struct CountWriter<W> {
    writer: W,
    bytes: usize,
}
impl<W: Write> Write for CountWriter<W> {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        let count = self.writer.write(bytes)?;
        self.bytes += count;
        Ok(count)
    }
    fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()
    }
}

fn diagnostic_budget(name: &str, default: usize) -> Result<usize, Error> {
    match std::env::var(name) {
        Ok(value) => value.parse().map_err(|_| {
            Error::new(
                "invalid_config",
                format!("{name} must be a nonnegative integer"),
            )
        }),
        Err(std::env::VarError::NotPresent) => Ok(default),
        Err(error) => Err(Error::new("invalid_config", error.to_string())),
    }
}

fn main() {
    if std::env::args().skip(1).collect::<Vec<_>>() == ["--version", "--json"] {
        let identity = serde_json::json!({
            "identity_version": 1,
            "name": env!("CARGO_PKG_NAME"),
            "version": env!("CARGO_PKG_VERSION"),
            "build_revision": null,
            "ir_schema_version": evas_kernel::ir::SCHEMA_VERSION,
            "request_protocol_version": null,
            "platform": {"os": std::env::consts::OS, "arch": std::env::consts::ARCH}
        });
        if serde_json::to_writer(io::stdout().lock(), &identity).is_err() {
            eprintln!("failed to write kernel identity");
            std::process::exit(1);
        }
        return;
    }
    let path = std::env::var_os("EVAS_DIAGNOSTICS_PATH");
    let (result, mut report) = if path.is_some() {
        let options = (|| {
            Ok(Options {
                max_records: diagnostic_budget("EVAS_DIAGNOSTICS_RECORDS", 2048)?,
                max_record_bytes: diagnostic_budget("EVAS_DIAGNOSTICS_BYTES", 1024 * 1024)?,
            })
        })();
        let (result, report) = match options {
            Ok(options) => diagnostics::capture(options, execute),
            Err(error) => diagnostics::capture(Options::default(), || Err(error)),
        };
        (result, Some(report))
    } else {
        (execute(), None)
    };
    let mut exit = 0;
    let encoding = Instant::now();
    match &result {
        Ok(response) => {
            let mut output = CountWriter {
                writer: io::stdout().lock(),
                bytes: 0,
            };
            if serde_json::to_writer(&mut output, response).is_err() || writeln!(output).is_err() {
                eprintln!("failed to write kernel response");
                exit = 1;
            }
            if let Some(report) = &mut report {
                report
                    .counters
                    .insert("output_json_bytes", output.bytes as u64);
            }
        }
        Err(error) => {
            eprintln!("{}", serde_json::to_string(error).unwrap());
            exit = 2;
        }
    }
    if let (Some(path), Some(mut report)) = (path, report) {
        report.stages.insert(
            "protocol.encode",
            Timing {
                calls: 1,
                nanos: encoding.elapsed().as_nanos().min(u64::MAX as u128) as u64,
            },
        );
        // An existing artifact is never overwritten. Partial writes or a killed
        // process are not a complete report; the client checks JSON and status.
        let write = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .and_then(|file| serde_json::to_writer(file, &report).map_err(io::Error::other));
        if let Err(error) = write {
            if exit == 0 {
                eprintln!(
                    "{}",
                    serde_json::to_string(&Error::new("diagnostic_io", error.to_string())).unwrap()
                );
                exit = 3;
            }
        }
    }
    if exit != 0 {
        std::process::exit(exit);
    }
}
