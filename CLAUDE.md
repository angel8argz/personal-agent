# CLAUDE.md

## NEVER (laws; exceptions require asking first)
- Never exceed 200 changed lines in one commit without asking.
- Never touch src/auth/, src/billing/, migrations/, or prod config unattended.
- Never report work as done from your own assessment. Done = the check passed.
- Never invent a secret, an endpoint, or a convention. Stop and ask.
- Never add a dependency. Propose it in STATE.md and stop.
- Never exceed effort high inside any loop. xhigh is for one-shot reviews only.
- Never edit or delete a test to make it pass. That is a fail, always.
- Never echo, transcribe, or explain your internal reasoning in response
  text. (Official: triggers reasoning_extraction refusals on Fable 5.)
- When a /goal condition passes, write goals/<name>.md with the condition as
  its predicate before reporting success.