import argparse
import json
import os
import os.path as osp
import re
import shutil
import subprocess
from typing import Optional, Tuple

from ai_scientist.generate_ideas import search_for_papers
from ai_scientist.llm import (
    AVAILABLE_LLMS,
    create_client,
    extract_json_between_markers,
    get_response_from_llm,
)
from ai_scientist.website_search import search_for_websites


# GENERATE LATEX
def generate_latex(coder, folder_name, pdf_file, timeout=30, num_error_corrections=5):
    folder = osp.abspath(folder_name)
    cwd = osp.join(folder, "latex")  # Fixed potential issue with path
    writeup_file = osp.join(cwd, "template.tex")

    # Check all references are valid and in the references.bib file
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    cites = re.findall(r"\\cite[a-z]*{([^}]*)}", tex_text)
    references_bib = re.search(
        r"\\begin{filecontents}{references.bib}(.*?)\\end{filecontents}",
        tex_text,
        re.DOTALL,
    )
    if references_bib is None:
        print("No references.bib found in template.tex")
    else:
        bib_text = references_bib.group(1)
        cites = [cite.strip() for item in cites for cite in item.split(",")]
        for cite in cites:
            if cite not in bib_text:
                print(f"Reference {cite} not found in references.")
                prompt = f"""Reference {cite} not found in references.bib. Is this included under a different name?
    If so, please modify the citation in template.tex to match the name in references.bib at the top. Otherwise, remove the cite."""
                coder.run(prompt)

    # Check all included figures are actually in the directory.
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    referenced_figs = re.findall(r"\\includegraphics.*?{(.*?)}", tex_text)
    all_figs = [f for f in os.listdir(folder) if f.endswith(".png")]
    for figure in referenced_figs:
        if figure not in all_figs:
            print(f"Figure {figure} not found in directory.")
            prompt = f"""The image {figure} not found in the directory. The images in the directory are: {all_figs}.
Please ensure that the figure is in the directory and that the filename is correct. Check the notes to see what each figure contains."""
            coder.run(prompt)

    # Remove duplicate figures.
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    referenced_figs = re.findall(r"\\includegraphics.*?{(.*?)}", tex_text)
    duplicates = {x for x in referenced_figs if referenced_figs.count(x) > 1}
    if duplicates:
        for dup in duplicates:
            print(f"Duplicate figure found: {dup}.")
            prompt = f"""Duplicate figures found: {dup}. Ensure any figure is only included once.
If duplicated, identify the best location for the figure and remove any other."""
            coder.run(prompt)

    # Remove duplicate section headers.
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    sections = re.findall(r"\\section{([^}]*)}", tex_text)
    duplicates = {x for x in sections if sections.count(x) > 1}
    if duplicates:
        for dup in duplicates:
            print(f"Duplicate section header found: {dup}")
            prompt = f"""Duplicate section header found: {dup}. Ensure any section header is declared once.
If duplicated, identify the best location for the section header and remove any other."""
            coder.run(prompt)

    # Iteratively fix any LaTeX bugs
    for i in range(num_error_corrections):
        # Filter trivial bugs in chktex
        check_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()
        if check_output:
            prompt = f"""Please fix the following LaTeX errors in `template.tex` guided by the output of `chktek`:
{check_output}.

Make the minimal fix required and do not remove or change any packages.
Pay attention to any accidental uses of HTML syntax, e.g. </end instead of \\end.
"""
            coder.run(prompt)
        else:
            break
    compile_latex(cwd, pdf_file, timeout=timeout)


def compile_latex(cwd, pdf_file, timeout=30):
    print("GENERATING LATEX")

    commands = [
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["bibtex", "template"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
    ]

    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            print("Standard Output:\n", result.stdout)
            print("Standard Error:\n", result.stderr)
        except subprocess.TimeoutExpired:
            print(f"Latex timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            print(f"Error running command {' '.join(command)}: {e}")

    print("FINISHED GENERATING LATEX")

    # Attempt to move the PDF to the desired location
    try:
        shutil.move(osp.join(cwd, "template.pdf"), pdf_file)
    except FileNotFoundError:
        print("Failed to rename PDF.")

per_section_tips= {
  "Abstract": [
    "- Provide a concise overview of the startup idea or MVP.",
    "- Highlight what problem you are solving, who benefits, and why it matters.",
    "- State what you have learned from building and testing the MVP."
],
  "Background": [
    "- Include a few relevant websites that are most relevant to the idea. This section should be very concise. NEVER mention the our approach or results from the experiments.",
  ],
  "Problem Statement": [
    "- Describe the pain point or challenge in detail.",
    "- Clearly articulate the gap in existing solutions or opportunities for innovation.",
    "- NEVER mention the our approach or results from the experiments."
  ],
  "MVP Implementation": [
    "- First present the solution that you are proposing that corresponds to the problem statement.",
    "- Provide a high-level technical overview of the MVP to test the effectiveness of the solution. Remember, MVP is not the solution, it is just a way to test the solution.",
    "- You can put conversation logs or usage logs to illustrate the features of the MVP. DO NOT ADD ANY SURVEY RESULTS.",
    "- Include simple diagrams using TikZ."
  ],
  "Validation Approach": [
    "- Define key metrics or criteria for validating your assumptions.",
    "- List imprortant experiments (Runs) you have conducted, do not add the ones that had bugs. We are comparing the results across different features. We are not interested in bug fixes or small UX improvments here. Do not use run numbers, instead use the description of the experiments."
    "- Breifly explain how the survey is simulated using LLM agents.",
    "- DO NOT ADD ANY SURVEY RESULTS. It should be done in the following results section."
  ],
  "Results": [
    "- Shows the results of the method described in Validation Approach.",
    "- Compare results (surveys and app usage logs) between different runs and analyze the results. Do not add the ones that had bugs. We are comparing the results across different features. We are not interested in bug fixes or small UX improvments here. Do not use run numbers, instead use the description of the experiments.",
    "- Include some app usage examples to illustrate features of MVP.",
    "- Include figures and tables (for open ended answers) to present the results.",
    "- Make sure this section flows naturally and tells a story. Make sure it matches with the validation approach. Do not just present the result without discussion or context."
  ],
  "Conclusion and Next Steps": [
    "- Recap main takeaway. ",
    "- Include limitations of the simmple text based MVP compared to full product, and AI agent based validation method."
    "- Address any open questions or areas needing further exploration.",
    "- Propose a clear roadmap for future development."
  ],
  "Appendix": [
    "- Add AppCode and some exact answers to openended questions not included in the main text."
    "- Detail how you have fixed bugs or made improvements based on user feedback over all the runs. You can add usage logs or user feedback to illustrate the improvements."
  ]
}


error_list = """- Unenclosed math symbols
- Only reference figures that exist in our directory
- LaTeX syntax errors
- Numerical results that do not come from explicit experiments and logs
- Repeatedly defined figure labels
- References to papers that are not in the .bib file, DO NOT ADD ANY NEW CITATIONS!
- Unnecessary verbosity or repetition, unclear text
- Results or insights in the `notes.txt` that have not yet need included
- Any relevant figures that have not yet been included in the text
- Closing any \\begin{{figure}} with a \\end{{figure}} and \\begin{{table}} with a \\end{{table}}, etc.
- Duplicate headers, e.g. duplicated \\section{{Introduction}} or \\end{{document}}
- Unescaped symbols, e.g. shakespeare_char should be shakespeare\\_char in text
- Incorrect closing of environments, e.g. </end{{figure}}> instead of \\end{{figure}}
- Incorrect dash, e.g. - instead of --
- Incorrect straight quotes. You need to use ``content'' instead of "content"
"""

refinement_prompt = (
    """Great job! Now criticize and refine only the {section} that you just wrote.
Make this complete in this pass, do not leave any placeholders.

Pay particular attention to fixing any errors such as:
"""
    + error_list
)

second_refinement_prompt = (
    """Criticize and refine the {section} only. Recall the advice:
{tips}
Make this complete in this pass, do not leave any placeholders.

Pay attention to how it fits in with the rest of the paper.
Identify any redundancies (e.g. repeated figures or repeated text), if there are any, decide where in the paper things should be cut.
Identify where we can save space, and be more concise without weakening the message of the text.
Fix any remaining errors as before:
"""
    + error_list
)

# CITATION HELPERS
citation_system_msg = """You have already written an initial draft of the paper and now you are looking to add missing citations to related information throughout the paper.
The Background section already has some initial comments on which websites to add and discuss.

Focus on completing the existing write-up and do not add entirely new elements unless necessary.
Feel free to add more cites to a particular point if there is only one or two references.
Ensure no information is cited without a corresponding reference in the `references.bib` file.
Aim to discuss a broad range of relevant information, not just the most popular ones.
Make sure not to copy verbatim from prior literature to avoid plagiarism.

You will be prompted to give a precise description of where and how to add the cite, and a search query for the websites to be cited.
Finally, you will select the most relevant cite from the search results (few results will be shown).
You will have {total_rounds} rounds to add the references, but do not need to use them all.

You do not need to scrape the website as the information has already been provided to you. Say no to Add URL to the chat?.
DO NOT ADD A CITATION THAT ALREADY EXISTS! ESPECIALLY DO NOT ADD CITATION OF THE AI SCIENTIST PAPER."""

citation_first_prompt = '''Round {current_round}/{total_rounds}:

You have written this LaTeX draft so far:

"""
{draft}
"""

Identify the most important citation that you still need to add, and the query to find the paper.

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason over the paper and identify where citations should be added.
If no more citations are needed, add "No more citations needed" to your thoughts.
Do not add "No more citations needed" if you are adding citations this round.

In <JSON>, respond in JSON format with the following fields:
- "Description": A precise description of the required edit, along with the proposed text and location where it should be made.
- "Query": The search query to find the website, the query should be detailed and describe the information you are looking for, e.g. 'number of people living in Toyko'

Ensure the description is sufficient to make the change without further context. Someone else will make the change.
The query will work best if you are able to recall the exact name of the paper you are looking for, or the authors.
This JSON will be automatically parsed, so ensure the format is precise.'''

citation_second_prompt = """Search has recovered the following articles:

{websites}

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason over the search results and identify which citation best fits your paper and the location is to be added at.
If none are appropriate, add "Do not add any" to your thoughts.

In <JSON>, respond in JSON format with the following fields:
- "Selected": A list of the indices of the selected papers to be cited, e.g. "[0, 1]". Can be "[]" if no papers are selected. This must be a string.
- "Description": Update the previous description of the required edit if needed. Ensure that any cites precisely match the name in the bibtex!!!

Do not select websites that are already in the `references.bib` file at the top of the draft, or if the same citation exists under a different name.
This JSON will be automatically parsed, so ensure the format is precise."""


def get_citation_aider_prompt(
        client, model, draft, current_round, total_rounds
) -> Tuple[Optional[str], bool]:
    msg_history = []
    try:
        text, msg_history = get_response_from_llm(
            citation_first_prompt.format(
                draft=draft, current_round=current_round, total_rounds=total_rounds
            ),
            client=client,
            model=model,
            system_message=citation_system_msg.format(total_rounds=total_rounds),
            msg_history=msg_history,
        )
        if "No more citations needed" in text:
            print("No more citations needed.")
            return None, True

        ## PARSE OUTPUT
        json_output = extract_json_between_markers(text)
        assert json_output is not None, "Failed to extract JSON from LLM output"
        query = json_output["Query"]
        websites = search_for_websites(query)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
        return None, False

    if websites is None:
        print("No websites found.")
        return None, False

    website_strings = []
    for i, website in enumerate(websites):
        website_strings.append(
            """{i}: {title}. {authors}. {venue}, {year}.\nAbstract: {summary} \nKey Quotes: {key_quotes}""".format(
                i=i,
                title=website["title"],
                authors=website["authors"],
                venue=website["venue"],
                year=website["year"],
                summary=website["summary"],
                key_quotes=website["key_quotes"],
            )
        )
    websites_str = "\n\n".join(website_strings)

    try:
        text, msg_history = get_response_from_llm(
            citation_second_prompt.format(
                websites=websites_str,
                current_round=current_round,
                total_rounds=total_rounds,
            ),
            client=client,
            model=model,
            system_message=citation_system_msg.format(total_rounds=total_rounds),
            msg_history=msg_history,
        )
        if "Do not add any" in text:
            print("Do not add any.")
            return None, False
        ## PARSE OUTPUT
        json_output = extract_json_between_markers(text)
        assert json_output is not None, "Failed to extract JSON from LLM output"
        desc = json_output["Description"]
        selected_websites = json_output["Selected"]
        selected_websites = str(selected_websites)

        # convert to list
        if selected_websites != "[]":
            selected_websites = list(map(int, selected_websites.strip("[]").split(",")))
            assert all(
                [0 <= i < len(websites) for i in selected_websites]
            ), "Invalid website index"
            bibtexs = [websites[i]["citationStyles"]["bibtex"] for i in selected_websites]
            bibtex_string = "\n".join(bibtexs)
        else:
            return None, False

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
        return None, False

    # Add citation to draft
    aider_format = '''The following citations have just been added to the end of the `references.bib` file definition at the top of the file:
"""
{bibtex}
"""
You do not need to add them yourself.
ABSOLUTELY DO NOT ADD IT AGAIN!!!

Make the proposed change to the draft incorporating these new cites:
{description}

Use your judgment for whether these should be cited anywhere else.
Make sure that any citation precisely matches the name in `references.bib`. Change its name to the correct name in the bibtex if needed.
Ensure the citation is well-integrated into the text.'''

    aider_prompt = (
            aider_format.format(bibtex=bibtex_string, description=desc)
            + """\n You must use \cite or \citet to reference papers, do not manually type out author names."""
    )
    return aider_prompt, False


# PERFORM WRITEUP
def perform_writeup(
        idea, folder_name, coder, cite_client, cite_model, num_cite_rounds=20
):
    # CURRENTLY ASSUMES LATEX
    abstract_prompt = f"""We've provided the `latex/template.tex` file to the project. We will be filling it in section by section. Do not write the results before the result section.

First, please fill in the "Title" and "Abstract" sections of the writeup. Throughout the report, do not mention run number, instead use description of each run.

Some tips are provided below:
{per_section_tips["Abstract"]}

Before every paragraph, please include a brief description of what you plan to write in that paragraph in a comment.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
    coder_out = coder.run(abstract_prompt)
    coder_out = coder.run(
        refinement_prompt.format(section="Abstract")
        .replace(r"{{", "{")
        .replace(r"}}", "}")
    )
    for section in [
        "Problem Statement", 
        "MVP Implementation",
        "Validation Approach",
        "Results",
        "Conclusion and Next Steps",
        "Appendix",
    ]:
        section_prompt = f"""Please fill in the {section} of the writeup. Some tips are provided below:
{per_section_tips[section]}

Be sure to use \cite or \citet where relevant, referring to the works provided in the file.
Do not cite anything that is not already in `references.bib`. Do not add any new entries to this.

Keep the experimental results (figures and tables) only in the Results section, and make sure that any captions are filled in.
In this pass, do not reference anything in later sections of the paper.

Before every paragraph, please include a brief description of what you plan to write in that paragraph in a comment.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
        coder_out = coder.run(section_prompt)
        coder_out = coder.run(
            refinement_prompt.format(section=section)
            .replace(r"{{", "{")
            .replace(r"}}", "}")
        )

    # SKETCH THE Background
    section_prompt = f"""Please fill in the Background of the writeup. Some tips are provided below:

{per_section_tips["Background"]}

For this section, very briefly sketch out the structure of the section, and clearly indicate what papers you intend to include.
Do this all in LaTeX comments using %.
The Background should be concise, only plan to discuss the most relevant work.
Do not modify `references.bib` to add any new citations, this will be filled in at a later stage.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
    coder_out = coder.run(section_prompt)

    # Fill paper with cites.
    for _ in range(num_cite_rounds):
        with open(osp.join(folder_name, "latex", "template.tex"), "r") as f:
            draft = f.read()
        prompt, done = get_citation_aider_prompt(
            cite_client, cite_model, draft, _, num_cite_rounds
        )
        if done:
            break
        if prompt is not None:
            # extract bibtex string
            bibtex_string = prompt.split('"""')[1]
            # insert this into draft before the "\end{filecontents}" line
            search_str = r"\end{filecontents}"
            draft = draft.replace(search_str, f"{bibtex_string}{search_str}")
            with open(osp.join(folder_name, "latex", "template.tex"), "w") as f:
                f.write(draft)
            coder_out = coder.run(prompt)

    coder_out = coder.run(
        refinement_prompt.format(section="Background")
        .replace(r"{{", "{")
        .replace(r"}}", "}")
    )

    ## SECOND REFINEMENT LOOP
    coder.run(
        """Great job! Now that there is a complete draft of the entire paper, let's refine each section again.
First, re-think the Title if necessary. Keep this concise and descriptive of the paper's concept, but try by creative with it."""
    )
    for section in [
        "Abstract",
        "Background",
        "Problem Statement", 
        "MVP Implementation",
        "Validation Approach",
        "Results",
        "Conclusion and Next Steps",
        "Appendix",
    ]:
        coder_out = coder.run(
            second_refinement_prompt.format(
                section=section, tips=per_section_tips[section]
            )
            .replace(r"{{", "{")
            .replace(r"}}", "}")
        )

    generate_latex(coder, folder_name, f"{folder_name}/{idea['Name']}.pdf")


if __name__ == "__main__":
    import json

    from aider.coders import Coder
    from aider.io import InputOutput
    from aider.models import Model

    parser = argparse.ArgumentParser(description="Perform writeup for a project")
    parser.add_argument("--folder", type=str)
    parser.add_argument("--no-writing", action="store_true", help="Only generate")
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-chat",
        choices=AVAILABLE_LLMS,
        help="Model to use for AI Scientist.",
    )
    args = parser.parse_args()
    client, client_model = create_client(args.model)
    print("Make sure you cleaned the Aider logs if re-generating the writeup!")
    folder_name = args.folder
    idea_name = osp.basename(folder_name)
    exp_file = osp.join(folder_name, "experiment.py")
    vis_file = osp.join(folder_name, "plot.py")
    notes = osp.join(folder_name, "notes.txt")
    model = args.model
    writeup_file = osp.join(folder_name, "latex", "template.tex")
    if not osp.exists(writeup_file):
        raise ValueError(f"Writeup file {writeup_file} not found")
    ideas_file = osp.join(folder_name, "ideas.json")
    with open(ideas_file, "r") as f:
        ideas = json.load(f)
    for idea in ideas:
        if idea["Name"] in idea_name:
            print(f"Found idea: {idea['Name']}")
            break
    if idea["Name"] not in idea_name:
        raise ValueError(f"Idea {idea_name} not found")
    fnames = [exp_file, writeup_file, notes]
    io = InputOutput(yes=True, chat_history_file=f"{folder_name}/{idea_name}_aider.txt")
    if args.model == "deepseek-coder-v2-0724":
        main_model = Model("deepseek/deepseek-coder")
    elif args.model == "llama3.1-405b":
        main_model = Model("openrouter/meta-llama/llama-3.1-405b-instruct")
    elif args.model == "deepseek-chat":
        main_model = Model("deepseek/deepseek-chat")
    else:
        main_model = Model(model)
    coder = Coder.create(
        main_model=main_model,
        fnames=fnames,
        io=io,
        stream=False,
        use_git=False,
        edit_format="diff",
    )
    if args.no_writing:
        generate_latex(coder, args.folder, f"{args.folder}/test.pdf")
    else:
        try:
            perform_writeup(idea, folder_name, coder, client, client_model, num_cite_rounds=2)
        except Exception as e:
            print(f"Failed to perform writeup: {e}")
