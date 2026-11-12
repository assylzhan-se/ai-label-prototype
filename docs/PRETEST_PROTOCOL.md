# Questionnaire pretest and approval (feedback point 3)

Goal: check that students understand the six rating items, the 1–7 scale and the label-recall question
**before** recruiting participants. Pretest people are **not** used as study participants later.

## Who and how
- 3–5 AITU students aged 18–25 who have used a dating app (not team members).
- About 10 minutes each, in person or by video call, one at a time.
- Run the prototype in test mode: `http://127.0.0.1:5000/?test=1` (sessions are flagged as test data and never analysed).

## Steps (one interviewer + one note-taker)
1. Explain: "We are testing the questions, not you. Please think aloud."
2. The student goes through 2 profiles and answers normally while thinking aloud.
3. For each of the six items, ask:
   - "In your own words, what does this statement ask?"
   - "Was anything unclear or hard to answer?"
4. Ask about the scale: "What do 1, 4 and 7 mean to you?"
5. Ask the recall question and then: "What did you understand by 'how the profile photos were created'?"
6. Ask about the interface: "Was anything hard to tap, read or find on your phone?"

## Record form (one row per student × item)
| Pretest ID | Item | Paraphrase correct? (Y/N) | Problem noted | Suggested change |
|---|---|---|---|---|
| PT1 | 1 genuine | | | |

## Decision rule (fixed in advance)
- An item is **revised** if 2 or more students paraphrase it incorrectly or call it unclear.
- Any interface problem reported by 2 or more students is fixed and the tests are rerun.
- All changes are recorded in the report as deviations (date, what, why).

## Approval message (send before recruiting)
> Dear Professor, our team (Abdigalym, Demesh, Shalmanov, Aktore) would like to start data collection for our
> dating-app label experiment. Participants: AITU students aged 18–25, voluntary, anonymous (random study code
> only, no names/e-mails/IP), consent page and debrief included, fictional profiles with synthetic faces.
> The questionnaire was pretested with [n] students on [date]; changes: [none / list].
> May we start recruiting? Thank you.
