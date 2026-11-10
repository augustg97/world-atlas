# The no-regression protocol — World Atlas

Answering the question every substantial change raises: *will this reduce the accuracy of any
individual frame?*

**Usually yes, substantially — and where it cannot be avoided, the residue can be made small,
named and justified rather than merely accepted.** This document is the mechanism.

---

## 1. Why "it will look like a regression" is usually the wrong thing to say

A long-lived model accumulates **errors that partly cancel**. Where the second happened to match
the first locally, an item was right **by cancellation, not by being right**. Remove both and it
moves.

That is not a regression. Keeping it would mean keeping a bug because it flattered one item.

So the first question about any apparent regression is: *was this item right, or merely
flattered?*

## 2. The gate

`{{GATE_SCRIPT}}` — read-only. It scores **every item the app actually treats this way**, on its
own window, under both states, and reports the **individual** outcome, not the average.

**It must mirror the app's real rules.** One project's gate scored 158 items where the build only
touches 124, because its eligibility guard was wrapped in `try/except: pass` around a function it
was calling wrongly — every call raised, every exception was swallowed, the guard passed
everything, and it reported "7 true regressions", five of which were items the build never
touches under either state.

**A `try/except` around a guard inverts it.** If the guard cannot run, raise.

Current result:

| | |
|---|---|
| items scored | |
| improved | |
| unchanged | |
| regressed | |
| mean | → |

## 3. Classify every regression

| class | n | meaning | response |
|---|---|---|---|
| **PRE-EXISTING** | | bad in *both* states; the change revealed it | fix the item |
| **RESOLUTION-LIMITED** | | not resolvable at the shipped grid | record it |
| **CANCELLATION** | | a small drop from a position the old error flattered | expected |
| **TRUE** | | genuinely worse | the only class that blocks anything |

Then diagnose the TRUE ones **individually**, in a table, rather than leaving them as a number.
In the prior project four of seven turned out to be data errors or scorer errors the change
merely exposed — including one item authored 3,300 km from the place it is named for.

| item | before → after | what is actually happening |
|---|---|---|

## 4. The protocol — five steps, in order

1. **Never ship on an average.** Run the gate before and after. An aggregate improvement with an
   unexamined tail is not evidence.
2. **Classify every regression.** A drop that is bad in both states is a pre-existing error
   surfacing; fix the item, never keep the compensating error.
3. **Adjudicate the true ones with an independent witness.** The model's own data cannot settle a
   dispute in which it is one of the parties.
4. **Fix, exempt, or record.** Every surviving TRUE case ends in a corrected datum, a documented
   exemption with a reason, or a recorded known-limit. **None may be silent.**
5. **Re-run and diff.** Ship when TRUE is zero or every remaining case has a written reason.

## 5. The same discipline for every other change

Every other staged change already has a pre-existing quantitative gate, and **the rule is that
none of them may move backwards**:

| change | the gate that must not regress | where |
|---|---|---|
| | | |

## 6. What this cannot promise

Be straight about the limits:

- **The classifier is heuristic** unless it consults the independent witness. Say which it is.
- **Say what "accuracy" means here.** A proxy score is a good proxy and not the whole truth.
- **Where two sources genuinely disagree, no protocol resolves it.** The honest response is to
  record the disagreement, with its measurement, as a known limit.
