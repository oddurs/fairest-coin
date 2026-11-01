# Chapter 1: The ideal coin

Chapter 0 ended with a promise: quantum mechanics has outcomes that are not decided until
they happen. This chapter builds the simplest thing that has one, a quantum coin, out of
nothing but arithmetic. By the end it will flip, and it will turn out to be every bit as
fake as the random generators chapter 0 distrusted. That failure is the point.

## A bit, and a qubit

A classical bit is 0 or 1. A coin on the table is heads or tails. You can describe either
completely with one symbol.

A qubit needs two numbers. Its state is written

  |ψ⟩ = α|0⟩ + β|1⟩

where |0⟩ and |1⟩ are the two outcomes you can observe and α and β are *amplitudes*:
complex numbers with |α|² + |β|² = 1. This project calls |0⟩ heads and |1⟩ tails,
everywhere.

Amplitudes are not probabilities, but they decide them. When you measure the qubit you see
0 with probability |α|² and 1 with probability |β|². This is the Born rule, and it is the
only bridge between the arithmetic and anything you can observe. After the measurement the
qubit simply *is* what you saw; the amplitudes are gone.

In code, a qubit is a vector of two complex numbers. A coin lying heads up is

```pycon
>>> import numpy as np
>>> heads = np.array([1, 0], dtype=complex)
>>> abs(heads) ** 2
array([1., 0.])
```

## Tossing it

To toss the coin we need an operation that takes heads to "both, equally". Operations on
qubits are matrices that preserve the total probability (unitary matrices), and this one is
the Hadamard gate:

```pycon
>>> from coin.gates import H
>>> H.real.round(3)
array([[ 0.707,  0.707],
       [ 0.707, -0.707]])
>>> tossed = H @ heads
>>> (abs(tossed) ** 2).round(3)
array([0.5, 0.5])
```

That is the whole quantum coin: start at |0⟩, apply H, measure. Fifty-fifty.

So far this looks like a fancy way to write ½. Here is where it stops being one. Toss a
classical coin twice and it is still random. Toss the quantum coin twice:

```pycon
>>> (abs(H @ H @ heads) ** 2).round(3)
array([1., 0.])
```

Heads, every time. The second H does not randomise the coin further; it undoes the first.
The amplitudes for tails, one positive and one negative, cancel. Probabilities can only
add, so no theory built on probabilities alone can do this. Amplitudes can cancel, and
cancellation, *interference*, is the first thing quantum mechanics does that a coin cannot.

## Circuits

Writing matrices by hand stops scaling at about two qubits, so the project describes
experiments as circuits: a list of gates and measurements on numbered qubits.

```pycon
>>> from coin.circuit import Circuit
>>> from coin.sim import probabilities
>>> coin = Circuit(1).h(0).measure(0, 0)
>>> probabilities(coin)
{'0': 0.5, '1': 0.5}
>>> probabilities(Circuit(1).h(0).h(0).measure(0, 0))
{'0': 1.0}
```

Those numbers are tidier than the arithmetic behind them. The amplitudes are 1/√2, which no
computer stores exactly, and the probabilities come out a hair off before the simulator
renormalises them and drops anything smaller than 10⁻¹² as rounding noise. That is why every
test in this project compares computed numbers with a stated tolerance, never with `==`.
The examples in these chapters are the one exception: they check what you would see
printed, digit for digit.

```pycon
>>> from coin.sim import simulate
>>> simulate(Circuit(1).h(0)).real
array([0.70710678, 0.70710678])
```

With n qubits the state needs 2ⁿ amplitudes, one for every string of outcomes. The
simulator stores them as an n-dimensional array with one axis of length 2 per qubit, and
applies a gate by contracting its matrix against just the axes of the qubits it touches:

<!-- from: src/coin/sim.py -->
```python
    unitary = matrix(gate).reshape((2,) * (2 * k))
    axes = [n - 1 - q for q in reversed(gate.qubits)]
    contracted = np.tensordot(unitary, state, axes=(list(range(k, 2 * k)), axes))
    return np.moveaxis(contracted, list(range(k)), axes)
```

The `n - 1 - q` is bookkeeping for a convention. Outcome strings are written with qubit 0 on
the right, as in binary numbers and as on IBM's hardware, so qubit 0 is the *last* axis.

```pycon
>>> probabilities(Circuit(3).x(0).measure_all())
{'001': 1.0}
```

## Flipping

`probabilities` is exact. A real coin does not give you probabilities; it gives you one
outcome per flip. The simulator imitates that by drawing outcomes with the Born
probabilities, all `shots` flips in one draw:

<!-- from: src/coin/sim.py -->
```python
    counts = rng.multinomial(shots, _distribution(circuit, noise))
```

(`noise` is empty for the ideal coin. Chapter 2 is where it stops being empty.)

and the `coin` command wraps it:

```console
$ coin flip --sim --shots 10000 --seed 1
heads   4,971   49.71%
tails   5,029   50.29%
```

4,971 rather than 5,000 is not a flaw. Ten thousand fair flips scatter around 5,000 with a
standard deviation of √(10000 · ½ · ½) = 50, so 29 short is well inside the expected
wobble. A coin that came up *exactly* 5,000 every time would be the suspicious one.

## The catch

Look at what made those numbers: `rng`, a NumPy random generator, started from `--seed 1`.
Run it again with the same seed and you get the same ten thousand flips. Every outcome above
was decided by an arithmetic procedure before the command ran.

That is precisely the kind of randomness chapter 0 rejected. The simulator gets the
*probabilities* exactly right, because they are arithmetic, but it cannot produce a single
genuinely random outcome, because no arithmetic can. The amplitudes say "half heads,
half tails" and then a pseudo-random generator does the flipping.

To get an outcome that nothing decided in advance we need an actual qubit. Chapter 2 sends
this exact circuit to an IBM quantum computer, and the first thing it finds is that the real
coin is not fair.
