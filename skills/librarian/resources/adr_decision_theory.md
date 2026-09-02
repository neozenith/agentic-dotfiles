# The definition of a decision (aka ADR)


## Perception

- Nothing is ever good or bad.
- It is just `Facts`.
- `Facts` are things that are true (well... _percieved_ to be true, but that is a deeper discussion).

## Decisional Balance

- Given a `Value System`, we apply that filter (aka `Lens`) into sorting whether that thing is a `Pro` or a `Con`, whether it is a `Benefit` or a `Cost`.
- This sorting of Pros vs Cons is called `Decisional Balance`.
- An ADR is intended to capture this `Lens` of how to sort information through our `Value System`.

## Context

- `Context` is an important factor to capture the factors that went into the `Reasoning` of a `Decision Lens`.
    - `Scale` There are decisions I would make differently at different scales.
        - Eg Number of customers: 1,10,100,1000,10000+
        - Number of computer nodes, employees, etc
    - `Time` We have a limited deadline, or unlimited time
    - `Resources` Usually budget, people, etc into how we are going to support `Operational Expenses (OpEx)`
    - `Zeitgeist` As a different phrasing for the `Time & Place` when a decision is made.
      For example 2019, before ChatGPT and now 2026 with Fable tier Frontier models.
      The lay of the land has changed and could invalidate the `Decisional Balance`

## Regulating Condition

- It is similar to how the Agile Manifesto structured "We value X over Y, but not at the expense of Z".
    - X is the thing that is valued as beneficial
    - Y is the thing that is seen as a cost and often in tension with X
    - Z is the failure mode when Y is neglected and X gets over indexed.
      Z is the `Regulating Condition`.
- `Unless` This clause is intended to be the `Regulating Condition`.
    - I have worked in many places where "It's how we have always done things" has lead to failure.
    - Those people in the future do not have the permission and reasoning for that `Regulating Condition`
    - When that `Decision` should have expired and been reviewed.

## Informed Decisions

- As already stated above there are conditions and context that mean a decision should be reviewed as the `Decisional Balance` would have shifted.
- It is important to distinguish `Symptoms` from `Root Causes`.
    - `Information*` we `Percieve` as "true" and then assume are `Facts` are a failure mode when the `Information` is misleading.
    - I distinguish `Information*` with a trailing asterisk to imply the Information may be true or misleading.
    - `Information` without the trailing asterisk is the abstract concept where noting the chance it is misleading is not important for the conversation at hand.
    - We should treat all `Information*` with skepticism and seek `Coroboration` and/or `Empirical Evidence` we source ourselves through experimentation.
    - Sometimes we can only make `Decisions` based on incomplete `Information`.
    - We must evaluate the `Risks` and `Controls` we could associate with making a `Bad Decision`.
    - With sufficient `Controls` and `Acceptable Risk Budgets` we can still make an `Informed Decision` with `Incomplete Information` even if it proves to be a `Bad Decision`.
- We can revert / revise `Bad Decisions` with newer and more `Informed Decisions`.