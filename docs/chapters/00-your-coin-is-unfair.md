# Chapter 0: Your coin is unfair

Before a football match, a referee flips a coin and nobody objects. Before a cricket test,
a toss decides who bats. We trust a coin flip because nobody can predict it, and we assume
that means nobody *could* predict it. Those are different claims. This project is about the
gap between them.

## The coin obeys Newton

A coin in the air is a small, rigid body moving under gravity. Its flight is governed by
equations that were finished in the seventeenth century. Give those equations the coin's
starting height, its upward speed and its spin, and they tell you how it lands. Nothing in
the flight is undecided.

In 1986 the mathematician Joseph Keller worked this out for an idealised coin spinning
about a horizontal axis [1]. Outcomes form bands in the space of starting conditions:
heads for these speeds and spins, tails for those. The bands are thin, which is why
flipping feels random, but they are bands. A flip is a measurement of your thumb, and the
coin reports it faithfully.

Persi Diaconis, a statistician and former professional magician, took this further [2].
With Susan Holmes and Richard Montgomery he had a mechanical coin-tosser built: given the
same launch, it produced the same landing, every time. Then they looked at how real people
flip. A real coin does not spin cleanly about one axis; it also wobbles, like a tilted
spinning plate. That wobble means the coin spends slightly more of its flight with its
starting face pointing up. Their model predicted that a vigorously flipped coin lands on the
side it started about 51% of the time.

## Somebody checked

A prediction of 51% is easy to state and hard to test. To tell 51% from 50% you need tens
of thousands of flips, and to rule out one person's quirks you need many flippers.

In 2023 František Bartoš and a team of volunteers did it. They flipped coins from 46
currencies a total of 350,757 times, recording the starting face and the landing face
every time [3]. Coins landed on the side they started 50.8% of the time. The effect varied
between people, as the wobble theory says it should: some flippers wobble more than
others. It did not depend on which coin was used.

So the honest answer to "is a coin flip fair?" is: no, slightly, and in a direction you can
predict if you see which way up it started.

## Computers are worse, on purpose

When a computer needs a random number, it usually asks a *pseudo-random number generator*.
This is a short program that takes a number, the seed, and produces a long sequence of
numbers that look random. Start it with the same seed and it produces the same sequence,
every time. That is the point: a simulation you can replay is a simulation you can debug.

The standard generator in Python, the Mersenne Twister, produces numbers that pass a
battery of statistical tests. Yet anyone who sees 624 consecutive outputs can reconstruct
its entire internal state and predict every number that follows [4]. It is a sequence that
looks random to someone who isn't paying attention.

John von Neumann, one of the people who invented these methods, put it bluntly in 1951:
"Anyone who considers arithmetical methods of producing random digits is, of course, in a
state of sin" [5]. He used them anyway, as we all do, because for most purposes "nobody
here can predict it" is good enough.

## Testing does not save us

Perhaps we can sidestep the question of where the numbers come from and simply test the
numbers themselves. There are well-established suites for exactly this; the US National
Institute of Standards and Technology publishes one [6]. They check that zeros and ones are
equally common, that runs of the same bit have the right lengths, that no short pattern
repeats too often.

But a statistical test can only ever fail to find a pattern. It cannot show that no pattern
exists. The digits of π pass these tests, and they are as far from random as anything can
be: every digit is fixed by a formula, and anyone with the formula can produce them. A
sequence can be perfectly predictable and still look perfectly random to every test we
know how to write.

Physical noise sources, such as the thermal jitter in a resistor, or the wall of lava
lamps a web company films to seed its keys [7], are much better in practice. They are
unpredictable because they are complicated, though, not because the physics leaves the
outcome open. In principle, a detailed enough model of the lava lamp would predict it.

## The question

So we have three sources of randomness. Each one fails in its own way:

- A coin is physics we choose not to compute.
- A generator is arithmetic we choose not to look at.
- A test is a search that can come back empty, but never proves there's nothing to find.

There is one place in physics where the outcome is not merely hard to predict but is not
determined at all before it happens. In quantum mechanics, a measurement can have
outcomes whose probabilities are fixed by the theory while the individual result is fixed
by nothing. And, more remarkably, there is an experiment that can tell the difference
between "unpredictable because hidden" and "unpredictable because undecided", without
trusting the equipment that runs it.

That is the question this project asks, one chapter at a time, on a real quantum computer:

**Can you prove a coin flip is random?**

Chapter 1 builds the simplest possible quantum coin, from nothing.

## References

1. J. B. Keller, "The probability of heads," *The American Mathematical Monthly* 93(3),
   191–197 (1986). [doi:10.1080/00029890.1986.11971784](https://doi.org/10.1080/00029890.1986.11971784)
2. P. Diaconis, S. Holmes and R. Montgomery, "Dynamical bias in the coin toss," *SIAM
   Review* 49(2), 211–235 (2007). [doi:10.1137/S0036144504446436](https://doi.org/10.1137/S0036144504446436)
3. F. Bartoš et al., "Fair coins tend to land on the same side they started: Evidence from
   350,757 flips," *Journal of the American Statistical Association* 120, 2118–2127 (2025).
   [doi:10.1080/01621459.2025.2516210](https://doi.org/10.1080/01621459.2025.2516210);
   preprint [arXiv:2310.04153](https://arxiv.org/abs/2310.04153)
4. M. Matsumoto and T. Nishimura, "Mersenne Twister: a 623-dimensionally equidistributed
   uniform pseudo-random number generator," *ACM Transactions on Modeling and Computer
   Simulation* 8(1), 3–30 (1998). [doi:10.1145/272991.272995](https://doi.org/10.1145/272991.272995).
   The 624-word state is why 624 outputs suffice; Python's documentation warns that the
   generator is "completely unsuitable for cryptographic purposes":
   [docs.python.org/3/library/random.html](https://docs.python.org/3/library/random.html)
5. J. von Neumann, "Various techniques used in connection with random digits," *National
   Bureau of Standards Applied Mathematics Series* 12, 36–38 (1951). Reprinted in *Collected
   Works* vol. 5, 768–770 (1963): [scan hosted by Los Alamos](https://mcnpx.lanl.gov/pdf_files/InBook_Computing_1961_Neumann_JohnVonNeumannCollectedWorks_VariousTechniquesUsedinConnectionwithRandomDigits.pdf)
6. A. Rukhin et al., *A Statistical Test Suite for Random and Pseudorandom Number
   Generators for Cryptographic Applications*, NIST Special Publication 800-22 Rev. 1a
   (2010). [doi:10.6028/NIST.SP.800-22r1a](https://doi.org/10.6028/NIST.SP.800-22r1a)
7. Cloudflare, "LavaRand in production: the nitty-gritty technical details" (2017).
   [blog.cloudflare.com/lavarand-in-production-the-nitty-gritty-technical-details](https://blog.cloudflare.com/lavarand-in-production-the-nitty-gritty-technical-details/)
