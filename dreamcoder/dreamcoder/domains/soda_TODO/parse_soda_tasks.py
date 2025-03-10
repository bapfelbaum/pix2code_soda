import json
import os

from dreamcoder.domains.text.main import (
    ConstantInstantiateVisitor,
    LearnedFeatureExtractor,
)
from dreamcoder.domains.text.makeTextTasks import delimiters, guessConstantStrings
from dreamcoder.ec import commandlineArguments, ecIterator
from dreamcoder.grammar import Grammar
from dreamcoder.program import *
from dreamcoder.task import Task
from dreamcoder.type import arrow, tint
from dreamcoder.utilities import numberOfCPUs


### Types for Tasks
def guess_type(xs):
    """
    Return a TypeConstructor corresponding to x's python type.
    Raises an exception if the type cannot be guessed.
    """
    if all(isinstance(x, bool) for x in xs):
        return tbool
    elif all(isinstance(x, int) for x in xs):
        return tint
    elif all(isinstance(x, str) for x in xs):
        return tstr
    elif all(isinstance(x, list) for x in xs):
        return tlist(guess_type([y for ys in xs for y in ys]))
    else:
        raise ValueError("cannot guess type from {}".format(xs))


def guess_arrow_type(examples):
    a = len(examples[0][0])
    input_list = True  # TODO change for tuple / list
    input_types = []
    # guess_type([i for (i,), _ in examples])
    input_types = [guess_type([x for x, _ in examples])]
    output_type = guess_type([y for _, y in examples])
    return arrow(*(input_types + [output_type]))


def preprocess(x):
    if isinstance(x, tuple):
        return tuple(preprocess(z) for z in x)
    if isinstance(x, list):
        return [preprocess(z) for z in x]
    if isinstance(x, str):
        return [c for c in x]
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x
    assert False


# Create Task # TODO rename
def problem(item, needToTrain=False):
    examples = item["examples"]

    task = Task(
        item["name"],
        guess_arrow_type(examples),
        [((preprocess(x),), preprocess(y)) for x, y in examples],
    )

    task.mustTrain = True
    return task


### Tasks
def parse_relation_tasks(path=None):
    task_examples = []

    if path is None:
        path = "data/soda

    json_files = [f.path for f in os.scandir(path) if f.path.endswith(".json")]

    for task_file in json_files:
        task_name = task_file.split("/")[-1][:-5]
        f = open(task_file)
        examples = json.load(f)
        parsed_examples = []

        for example in examples:
            input = example["input"]

            output = example["output"]

            parsed_examples.append((input, output))

        task_dict = {"name": task_name, "examples": parsed_examples}

        task_examples.append(task_dict)

    tasks = [problem(item) for item in task_examples]

    for task in tasks:
        guessConstantStrings(task)

    return tasks


if __name__ == "__main__":
    parse_relation_tasks("data/soda_dc_tasks")
