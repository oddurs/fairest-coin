# Chapter 4: Two coins that agree

Chapter 3 ended on π. No test of a sequence can prove it random, because a sequence that
was fixed in advance can pass every test. If anything can do better, it has to be a
property that no pre-written sequence could have. This chapter builds the thing that has
one: two coins, each fair on its own, that always land the same way. Then it shows that
agreeing, by itself, proves nothing.

## The Bell pair

One qubit in |0⟩, a Hadamard, and it is chapter 1's coin. Add a second qubit and a CX, a
gate that flips the second qubit when the first is |1⟩, and the pair is in

    (|00⟩ + |11⟩) / √2

the *Bell pair*. Measure both and there are only two outcomes, each half the time:

```pycon
>>> from coin.circuit import Circuit
>>> from coin.sim import probabilities
>>> bell = Circuit(2).h(0).cx(0, 1).measure(0, 0).measure(1, 1)
>>> probabilities(bell)
{'00': 0.5, '11': 0.5}
```

Each coin alone is fair: qubit 0 reads 1 half the time, and so does qubit 1. But the two
never disagree. Neither coin decided its face before it was read, and yet whichever face one
shows, the other shows too. This is *entanglement*: the pair has a definite state, and
neither qubit has one of its own.

## Glued coins also agree

Before making anything of that, consider two ordinary coins glued together, face to face.
Toss them as one and they too always agree, each fair on its own:

```pycon
>>> import numpy as np
>>> first = np.random.default_rng(4).integers(0, 2, 10_000)
>>> second = first.copy()
>>> float((first == second).mean()), float(first.mean())
(1.0, 0.4948)
```

Nothing quantum happened there. The second coin copied the first, as a list written in
advance could. From outcomes read this way alone, the Bell pair and the glued coins cannot
be told apart: both produce "same face, either face, half the time", and a sequence that
does that can be written down before anyone looks.

So agreement is not evidence of anything quantum, and this chapter's run cannot be either.
What it shows is that the pair can be made on real hardware, and how close it comes to the
ideal. The difference between the Bell pair and the glue only appears when the coins are
read in other ways, which chapter 5 does.

## Compiling it for the chip

Chapter 2 lowered the one-qubit coin to the gates IBM's hardware runs: `rz`, `sx` and `x`.
The pair needs one more. The CX is not native on `ibm_marrakesh`; the two-qubit gate the
chip runs is CZ, which flips the phase of |11⟩ and nothing else. A CX is a CZ with a
Hadamard on either side of its target, and those Hadamards join the single-qubit gates
around them, so the pair costs one CZ and no more pulses than it must.

This is the program that actually ran, as the archive keeps it:

```pycon
>>> from coin.archive import load_run
>>> run = load_run("data/runs/2026-11-05-dbme92m74qds73ds595g")
>>> print(run.circuit_qasm)
OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
rz(1.5707963267948966) q[0];
sx q[0];
rz(1.5707963267948966) q[0];
rz(1.5707963267948966) q[1];
sx q[1];
rz(1.5707963267948966) q[1];
cz q[0], q[1];
c[0] = measure q[0];
rz(1.5707963267948966) q[1];
sx q[1];
rz(1.5707963267948966) q[1];
c[1] = measure q[1];
<BLANKLINE>
>>> run.extra["executed_ops"]
{'cz': 1, 'measure': 2, 'rz': 6, 'sx': 3}
```

Three `rz`·`sx`·`rz` runs: the Hadamard on qubit 0, and the two Hadamards that turn the CZ
into a CX on qubit 1. The `rz` gates are free on hardware, since they are a change of frame
in the control electronics rather than a pulse. What costs time and error is three `sx`
pulses and one CZ.

The last line is the hardware's own count, read back after Qiskit mapped the program onto
the chip. It matches, because nothing is ever routed: a CZ can only run between two qubits
the chip couples, and the program is refused, rather than rewritten with SWAPs, if it asks
for any other pair.

## Choosing the pair

`ibm_marrakesh` couples 176 pairs of its 156 qubits. They are not alike: each pair's CZ has
its own error, and each qubit its own readout. Chapter 2's noise model extends to two
qubits: relaxation and depolarizing after every gate, the CZ included, then each qubit's
readout. Run on every coupled pair, it ranks them. The score is the CHSH value chapter 5
needs, but the ranking would barely change for agreement:

```console
$ coin predict --calibration data/runs/2026-11-05-dbme92m74qds73ds595g --pairs
156 coupled pairs scored; the best 5:
    pair  predicted S  cz error  readout
   5-6         2.7819   0.00124  published, published
  87-97        2.7534   0.00151  published, published
 153-154       2.7455   0.00233  published, published
 147-148       2.7401   0.00259  published, published
 137-147       2.7356   0.00179  published, published
```

156 rather than 176 because the model leaves out a pair if either qubit, or its CZ, has a
calibration it cannot use. The best was qubits 5 and 6. Its prediction for the Bell pair:
99.25% agreement, each coin within a fraction of a percent of fair.

## The run

The prediction was written to disk, then 10,000 shots of the pair ran on qubits 5 and 6:

```console
$ coin compare data/runs/2026-11-05-dbme92m74qds73ds595g
pair         5-6, 10,000 shots
agreement    97.67% measured, 99.25% predicted, z = -18.2 (outside 3σ)
P(1) on 5    50.80% measured, 50.02% predicted, z = +1.6 (within 3σ)
P(1) on 6    49.21% measured, 49.59% predicted, z = -0.8 (within 3σ)
```

Each coin is fair on its own, as predicted. Together they agree 97.67% of the time:
entangled, but less perfectly than the model expected. At 10,000 shots that gap is eighteen
standard deviations, so the model missed something.

The counts say what:

```pycon
>>> run.counts
{'00': 4883, '01': 196, '10': 37, '11': 4884}
```

Outcome strings are written qubit 6 first, so `01` means qubit 5 read 1 and qubit 6 read 0.
That happened 196 times; the reverse, 37. Disagreement from imperfect entanglement would be
even-handed. This is lopsided: when both should have read 1, qubit 6 read 0 about 4% of the
time, while its published readout error for |1⟩ was 0.78%.

It is the same lesson as chapter 2's qubit 59. A published readout number describes the
readout at calibration time, and the readout a job gets can be worse. The pair was chosen,
and its agreement predicted, from those published numbers. Later the same day, two readout
jobs measured every qubit's readout directly: qubit 5, this time, read |0⟩ as 1 6% of the
time, and qubits 153 and 154 came out ahead. So from here on the pair is chosen, and its
predictions made, from readout measured in the same session.

## What agreement does not show

The run shows that two qubits on a real chip can be entangled well enough to agree on
97.67% of 10,000 coins, each coin fair alone. It does not show that the coins were random,
nor even that anything quantum happened: glued coins agree too.

What glued coins cannot do is agree *by the right amount at every angle*. Read the Bell
pair not in the coin's own basis but along two axes rotated by an angle θ, and quantum
mechanics says the coins agree with probability cos²(θ/2); a pre-written list, however it
is made, cannot match that at every pair of angles at once. Chapter 5 measures that
difference, predicted and committed to git before the run, and asks what it certifies.
