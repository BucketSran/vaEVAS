# Public example

After implementing `/app/circuit.va`, run this deck from `/app/testbench`:

```sh
spectre tb.scs -format psfascii -raw psf
```

The 900 ns experiment saves `vin`, `track`, `rst`, and `vout`. It includes short and longer acquisition windows, repeated acquisitions, input changes during tracking and hold, reset during tracking, and reset during hold. The instance overrides `vinit` to 0.8 V.

The deck includes only the submitted model. It supplies no reference implementation. A saved waveform alone does not establish that the model satisfies the specification.
