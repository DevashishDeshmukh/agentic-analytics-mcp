# Reproducible README demo. Regenerate: make up && vhs docs/demo.tape
# Needs: Postgres running (make up), LLM key in .env. Uses ~4 LLM calls.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1280
Set Height 760
Set Padding 18
Set TypingSpeed 35ms
Set Theme "Catppuccin Mocha"
Set WaitPattern /\$$/

Hide
Type "cd /Users/devashishdeshmukh/Work/MCP && export PS1='$ ' && clear"
Enter
Sleep 500ms
Show

Type "# Two MCP servers, all tools read-only"
Enter
Type "make -s tools"
Enter
Wait@60s
Sleep 4s

Type "clear"
Enter
Type "# Baseline: schema only, no docs. The model guesses what 'net revenue' means."
Enter
Type `make -s ask Q="What was net revenue in 2024?" CONFIG=baseline`
Enter
Wait@90s
Sleep 7s

Type "clear"
Enter
Type "# RAG: retrieves the governed metric definition and cites it."
Enter
Type `make -s ask Q="What was net revenue in 2024?"`
Enter
Wait@90s
Sleep 7s

Type "clear"
Enter
Type "# Writes are rejected by Postgres itself, not by the prompt."
Enter
Type `make -s tool S=warehouse T=run_query A='{"sql":"DELETE FROM analytics.orders"}'`
Enter
Wait@60s
Sleep 5s
