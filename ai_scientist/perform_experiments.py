import json
import os.path as osp
import shutil
import subprocess
import sys
from subprocess import TimeoutExpired

MAX_ITERS = 4
MAX_STDERR_OUTPUT = 1500

coder_prompt = """Your goal is to implement and test the following MVP: {title}.
Problem: {problem}
Solution: {solution}
MVP: {mvp}
Target: {target}
You are given a total of up to {max_runs} runs to complete the necessary experiments. You do not need to use all {max_runs}. After every run, you will recieve the results written in results.txt.

After you complete each change, we will run the command `python experiment.py --out_dir=run_i' where i is the run number and evaluate the results.
YOUR PROPOSED CHANGE MUST USE THIS COMMAND FORMAT, DO NOT ADD ADDITIONAL COMMAND LINE ARGS.
You can then implement the next thing on your list."""


# RUN EXPERIMENT
def run_experiment(folder_name, run_num, max_runs, timeout=7200):
    cwd = osp.abspath(folder_name)
    # COPY CODE SO WE CAN SEE IT.
    shutil.copy(
        osp.join(folder_name, "experiment.py"),
        osp.join(folder_name, f"run_{run_num}.py"),
    )

    # LAUNCH COMMAND
    command = [
        "python",
        "experiment.py",
        f"--out_dir=run_{run_num}",
    ]
    try:
        result = subprocess.run(
            command, cwd=cwd, stderr=subprocess.PIPE, text=True, timeout=timeout
        )

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(f"Run {run_num} failed with return code {result.returncode}")
            if osp.exists(osp.join(cwd, f"run_{run_num}")):
                shutil.rmtree(osp.join(cwd, f"run_{run_num}"))
            print(f"Run failed with the following error {result.stderr}")
            stderr_output = result.stderr
            if len(stderr_output) > MAX_STDERR_OUTPUT:
                stderr_output = "..." + stderr_output[-MAX_STDERR_OUTPUT:]
            next_prompt = f"Run failed with the following error {stderr_output}"
        else:
            with open(osp.join(cwd, f"run_{run_num}", "results.txt"), "r") as f:
                results = f.read()

            next_prompt = f"""Run {run_num} completed. Here are the results:

Samples of the surveys:
{results}

Decide if you need to re-plan your experiments given the result (you often will not need to). Remember the ultimate goal is to validate the MVP.

Someone else will be using `notes.txt` to perform a writeup on this in the future.
Please include *all* relevant information for the writeup on Run {run_num}, including an run number, description and obervation. Be as verbose as necessary.
You must include all of the survey results, just copy the exact results. Additionally, include some important exerpts from the app usage logs in the following format, do not include user thoughts.

Log 1
INSIGHTS: <INSIGHTS>
USER INPUT: <USER INPUT>
APP OUTPUT: <APP OUTPUT>
continue...

Log 2
INSIGHTS: <INSIGHTS>
USER INPUT: <USER INPUT>
APP OUTPUT: <APP OUTPUT>
continue...

Do not delete/replace anything that is already in the `notes.txt` file.
"""
        if run_num == max_runs:
            next_prompt += "\nYou have finished all experiments. You cannot propose any more changes."
        else:
            next_prompt += f"""\nYou have {max_runs - run_num} more experiments you can use. You do not need to use all runs.
Then, implement the next thing on your list.
We will then run the command `python experiment.py --out_dir=run_{run_num + 1}'.
YOUR PROPOSED CHANGE MUST USE THIS COMMAND FORMAT, DO NOT ADD ADDITIONAL COMMAND LINE ARGS.
If you are finished with experiments, respond with 'ALL_COMPLETED'.""" 
        return result.returncode, next_prompt
    except TimeoutExpired:
        print(f"Run {run_num} timed out after {timeout} seconds")
        if osp.exists(osp.join(cwd, f"run_{run_num}")):
            shutil.rmtree(osp.join(cwd, f"run_{run_num}"))
        next_prompt = f"Run timed out after {timeout} seconds"
        return 1, next_prompt


# RUN PLOTTING
def run_plotting(folder_name, timeout=600):
    cwd = osp.abspath(folder_name)
    # LAUNCH COMMAND
    command = [
        "python",
        "plot.py",
    ]
    try:
        result = subprocess.run(
            command, cwd=cwd, stderr=subprocess.PIPE, text=True, timeout=timeout
        )

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(f"Plotting failed with return code {result.returncode}")
            next_prompt = f"Plotting failed with the following error {result.stderr}"
        else:
            next_prompt = ""
        return result.returncode, next_prompt
    except TimeoutExpired:
        print(f"Plotting timed out after {timeout} seconds")
        next_prompt = f"Plotting timed out after {timeout} seconds"
        return 1, next_prompt


# PERFORM EXPERIMENTS
def perform_experiments(idea, folder_name, coder, max_runs=2) -> bool:
    ## RUN EXPERIMENT
    current_iter = 0
    run = 1
    next_prompt = coder_prompt.format(
        title=idea["Title"],
        problem=idea["Problem"],
        solution=idea["Solution"],
        mvp=idea["MVP"],
        target=idea["Target"],
        max_runs=max_runs,
    )
    while run <= max_runs:
        if current_iter >= MAX_ITERS:
            print("Max iterations reached")
            break
        coder_out = coder.run(next_prompt)
        print(coder_out)
        if "ALL_COMPLETED" in coder_out:
            break
        return_code, next_prompt = run_experiment(folder_name, run, max_runs)
        if return_code == 0:
            run += 1
            current_iter = 0
        current_iter += 1
    if current_iter >= MAX_ITERS:
        print("Not all experiments completed.")
        return False
    coder_out = coder.run(next_prompt) # write final run result to notes.txt
    current_iter = 0
    next_prompt = """
Great job! Please modify `plot.py` to generate the most relevant plots for the final writeup. 

In particular, be sure to fill in the "plots" dictionary with the correct names for each run that you want to plot.

Make sure you have a good description for each of the run in the dictionary.

We will be running the command `python plot.py` to generate the plots.
"""
    while True:
        _ = coder.run(next_prompt)
        return_code, next_prompt = run_plotting(folder_name)
        current_iter += 1
        if return_code == 0 or current_iter >= MAX_ITERS:
            break
    next_prompt = """
Please modify `notes.txt` with a description of what each plot shows along with the filename of the figure. Please do so in-depth.

Somebody else will be using `notes.txt` to write a report on this in the future.
"""
    coder.run(next_prompt)

    return True
