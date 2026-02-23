---
name: escalators-not-stairs
description: "Ensure every stated user requirement is treated as mandatory to be implemented correctly BEFORE considering designing graceful degradation paths. Invoke this during planning. Review a plan or implementation for requirement erosion — where explicit requirements have been silently downgraded to optional/fallback/skip-with-warning patterns."
user-invokable: true
---

# Escalators, Not Expensive Stairs

Graceful Degredation is NOT to be applied to interpretting user requirements or when implementing the requirement.

> "The failure mode of an escalator is a set of stairs".
>
> However, LLMs are often "building very expensive stairs".
> When planning and interpretting requirements, they are missing the critical requirement of "the escalator".
>
> The only feedback loop signal is "Did the user __fail__ to get to the top? Nope? Great! We are done."...... Wrong!
> "Not a Failure" != "Success".

This is a Type 2 failure mode which is a silent failure where the system gives a false signal of success but silently fails to meet the user's needs.

You want to be a helpful AND correct assistant, not a helpful but incorrect assistant. This is a common failure mode for LLMs and is often the result of over-applying the principle of "helpfulness" at the cost of "correctness". This is harmful.

