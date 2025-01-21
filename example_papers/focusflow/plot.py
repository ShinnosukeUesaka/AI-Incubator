import json
import os
import os.path as osp
import pickle
from pathlib import Path
from typing import Dict, List, Set, Union

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plots: Dict[str, Dict[str, Union[str, Dict[str, str]]]] = {
    "Focus Improvement Results": {
        "filename": "focus_improvement_bar",
        "plot_type": "bar",
        "question": "Did the app help you maintain focus?",
        "runs": {
            "run_1": "Run 1: Core Features",
            "run_2": "Run 2: Task Prioritization",
            "run_3": "Run 3: Task Completion",
            "run_4": "Run 4: Fixed Priorities",
            "run_5": "Run 5: Custom Sessions"
        },
    },
    "Productivity Impact": {
        "filename": "productivity_impact_bar",
        "plot_type": "bar",
        "question": "How would you rate your productivity while using the app?", 
        "runs": {
            "run_1": "Run 1: Core Features",
            "run_2": "Run 2: Task Prioritization",
            "run_3": "Run 3: Task Completion",
            "run_4": "Run 4: Fixed Priorities",
            "run_5": "Run 5: Custom Sessions"
        },
    },
    "Reward System Effectiveness": {
        "filename": "reward_effectiveness_bar",
        "plot_type": "bar",
        "question": "Did the reward system motivate you to complete focus sessions?",
        "runs": {
            "run_1": "Run 1: Core Features",
            "run_2": "Run 2: Task Prioritization",
            "run_3": "Run 3: Task Completion",
            "run_4": "Run 4: Fixed Priorities",
            "run_5": "Run 5: Custom Sessions"
        },
    }
}

# LOAD FINAL RESULTS:
folders: Path = Path(".").iterdir()
final_results: Dict[str, pd.DataFrame] = {}
train_info: Dict = {}

for folder in folders:
    if folder.name.startswith("run") and folder.is_dir():
        with open(folder / "answers.csv", "r") as f:
            final_results[folder.name] = pd.read_csv(f)

def create_bar_chart(data_dict: Dict[str, pd.DataFrame], 
                    question: str,
                    title: str,
                    output_path: Path,
                    runs_config: Dict[str, str]) -> None:
    plt.figure(figsize=(12, 6))
    
    # Get all unique options across all runs
    all_options: Set[str] = set()
    for run_data in data_dict.values():
        all_options.update(run_data[question].unique())
    all_options = sorted(list(all_options))
    
    # Calculate positions for grouped bars
    n_runs: int = len(data_dict)
    width: float = 0.8 / n_runs  # Bar width
    positions: np.ndarray = np.arange(len(all_options))
    
    # Plot bars for each run
    for i, (run_name, run_data) in enumerate(data_dict.items()):
        counts = run_data[question].value_counts()
        values: List[int] = [counts.get(option, 0) for option in all_options]
        x_positions: np.ndarray = positions + (i - n_runs/2 + 0.5) * width
        
        bars = plt.bar(x_positions, values, width, 
                      label=runs_config[run_name],
                      alpha=0.8)
        
        # Add value labels on top of each bar
        for bar in bars:
            height: float = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom')
    
    plt.title(title)
    plt.xlabel("Options")
    plt.ylabel("Number of Responses")
    plt.xticks(positions, all_options)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def create_pie_chart(data: pd.DataFrame,
                    question: str,
                    title: str,
                    output_path: Path) -> None:
    plt.figure(figsize=(10, 8))
    counts = data[question].value_counts()
    
    plt.pie(counts.values, labels=counts.index, autopct='%1.1f%%',
            startangle=90)
    plt.title(title)
    
    plt.axis('equal')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

# Generate plots for each configuration
for plot_name, plot_config in plots.items():
    if plot_config["plot_type"] == "pie":
        # Validate that pie charts only have one run
        if len(plot_config["runs"]) != 1:
            raise ValueError(f"Pie chart '{plot_name}' must have exactly one run, "
                           f"but has {len(plot_config['runs'])} runs.")
        
        run_name = list(plot_config["runs"].keys())[0]
        if run_name in final_results:
            output_path = Path(f"{plot_config['filename']}_{run_name}.png")
            create_pie_chart(
                final_results[run_name],
                plot_config["question"],
                plot_name,
                output_path
            )
    
    elif plot_config["plot_type"] == "bar":
        # Collect data for all runs in this plot
        plot_data: Dict[str, pd.DataFrame] = {}
        for run_name, run_label in plot_config["runs"].items():
            if run_name in final_results:
                plot_data[run_name] = final_results[run_name]
        
        if plot_data:  # Only create plot if we have data
            output_path = Path(f"{plot_config['filename']}.png")
            create_bar_chart(
                plot_data,
                plot_config["question"],
                plot_name,
                output_path,
                plot_config["runs"]
            )

print("Plots have been generated.")
