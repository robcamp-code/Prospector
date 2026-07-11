# Run the agent with a sample test row
run:
    uv run python -m src.main

# Evaluate the agent on the test dataset
eval:
    uv run python -m src.eval
