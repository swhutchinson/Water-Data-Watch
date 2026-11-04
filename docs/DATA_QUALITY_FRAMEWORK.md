# Data quality framework

The standard this project works to. It is written the way a data quality programme would write one, using public water data as its subject.

**It is about the data, not the water.** Nothing here says whether any river or beach is clean or safe. Findings are observations for a steward to review, and describe no failing on the publisher's part. All owner roles, thresholds, response times and decisions are illustrative. They show how a programme could run, and describe no real organisation.

## The question it answers

> Can this data be trusted for the decision it is about to feed, and if not, who needs to do what?

Quality here means fitness for a purpose. That idea comes from the [Government Data Quality Framework](https://www.gov.uk/government/publications/the-government-data-quality-framework/the-government-data-quality-framework), which also says there is no such thing as perfect quality data. So there is no single score. The same data can be fit for one decision and not for another.

## How a problem travels through the system

1. **Rule.** One plain statement, with a reason, a severity, thresholds, an owner role, a steward role and an action. `rules/register.yaml` holds them, and `rules/sql/` holds their SQL.
2. **Check.** Every night, every rule runs against the full window.
3. **Proof.** Each rule's own defect is planted in a private copy of the data. The rule must catch it, and the copy is thrown away. Rule CHK-01 fails if any rule misses.
4. **Exception.** Each failed record is listed, with a link back to the source where one exists.
5. **Effect.** Where it can be measured, the figure is worked out carefully and carelessly. That shows whether the problem changes the answer, and sets the order to fix things in.
6. **Issue.** A Fail or For review opens an issue with a due date. Three passes in a row close it. A night that couldn't be checked changes nothing.
7. **Verdict.** Each decision has gates and conditions. See below.

## Outcomes

| Outcome | Meaning | Colour and sign on the page |
|---|---|---|
| Pass | Within its thresholds | Green, with a tick |
| Fail | Over its fail threshold | Red, with a cross |
| For review | Unusual, and a person needs to look | Amber, with an exclamation mark |
| Not checked | The source or the check failed | Grey, with a dash |
| No data | There was nothing to check | Grey outline, with a dash |

Thresholds are percentages of the records a rule could check. A rule can pass with a few exceptions listed, if its threshold allows it. That is deliberate: a threshold is a stated tolerance.

## Verdicts

There is no average. A failed gate can't be outvoted by the rules that passed.

| Verdict | When |
|---|---|
| Not fit | Any gate failed |
| Not checked | Otherwise, any gate couldn't be checked or had no data |
| Fit with conditions | Otherwise, any gate needs review, or any condition isn't clean |
| Fit | Everything that matters passed |

A dataset with no rules written for a decision shows Not checked and says why. The overall verdict for a decision is the worst across its datasets. Every verdict stores its reasons, so anyone can reproduce it from `verdict_reasons.csv`.

## Dimensions

The six dimensions are from the Government framework, which credits DAMA UK. Four more are added here because they answer questions those six don't.

| Dimension | Rules | Question |
|---|---|---|
| Completeness | COM | Is anything missing that should be there? |
| Uniqueness | UNI | Is anything counted twice? |
| Timeliness | TIM | Is it recent enough? |
| Validity | VAL | Is it in the agreed form? |
| Consistency | CON | Does it agree with itself? |
| Accuracy | ACC | Is it plausibly right? |
| Reconciliation | SRC, REC | Does it agree with its source, and with a second source? |
| Privacy | PRV | Could it identify anyone? |
| AI readiness | AI | Could a model learn the wrong thing from it? |
| Auditability | AUD | Could the result be defended later? |

## Dropping and leaving out are different

- **Dropping below-limit results is a mistake.** They are real measurements. Leaving them out pushes the average up, and the size of that effect is measured.
- **Leaving out pollution samples is a choice about the question.** They are real too, but were taken because someone suspected a problem. Either choice can be right, as long as it is stated.

The report never presents these two alike.

## What automation does, and what people do

| The engine does | A person does |
|---|---|
| Runs every rule and proves it still works | Writes and approves rules |
| Lists exceptions and measures their effect | Decides what a finding means |
| Opens and closes issues by their stated logic | Owns the fix, or accepts the risk |
| Gives a verdict from stated rules | Decides whether to use the data anyway |

`rules/decisions.yaml` records decisions people have made. The engine reads that file and never writes to it.

## What "governed" doesn't mean

A governed figure has a stated method, an owner and a trail. It doesn't mean the figure is true. Unverified explanations stay labelled as questions, such as why so many samples are stamped 07:00.
