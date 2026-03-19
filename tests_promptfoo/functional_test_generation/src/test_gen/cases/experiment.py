import asyncio
import json
from pydantic import BaseModel
from src.test_gen.formatting import FormattedModel
from src.test_gen.assertions import TestCase, LLMRubricAssertion
from src.test_gen.utils import Assertions
from src.utils.tool_utils import list_experiment


class ExperimentEvaluationResult(BaseModel):
    evaluationId: str | None
    queryText: str
    searchConfigurationId: str


class ErrorMsg(BaseModel):
    error: str


class ExperimentEvaluationSnapshot(BaseModel):
    searchConfigurationId: str
    docIds: list[str]


class Metric(FormattedModel):
    metric: str
    value: float


class ExperimentSnapshot(BaseModel):
    snapshots: list[ExperimentEvaluationSnapshot]
    metrics: list[Metric]
    query_text: str


class ListExperimentResult(BaseModel):
    timestamp: str
    type: str
    status: str
    querySetId: str
    searchConfigurationList: list[str]
    judgmentList: dict[str, str] | list[str]
    size: int
    isScheduled: bool
    scheduledExperimentJobId: str | None
    results: list[ExperimentEvaluationResult | ErrorMsg | ExperimentSnapshot]


def get_experiments() -> list[ListExperimentResult]:
    """
    Provide overview of all experiments.
    The experiment output is same as calling get_experiment(experiment_id) for all
    experimentIds.
    :return:
    """
    return [
        ListExperimentResult(**x["_source"])
        for x in json.loads(asyncio.run(list_experiment()))["hits"]["hits"]
    ]


def get_top_n_experiments_overview_llm_rubric_assertion(
    data: list[ListExperimentResult],
) -> str:
    return Assertions.get_llm_rubric_assertion_yaml(
        data=data,
        relevant_fields=tuple(
            [
                "timestamp",
                "type",
                "status",
                "querySetId",
                "searchConfigurationList",
                "judgmentList",
                "size",
                "isScheduled",
                "scheduledExperimentJobId",
            ]
        ),
        field_key_to_description={},
        description_to_additional_values={},
    )


def create_experiments_last_n_overview_test_case(last_n: int) -> TestCase:
    experiments: list[ListExperimentResult] = get_experiments()
    experiments = list(reversed(sorted(experiments, key=lambda x: x.timestamp)))[
        :last_n
    ]

    return TestCase(
        prompt=f"""
                Give me an overview of the last {last_n} most recent experiments.
                Include the status of each experiment, the query, search configurations,
                judgement lists, experiment job id and an overview of the available results.
                """,
        assertions=tuple(
            [
                LLMRubricAssertion(
                    eval_prompt=get_top_n_experiments_overview_llm_rubric_assertion(
                        data=experiments
                    )
                )
            ]
        ),
    )