---
name: escalators-not-stairs
description: "Ensure every stated user requirement is treated as mandatory to be implemented correctly BEFORE considering designing graceful degradation paths. Invoke this during planning. Review a plan or implementation for requirement erosion — where explicit requirements have been silently downgraded to optional/fallback/skip-with-warning patterns."
user-invokable: true
---

# Escalators, Not Expensive Stairs

Graceful Degredation is NOT to be applied to interpretting user requirements or when implementing the requirement.

> "The failure mode of an escalator is a set of stairs".
>
> When planning and interpretting requirements, we are often "building very expensive stairs" and missing the requirement of "the escalator" as the critical function.
>
> Especially when the only feedback loop signal is "Did the user fail to get to the top? Nope? Great! We are done."...... Wrong!

This creates a Type 2 failure mode which is a silent failure where the system gives a false signal of success but silently fails to meet the user's needs.

You want to be a helpful AND correct assistant, not a helpful but incorrect assistant. This is a common failure mode for LLMs and is often the result of over-applying the principle of "helpfulness" at the cost of "correctness".

