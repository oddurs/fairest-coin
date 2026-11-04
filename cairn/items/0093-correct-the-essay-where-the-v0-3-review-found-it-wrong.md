---
id: 93
uid: 449f8528-c8f6-43d2-8258-a8fa23961359
title: Correct the essay where the v0.3 review found it wrong
type: docs
status: done
milestone: v0.3.2
assignee: Oddur Sigurdsson
created: 2026-11-04
updated: 2026-11-04
closed_at: 2026-11-04
priority: p2
effort: s
area: essay
---

## Problem

Found by the review of v0.3 on 2026-11-04. Chapter 2 explains the first chip map's sign error with the +0.63% lean measured
on the second map without saying so, and calls that prediction "readout alone" though it
modelled gate noise. Spike 0069 says the readout and coin jobs ran 23 minutes apart; that
is the gap between submissions, and chapter 2 says back to back. The README claims every
example in the chapters is run (a `text` block is not) and that quantum randomness "can
come with a proof" without the loophole caveat. The 0.3.1 changelog says "under 1.3e-5"
for 1.3036e-5.

## Acceptance criteria

- [x] Each listed sentence matches the archive, checked by recomputation
- [x] The README's claim about tested examples is true (the `text` block is run, or the claim is narrowed)

## 2026-11-04

Recomputed: coin compare on the second chip map gives median predicted −0.40%, measured +0.17% (first map −0.45%/+0.45%); meta.json times: |0⟩ submitted 05:52:32, back 06:14:23; |1⟩ 06:14:29 to 06:15:30; coin 06:15:36 to 06:16:13. Chapter 2 now names the second map, says both predictions took their lean from published readout (the dominant-errors table), and calls the link to the first map's sign error the likeliest reason, not a measurement. The dominant-errors block is a console block that the chapter tests run, with the script's full output (it had dropped four header lines); a test refuses any text block of command output. README: the proof needs assumptions, named; the tested-examples claim is narrowed to commands shown with their output. Spike 0069's timing and the 0.3.1 changelog's 1.3e-5 corrected.

## Result

Chapter 2, spike 0069, the README and the changelog match the archive: the +0.63% lean is named as the second map's, the job timing is what the archive records, the dominant-errors output is run by the tests, and the README claims only what is tested.
