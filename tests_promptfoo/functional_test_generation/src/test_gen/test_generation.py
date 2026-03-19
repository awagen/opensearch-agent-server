import asyncio
import json
import os
import sys
from collections.abc import Collection
import locale

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# adding the src root to the path here so we can both call the file's main directly
# as well as call the script via src.test_gen.test_generation from direct parent dir
# of src package
script_path = "/".join(os.path.realpath(__file__).split("/")[:-1])
sys.path.insert(0, f"{script_path}/../../")
from src.test_gen.assertions import (
    ContainsAssertion,
    LLMRubricAssertion,
    TestCase,
    TestSuite,
)
from src.test_gen.opensearch_client import get_client_manager
from src.utils.tool_utils import (
    get_document_ctr,
    get_judgment,
    get_query_ctr,
    get_query_performance_metrics,
    get_query_set,
    get_top_queries_by_engagement,
    list_experiment,
    list_judgment_list,
    list_query_set,
    list_search_configuration,
)
from src.utils.utils import flatten_lists


def format_value(value, float_decimals: int = 1) -> str | None:
    if isinstance(value, float):
        if int(value) == value:
            return str(int(value))
        else:
            return locale.format_string(f"%.{float_decimals}f", value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, dict):
        return json.dumps(value)
    if value is None:
        return None
    return value


class FormattedModel(BaseModel):
    def print_representation(self, float_decimals: int = 1):
        dict = self.model_dump()
        return {key: format_value(value, float_decimals) for key, value in dict.items()}


class ClickResult(FormattedModel):
    query_text: str
    search_volume: int
    searches_with_clicks: int
    total_clicks: int
    ctr_percentage: float
    average_clicks_per_search: float
    zero_click_rate_percentage: float


class DocumentCTR(FormattedModel):
    document_id: str
    time_range_days: int
    total_impressions: int
    total_clicks: int
    ctr_percentage: float
    average_position_when_clicked: float | None


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


class JudgementRating(BaseModel):
    rating: str | float
    docId: str


class JudgementRatings(BaseModel):
    query: str
    ratings: list[JudgementRating]


class JudgementListResults(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    timestamp: str
    name: str
    status: str
    type: str
    metadata: dict[str, any]
    judgmentRatings: list[JudgementRatings]


class QuerySetQuery(BaseModel):
    queryText: str


class QuerySetResults(BaseModel):
    id: str
    name: str
    description: str
    sampling: str
    timestamp: str
    querySetQueries: list[QuerySetQuery]


class SearchConfiguration(BaseModel):
    id: str
    name: str
    timestamp: str
    index: str
    query: str
    searchPipeline: str


class Assertions:
    @staticmethod
    def get_llm_rubric_assertion_yaml(
        data: Collection[BaseModel],
        relevant_fields: Collection[str],
        field_key_to_description: dict[str, str],
        description_to_additional_values: dict[str, any],
        extra_notes: str = "",
    ):
        dicts = [x.model_dump(include=set(relevant_fields)) for x in data]
        dicts_mapped = [
            {field_key_to_description.get(key, key): value for key, value in x.items()}
            for x in dicts
        ]
        dicts_yaml_str = yaml.dump_all(dicts_mapped).replace('"', "'")
        additional_yaml_str = yaml.dump(description_to_additional_values).replace(
            '"', "'"
        )
        return f"""
        Below under the header '###SEQUENCE' a few expected results are listed in yaml format.
        Each root element in the yaml listing refers to a single result.
        The keys in the yaml format are a description of the meaning under which the
        corresponding value shall appear in the response text. If the key is a combination of
        words combined by some delimiter, try to derive the meaning from the sequence of
        words it is made of. If the key and the context under which the value is mentioned
        in the response do not match, fail the assertion.
        Under a second header '###FACTS' there might be additional key - value pairs
        to check for occurrence in the response text. Here again the key gives the context
        under which mentioning of the value is expected.
        If no key-value pairs occur in this section, then nothing is to be asserted here.
        Compare floating point values only up to the second decimal.
        Fail the test if the information provided below within both headers can not be checked
        against the response because some parts are missing. Statements such as some field
        or the response being too big and thus not being able to retrieve those also
        counts as fail. {extra_notes}

        ###SEQUENCE
        {dicts_yaml_str}

        ###FACTS
        {additional_yaml_str}
        """


class AnalysisFunctions:
    @staticmethod
    def get_worst_performing_queries_test_case():
        return TestCase(
            prompt="""
            In the following I define categories and corresponding queries that should be mentioned under each category. The response can contain more, but the below should be contained:
            a) Problematic queries with zero CTR: wirelese and 'spiderwire stealth',
            b) high-volume queries with relatively low CTR, thus with potential high impact: gold, 'wireless earbun'.
            Furthermore, the response shall contain next step suggestions including the options:
            1) generate hypotheses,
            2) analyze search results.
            """,
            assertions=[
                ContainsAssertion(
                    contains_all=True,
                    contains_texts=[
                        "wirelese",
                        "spiderwire stealth",
                        "wi",
                        "gold",
                        "wireless earbun",
                    ],
                )
            ],
        )

    @staticmethod
    def get_ubi_event_index_size_test_case():
        return TestCase(
            prompt="""
                How many events are there in the ubi_events index? Go ahead with the analysis and directly come back to me with an answer.
                """,
            assertions=[ContainsAssertion(contains_all=True, contains_texts=["3,448"])],
        )

    @staticmethod
    def get_worst_performing_queries_30_days_test_case():
        return TestCase(
            prompt="""
            What are the worst performing queries of the past 30 days? Go ahead with the analysis and directly come back to me with an answer.
            """,
            assertions=[
                ContainsAssertion(
                    contains_all=True, contains_texts=["spiderwire stealth"]
                )
            ],
        )

    @staticmethod
    def get_ask_for_query_improvement_asks_for_search_config_test_case():
        return TestCase(
            prompt="""
            Help me improve the query samsung under the current search setup.
            """,
            assertions=[
                LLMRubricAssertion(
                    eval_prompt="""
                    Response contains an ask for the search configuration or plausible suggestions
                    based on observations from tracking data and / or reference ot the hypothesis agent.
                    """
                )
            ],
        )


class ClickFunctions:
    @staticmethod
    def get_click_results_top_n(
        top_n: int = 20, time_range_days: int = 30, ubi_index: str = "ubi_events"
    ) -> Collection[ClickResult]:
        click_coroutine = get_query_performance_metrics(
            query_text=None,
            top_n=top_n,
            time_range_days=time_range_days,
            ubi_index=ubi_index,
        )
        click_result = json.loads(asyncio.run(click_coroutine))
        return [ClickResult(**x) for x in click_result["queries"]]

    @staticmethod
    def get_top_n_ctr_llm_rubric_assertion(
        data: Collection[ClickResult], total_queries_analyzed: int
    ) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=data,
            relevant_fields=tuple(
                [
                    "query_text",
                    "search_volume",
                    "searches_with_clicks",
                    "total_clicks",
                    "ctr_percentage",
                    "average_clicks_per_search",
                    "zero_click_rate_percentage",
                ]
            ),
            field_key_to_description={
                "query_text": "the user query",
                "search_volume": "total number of searches",
                "searches_with_clicks": "number of searches with clicks",
                "total_clicks": "total number of clicks",
                "ctr_percentage": "CTR in percentage, rounded to two decimals",
                "average_clicks_per_search": "average number of clicks per search for the given query",
                "zero_click_rate_percentage": "percentage of searches for the given query for which no click occurred",
            },
            description_to_additional_values={
                "Total number of queries contained in the result": total_queries_analyzed
            },
        )

    @staticmethod
    def create_top_n_ctr_test_case(
        top_n: int = 20, time_range_days: int = 30, ubi_index: str = "ubi_events"
    ) -> TestCase:
        tool_results: Collection[ClickResult] = ClickFunctions.get_click_results_top_n(
            top_n=top_n, time_range_days=time_range_days, ubi_index=ubi_index
        )
        return TestCase(
            prompt=f"""Analyze the performance of the top {top_n} results in terms of CTR. For each query, determine the following
            properties: total query volume, searches with clicks and total number of clicks. Give the average clicks per search, the
            zero click rate and ctr. The latter two give in percentages.""",
            assertions=tuple(
                [
                    ContainsAssertion(
                        contains_all=True,
                        contains_texts=flatten_lists(
                            [
                                list(x.print_representation().values())
                                for x in tool_results
                            ]
                        ),
                    ),
                    LLMRubricAssertion(
                        eval_prompt=ClickFunctions.get_top_n_ctr_llm_rubric_assertion(
                            tool_results
                        )
                    ),
                ]
            ),
        )

    @staticmethod
    def get_query_ctr_rubric_assertion(data: ClickResult) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=[data],
            relevant_fields=tuple(
                [
                    "query_text",
                    "search_volume",
                    "searches_with_clicks",
                    "total_clicks",
                    "ctr_percentage",
                    "average_clicks_per_search",
                    "zero_click_rate_percentage",
                ]
            ),
            field_key_to_description={
                "query_text": "the user query",
                "search_volume": "total number of searches",
                "searches_with_clicks": "number of searches with clicks",
                "total_clicks": "total number of clicks",
                "ctr_percentage": "CTR in percentage, rounded to two decimals",
                "average_clicks_per_search": "average number of clicks per search for the given query",
                "zero_click_rate_percentage": "percentage of searches for the given query for which no click occurred",
            },
            description_to_additional_values={},
        )

    @staticmethod
    def create_query_ctr_test_case(
        query: str, time_range_days: int = 30, ubi_index: str = "ubi_events"
    ) -> TestCase:
        query_ctr_result_json = json.loads(
            asyncio.run(
                get_query_ctr(
                    query, time_range_days=time_range_days, ubi_index=ubi_index
                )
            )
        )
        query_ctr_result_json["search_volume"] = query_ctr_result_json["total_searches"]
        query_ctr_result: ClickResult = ClickResult(**query_ctr_result_json)

        return TestCase(
            prompt=f"""Analyze the performance of the query '{query}'. Specifically, for the given query, determine the following
            properties: total query volume, searches with clicks and total number of clicks. Give the average clicks per search, the
            zero click rate and ctr. The latter two give in percentages.""",
            assertions=tuple(
                [
                    ContainsAssertion(
                        contains_all=True,
                        contains_texts=tuple(
                            [
                                format_value(query_ctr_result.search_volume),
                                format_value(query_ctr_result.searches_with_clicks),
                                format_value(query_ctr_result.total_clicks),
                                format_value(query_ctr_result.ctr_percentage),
                                format_value(query_ctr_result.average_clicks_per_search),
                                format_value(query_ctr_result.zero_click_rate_percentage)
                            ]
                        ),
                    ),
                    LLMRubricAssertion(
                        eval_prompt=ClickFunctions.get_query_ctr_rubric_assertion(
                            query_ctr_result
                        )
                    ),
                ]
            ),
        )

    @staticmethod
    def get_document_ctr_rubric_assertion(data: DocumentCTR) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=[data],
            relevant_fields=tuple(
                [
                    "document_id",
                    "total_impressions",
                    "total_clicks",
                    "ctr_percentage",
                    "average_position_when_clicked",
                ]
            ),
            field_key_to_description={
                "document_id": "id of the document",
                "total_impressions": "number of times users saw the document",
                "total_clicks": "number of times the document was clicked",
                "ctr_percentage": "CTR in percentage, rounded to two decimals",
                "average_position_when_clicked": "average position in the search result for clicks on the document",
            },
            description_to_additional_values={},
        )

    @staticmethod
    def create_document_ctr_test_case(
        doc_id: str, num_days: int = 30, index: str = "ubi_events"
    ) -> TestCase:
        result = json.loads(
            asyncio.run(
                get_document_ctr(
                    doc_id=doc_id, time_range_days=num_days, ubi_index=index
                )
            )
        )
        result = DocumentCTR(**result)
        contains_texts = tuple(
            [
                format_value(result.total_impressions),
                format_value(result.total_clicks),
                format_value(result.ctr_percentage, 2),
            ]
        )
        if result.average_position_when_clicked:
            contains_texts = tuple(
                list(contains_texts)
                + [format_value(result.average_position_when_clicked)]
            )

        return TestCase(
            prompt=f"""Analyze the performance of the product with document_id '{doc_id}'
                in the index '{index}'.
                For the given document, provide the total number of impressions, the
                total number of clicks, ctr in percentage (rounded and formatted to 2 decimals)
                and the average click position.""",
            assertions=tuple(
                [
                    ContainsAssertion(contains_all=True, contains_texts=contains_texts),
                    LLMRubricAssertion(
                        eval_prompt=ClickFunctions.get_document_ctr_rubric_assertion(
                            result
                        )
                    ),
                ]
            ),
        )

    @staticmethod
    def create_top_queries_by_engagement_test_case(
        top_n: int = 20,
        min_search_volume: int = 5,
        time_range_days: int = 30,
        ubi_index: str = "ubi_events",
    ) -> TestCase:
        result = asyncio.run(
            get_top_queries_by_engagement(
                top_n=20, min_search_volume=5, time_range_days=30, ubi_index=ubi_index
            )
        )
        result = json.loads(result)
        total_queries_analyzed: int = result["total_queries_analyzed"]
        result = [ClickResult(**x) for x in result["queries"]]
        return TestCase(
            prompt=f"""Analyze the top {top_n} queries performance by engagement
                    in the index '{ubi_index}'. Only consider queries with at least
                    {min_search_volume} searches, and over a time range of {time_range_days}
                    days. Determine the following properties per query:
                    total query volume, searches with clicks and total number of clicks,
                    average clicks per search, the zero click rate and ctr.
                    The latter two give in percentages. Also state how many queries
                    matched the above filter criteria.
                    """,
            assertions=tuple(
                [
                    ContainsAssertion(
                        contains_all=True,
                        contains_texts=flatten_lists(
                            [list(x.print_representation().values()) for x in result]
                        )
                        + [str(total_queries_analyzed)],
                    ),
                    LLMRubricAssertion(
                        eval_prompt=ClickFunctions.get_top_n_ctr_llm_rubric_assertion(
                            data=result, total_queries_analyzed=total_queries_analyzed
                        )
                    ),
                ]
            ),
        )


class ExperimentFunctions:
    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def create_experiments_last_n_overview_test_case(last_n: int) -> TestCase:
        experiments: list[ListExperimentResult] = ExperimentFunctions.get_experiments()
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
                        eval_prompt=ExperimentFunctions.get_top_n_experiments_overview_llm_rubric_assertion(
                            data=experiments
                        )
                    )
                ]
            ),
        )


class JudgementFunctions:
    @staticmethod
    def get_judgement_lists() -> list[JudgementListResults]:
        return [
            JudgementListResults(**x["_source"])
            for x in json.loads(asyncio.run(list_judgment_list()))["hits"]["hits"]
        ]

    @staticmethod
    def get_judgement_list(judgement_id: str) -> JudgementListResults:
        return JudgementListResults(
            **json.loads(asyncio.run(get_judgment(judgment_id=judgement_id)))["hits"][
                "hits"
            ][0]["_source"]
        )

    @staticmethod
    def get_most_recent_judgement_lists_llm_rubric_assertion(
        data: list[JudgementListResults],
    ) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=data,
            relevant_fields=tuple(
                ["id", "timestamp", "name", "status", "type", "judgmentRatings"]
            ),
            field_key_to_description={},
            description_to_additional_values={},
        )

    @staticmethod
    def create_judgement_list_overview_test_case(last_n: int) -> TestCase:
        results: list[JudgementListResults] = JudgementFunctions.get_judgement_lists()
        results = list(reversed(sorted(results, key=lambda x: x.timestamp)))[:last_n]
        results = [
            x.model_copy(
                update={
                    "judgmentRatings": [
                        y.model_copy(update={"ratings": y.ratings[:5]})
                        for y in x.judgmentRatings[:5]
                    ]
                }
            )
            for x in results
        ]

        return TestCase(
            prompt=f"""
                        Give me an overview of the last {last_n} most recently created judgement lists.
                        Include the following attributes per experiment: the id, timestamp, name,
                        status, type and judgement ratings. For the judgement ratings, give only examples
                        for the first 5 queries and per query the first 5 example judgements.
                        """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt=JudgementFunctions.get_most_recent_judgement_lists_llm_rubric_assertion(
                            data=results
                        )
                    )
                ]
            ),
        )

    @staticmethod
    def get_single_judgement_lists_llm_rubric_assertion(
        data: JudgementListResults,
    ) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=[data],
            relevant_fields=tuple(
                ["id", "timestamp", "name", "status", "type", "judgmentRatings"]
            ),
            field_key_to_description={},
            description_to_additional_values={},
        )

    @staticmethod
    def create_single_judgement_list_test_case() -> TestCase:
        all_judgement_lists: list[JudgementListResults] = (
            JudgementFunctions.get_judgement_lists()
        )
        last_created_list: JudgementListResults = list(
            reversed(sorted(all_judgement_lists, key=lambda x: x.timestamp))
        )[0]
        result: JudgementListResults = JudgementFunctions.get_judgement_list(
            last_created_list.id
        )
        result = result.model_copy(
            update={
                "judgmentRatings": [
                    x.model_copy(update={"ratings": x.ratings[:5]})
                    for x in result.judgmentRatings[:5]
                ]
            }
        )
        return TestCase(
            prompt="""
                   Give me an overview of the most recently created judgement list.
                   Include the following attributes per experiment: the id, timestamp, name,
                   status, type and judgement ratings. For the judgement ratings, give only examples
                   for the first 5 queries and per query the first 5 example judgements.
                   """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt=JudgementFunctions.get_single_judgement_lists_llm_rubric_assertion(
                            data=result
                        )
                    )
                ]
            ),
        )


class QuerySetAndSearchConfigFunctions:
    @staticmethod
    def get_query_sets() -> list[QuerySetResults]:
        return [
            QuerySetResults(**x["_source"])
            for x in json.loads(asyncio.run(list_query_set()))["hits"]["hits"]
        ]

    @staticmethod
    def get_query_set_by_id(id: str) -> QuerySetResults:
        return QuerySetResults(
            **json.loads(asyncio.run(get_query_set(id)))["hits"]["hits"][0]["_source"]
        )

    @staticmethod
    def get_all_search_configs() -> list[SearchConfiguration]:
        return [
            SearchConfiguration(**x["_source"])
            for x in json.loads(asyncio.run(list_search_configuration()))["hits"][
                "hits"
            ]
        ]

    @staticmethod
    def get_query_sets_llm_rubric_assertion(data: list[QuerySetResults]) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=data,
            relevant_fields=tuple(
                ["id", "name", "descriptionsampling", "timestamp", "querySetQueries"]
            ),
            field_key_to_description={},
            description_to_additional_values={},
            extra_notes="When comparing the expected query set with the result, small "
            "query sets with <= 10 elements should be listed fully in the "
            "response and reflect the expectation, while for longer lists a "
            "subsample of 10 queries is sufficient. Make sure all of those "
            "queries also appear in the listed expectation.",
        )

    @staticmethod
    def create_query_set_test_case(top_n: int) -> TestCase:
        result: list[QuerySetResults] = (
            QuerySetAndSearchConfigFunctions.get_query_sets()
        )
        result = reversed(sorted(result, key=lambda x: x.timestamp))

        return TestCase(
            prompt=f"""
                   Give me an overview of the last {top_n} most recently created query sets.
                   Include the following attributes per query set: the id, name,
                   description, timestamp and the actual query set, listing a sample
                   of 10 example queries contained in the respective query set.
                   """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt=QuerySetAndSearchConfigFunctions.get_query_sets_llm_rubric_assertion(
                            data=result
                        )
                    )
                ]
            ),
        )

    @staticmethod
    def create_query_set_by_id_test_case() -> TestCase:
        available_configs = QuerySetAndSearchConfigFunctions.get_query_sets()
        available_configs = list(
            reversed(sorted(available_configs, key=lambda x: x.timestamp))
        )[0]
        result: QuerySetResults = QuerySetAndSearchConfigFunctions.get_query_set_by_id(
            available_configs.id
        )

        return TestCase(
            prompt=f"""
                   Give me an overview of the query set with id '{result.id}'.
                   Include the following attributes per query set: the id, name,
                   description, timestamp and the actual query set. If the query set
                   contains <= 10 elements, list the queries fully, otherwise
                   list 10 example queries.
                   """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt=QuerySetAndSearchConfigFunctions.get_query_sets_llm_rubric_assertion(
                            data=[result]
                        )
                    )
                ]
            ),
        )

    @staticmethod
    def get_search_configs_llm_rubric_assertion(data: list[SearchConfiguration]) -> str:
        return Assertions.get_llm_rubric_assertion_yaml(
            data=data,
            relevant_fields=tuple(
                ["id", "name", "timestamp", "index", "query", "searchPipeline"]
            ),
            field_key_to_description={},
            description_to_additional_values={},
        )

    @staticmethod
    def create_search_configs_overview_test_case() -> TestCase:
        search_configs: list[SearchConfiguration] = (
            QuerySetAndSearchConfigFunctions.get_all_search_configs()
        )
        return TestCase(
            prompt="""
                   Give me an overview of the available search configurations.
                   Include the following attributes per query set: the id, name,
                   timestamp, index, query and search pipeline (if any).
                   """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt=QuerySetAndSearchConfigFunctions.get_search_configs_llm_rubric_assertion(
                            data=search_configs
                        )
                    )
                ]
            ),
        )

    @staticmethod
    def create_query_set_w_queries_test_case() -> TestCase:
        return TestCase(
            prompt="""
            Create a new query set with the following queries:
              laptop stand
              wireless earbuds
              hoodie
              wine glass
              rc cars
              toys for boys
              lego friends
              othoking bamboo charging station
              phone charger
              alarm clock
              karaoke microphone
              samsung
            """,
            assertions=[
                LLMRubricAssertion(
                    eval_prompt="""
                    A new query set was created with the 12 queries mentioned in the prompt.
                    """
                )
            ],
        )

    @staticmethod
    def create_search_config_w_search_fields_test_case() -> TestCase:
        return TestCase(
            prompt="""
              Create a search configuration that searches across the fields
              asin, title, category, bullet_points, description, brand, color with a multi_match
              query and call it my_baseline_2. It searches the ecommerce index.
                """,
            assertions=[
                LLMRubricAssertion(
                    eval_prompt="""
                    One new search configuration with the name 'my_baseline_2' and a multi_match
                    query across the mentioned fields targeting the ecommerce index.
                    """
                )
            ],
        )


class InvestigateFunctions:
    @staticmethod
    def create_investigate_query_improvement_by_boost_test_case(
        query: str,
        boost_field: str,
        doc_index: str = "test_doc_index",
        event_index: str = "test_event_index",
    ):
        return TestCase(
            prompt=f"""
                    Help me improve the query '{query}' in the index '{doc_index}'
                    and utilize the tracking data as available in the index '{event_index}'
                    to make informed guesses about what could improve the ranking.
                    Form a few hypothesis and test test them, and give me an overview of the
                    results. Directly proceed with the needed tests without asking.
                    For evaluations base your judgements on the observed tracking data
                    rather than LLM based judgements. Utilize the per-product CTR for this
                    purpose.
                    Here is my current DSL query:
                    POST {doc_index}/_search
                    {{
                      'query': {{
                        'multi_match': {{
                          'query': 'shoe super',
                          'fields': [
                            'asin',
                            'title',
                            'category',
                            'bullet_points',
                            'description',
                            'brand',
                            'color'
                          ]
                        }}
                      }}
                    }}
                    """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt=f"""
                                The response should contain the suggestion of applying
                                a field boost to the '{boost_field}' field and the returned experiment
                                results should confirm a positive uplift with suitable metrics
                                reflecting the result of products that show more interactions
                                as per tracking data to appear at lower positions in the
                                search result.
                                """
                    )
                ]
            ),
        )

    @staticmethod
    def create_investigate_query_improvement_by_spell_correction_test_case(
        query: str,
        doc_index: str = "test_doc_index",
        event_index: str = "test_event_index",
        query_index: str = "test_query_index",
    ):
        return TestCase(
            prompt=f"""
                        Help me improve the query '{query}' in the index '{doc_index}'
                        and utilize the tracking data as available in the index '{event_index}'
                        as well as the query data in index '{query_index}'.
                        to make informed guesses about what could improve the ranking.
                        Form a few hypothesis and test test them, and give me an overview of the
                        results. Directly proceed with the needed tests without asking.
                        For evaluations base your judgements on the observed tracking data
                        rather than LLM based judgements. Utilize the per-product CTR for this
                        purpose.
                        Here is my current DSL query:
                        POST {doc_index}/_search
                        {{
                          'query': {{
                            'multi_match': {{
                              'query': 'shoe super',
                              'fields': [
                                'asin',
                                'title',
                                'category',
                                'bullet_points',
                                'description',
                                'brand',
                                'color'
                              ]
                            }}
                          }}
                        }}
                        """,
            assertions=tuple(
                [
                    LLMRubricAssertion(
                        eval_prompt="""
                                    The response should contain the suggestions of correcting
                                    the wrongly spelled underperforming
                                    query (via spellcheck, fuzzy matching or similar techniques)
                                    to be able to use interaction
                                    information of a corrected query with higher interaction rates.
                                    The returned experiment results should confirm a
                                    positive uplift with suitable metrics
                                    reflecting that the corrected query now fixes
                                    the retrieval problem and correct products are sufaced.
                                    """
                    )
                ]
            ),
        )

    @staticmethod
    def get_multi_step_analysis_test_case_1(
        conversation_id: str = "search_opt1_thread", run_id: str = "run-1"
    ) -> Collection[TestCase]:
        """
        NOTE: multi-step evaluations are simply performed by adding multiple
        test cases (which shall be run in sequence and not parallel!)
        while keeping conversionId and runId set to same value in
        all tests that should keep previous question in context.
        :return:
        """
        return [
            TestCase(
                prompt="Find the 10 worst performing queries.",
                assertions=[
                    LLMRubricAssertion(
                        eval_prompt="""
                        In the following I define categories and corresponding queries that should be mentioned under each category. The response can contain more, but the below should be contained:
                          a) Problematic queries with zero CTR: wirelese, wirels and 'spiderwire stealth',
                          b) high-volume queries with relatively low CTR, thus with potential high impact: gold, 'wireless earbuds'.
                          Furthermore, the response shall contain next step suggestions including the options:
                          1) generate hypotheses,
                          2) analyze search results.
                        """
                    ),
                    ContainsAssertion(
                        contains_all=True,
                        contains_texts=[
                            "wirelese",
                            "wirels",
                            "spiderwire stealth",
                            "wi",
                            "gold",
                            "wireless earbuds",
                            "wireless earbun",
                        ],
                    ),
                ],
                metadata={"conversationId": conversation_id, "runId": run_id},
            ),
            TestCase(
                prompt="Identify reasons for the bad performance of the identified queries as well as strategies. List all strategies in your response. Go ahead right away with the analysis without asking for my permission.",
                assertions=[
                    LLMRubricAssertion(
                        eval_prompt="""
                            Response lists plausible reasons and corresponding strategies to resolve the issues.
                            """
                    )
                ],
                metadata={"conversationId": conversation_id, "runId": run_id},
            ),
            TestCase(
                prompt="""
                Try out the proposed strategies one by one and give a conclusive summary of the effectiveness of each.
                Limit the testing of strategies to at most the top 5 most promising.
                Go ahead right away without asking for my permission.
                """,
                assertions=[
                    LLMRubricAssertion(
                        eval_prompt="""
                        The tried out strategies are addressing the most pressing issues identified in the previous discussion. The summary of the effectiveness of each strategy lists appropriate metrics
                        and gives plausible reasoning as to which changes are the most effective.
                        The suggestions explicitly make suggestions for the handling of zero result queries and poor result quality.
                        """
                    )
                ],
                metadata={"conversationId": conversation_id, "runId": run_id},
            ),
            TestCase(
                prompt="""
                    Based on the test results for the proposed strategies, recommend the most effective and give me concrete steps to deploy the change into the test system. C
                    an you directly do this, given your toolset?
                    Go ahead right away with answering above questions without asking for my permission. Do not yet deploy the configuration.
                    """,
                assertions=[
                    LLMRubricAssertion(
                        eval_prompt="""
                            Given the scenario of a search system, ensure that the most effective are suggested and the response contains plausible strategies for bringing those changes into effect.
                            The response contains answers to the posed questions but does not yet indicate the agent has taken any action towards actually deploying the solution in the given search system.
                            """
                    )
                ],
                metadata={"conversationId": conversation_id, "runId": run_id},
            ),
        ]

    @staticmethod
    def get_samsung_query_improvement_test_case():
        return TestCase(
            prompt="""
            Help me improve the query samsung. Here is my current DSL query:
              POST ecommerce/_search
              {
                'query': {
                  'multi_match': {
                    'query': 'samsung',
                    'fields': [
                      'asin',
                      'title',
                      'category',
                      'bullet_points',
                      'description',
                      'brand',
                      'color'
                    ]
                  }
                }
              }
              Come back to me with your suggestions and already perform the needed analysis to determine the better configuration.
              Do not ask me for approval of the analysis steps. Besides the results, mention all major steps taken, such as needed configurations,
              analysis and experiments performed.
            """,
            assertions=[
                LLMRubricAssertion(
                    eval_prompt="""
                    Different search configurations are created, and are compared both with an offline as well as with an online evaluation.
                    Offline and online evaluation results are clearly presented and agreement and / or disagreement of results of both
                    are clearly highlighted. The response wraps up with a clear recommendation, supported by appropriate data to support it.
                    """
                )
            ],
        )

    @staticmethod
    def get_field_boost_offline_eval_test_case():
        return TestCase(
            prompt="""
            Run offline evaluation to compare the search configurations for three different, promising field boosts.
            Use query set consisting of the queries: samsung, apple, nike.
            Select the most promising boost candidates yourself and come back to me with the result.
            Do not ask for permission to perform the required analysis steps.
            """,
            assertions=[
                LLMRubricAssertion(
                    eval_prompt="""
                        Three pointwise experiments are created, one for each search configuration. Results are compared to each
                        other and a winner reported back to the user.
                        """
                )
            ],
        )

    @staticmethod
    def get_search_config_copy_and_adjust_test_case():
        return TestCase(
            prompt="""
              Try to find the search configuration with name 'my_baseline'.
              In case it does not yet exist, please create it with the following configuration:

              {
                '_index': 'search-relevance-search-config',
                '_source': {
                  'name': 'my_baseline',
                  'index': 'ecommerce',
                  'query': {\n  'query': {\n    'multi_match': {\n      'query': '%SearchText%',\n      'fields': [\n        'asin',\n        'title',\n        'category',\n        'bullet_points',\n        'description',\n        'brand',\n        'color'\n      ]\n    }\n  }\n},
                }
              }

              Create a search configuration similar to 'my_baseline'
              but with a title boost of 5 and a brand boost of 3.
              Then run a pairwise comparison with these search configurations for the query
              samsung.
                """,
            assertions=[
                LLMRubricAssertion(
                    eval_prompt="""
                    One new search configuration based on the reference with field boosts.
                    Pairwise experiment created, run and results reported.
                    """
                )
            ],
        )


def build_test_suite_fast():
    return TestSuite(
        name="Fast Test Suite",
        description="Faster tests involving basic analysis / creation cases involving basic"
        " tool usage, yet without more involved analysis cases.",
        cases=tuple(
            [
                ClickFunctions.create_query_ctr_test_case(
                    "laptop", time_range_days=30, ubi_index="ubi_events"
                ),
                ClickFunctions.create_query_ctr_test_case(
                    "wireless earbuds", time_range_days=30, ubi_index="ubi_events"
                ),
                ClickFunctions.create_query_ctr_test_case(
                    "gold", time_range_days=30, ubi_index="ubi_events"
                ),
                ClickFunctions.create_document_ctr_test_case(
                    doc_id="B07ZCRSVBB", num_days=30, index="ubi_events"
                ),
                ClickFunctions.create_top_queries_by_engagement_test_case(
                    top_n=20,
                    min_search_volume=5,
                    time_range_days=30,
                    ubi_index="ubi_events",
                ),
                ExperimentFunctions.create_experiments_last_n_overview_test_case(
                    last_n=10
                ),
                JudgementFunctions.create_single_judgement_list_test_case(),
                JudgementFunctions.create_judgement_list_overview_test_case(last_n=4),
                QuerySetAndSearchConfigFunctions.create_query_set_test_case(top_n=5),
                QuerySetAndSearchConfigFunctions.create_search_configs_overview_test_case(),
                QuerySetAndSearchConfigFunctions.create_query_set_by_id_test_case(),
                ClickFunctions.create_top_queries_by_engagement_test_case(
                    top_n=20,
                    min_search_volume=5,
                    time_range_days=30,
                    ubi_index="test_event_index",
                ),
                # low ctr case
                ClickFunctions.create_document_ctr_test_case(
                    doc_id="shoe_low1", num_days=30, index="test_event_index"
                ),
                # high ctr case
                ClickFunctions.create_document_ctr_test_case(
                    doc_id="shoe_high1", num_days=30, index="test_event_index"
                ),
                # low ctr case
                ClickFunctions.create_document_ctr_test_case(
                    doc_id="trousers_green_low1", num_days=30, index="test_event_index"
                ),
                # high ctr case
                ClickFunctions.create_document_ctr_test_case(
                    doc_id="trousers_green_high1", num_days=30, index="test_event_index"
                ),
                AnalysisFunctions.get_ubi_event_index_size_test_case(),
                AnalysisFunctions.get_worst_performing_queries_30_days_test_case(),
                AnalysisFunctions.get_worst_performing_queries_test_case(),
                AnalysisFunctions.get_ask_for_query_improvement_asks_for_search_config_test_case(),
                QuerySetAndSearchConfigFunctions.create_query_set_w_queries_test_case(),
                QuerySetAndSearchConfigFunctions.create_search_config_w_search_fields_test_case(),
            ]
        ),
    )


def build_test_suite_slow():
    return TestSuite(
        name="Slow Test Suite",
        description="More involved cases combining steps of analysis, hypothesis and validation.",
        cases=tuple(
            [
                InvestigateFunctions.create_investigate_query_improvement_by_boost_test_case(
                    query="shoe super",
                    doc_index="test_doc_index",
                    event_index="test_event_index",
                    boost_field="brand",
                ),
                InvestigateFunctions.create_investigate_query_improvement_by_boost_test_case(
                    query="sweet trousers green",
                    doc_index="test_doc_index",
                    event_index="test_event_index",
                    boost_field="color",
                ),
                InvestigateFunctions.create_investigate_query_improvement_by_spell_correction_test_case(
                    query="ninhendo swithc",
                    doc_index="test_doc_index",
                    event_index="test_event_index",
                    query_index="test_query_index",
                ),
                InvestigateFunctions.get_samsung_query_improvement_test_case(),
                InvestigateFunctions.get_field_boost_offline_eval_test_case(),
                InvestigateFunctions.get_search_config_copy_and_adjust_test_case(),
            ]
            + list(
                InvestigateFunctions.get_multi_step_analysis_test_case_1(
                    conversation_id="search_opt1_thread", run_id="run-1"
                )
            )
        ),
    )


def get_promptfoo_config_from_csv_cases(timeout: int = 300000) -> str:
    return f"""
description: "Config for tests from csv file"

providers:
  - id: 'file://../../../agent_request.py'
    label: 'Orchestrator invocation'
    config:
      timeout: {timeout}

defaultTest:
  options:
    provider:
      id: bedrock:us.anthropic.claude-3-5-sonnet-20241022-v2:0
      config:
        region: us-east-1
        max_tokens: 256

tests: file://tests.csv
    """


if __name__ == "__main__":
    # we are just calling here such that global object is set with the right credentials
    # NOTE that the client manager will have the url and credentials set
    # on the first call, all subsequent calls just reuse the same object
    # (if the global object is not cleared)
    load_dotenv(f"{script_path}/../../../../.env")
    get_client_manager(
        opensearch_url=os.environ["TEST_GEN_OPENSEARCH_URL"],
        username=os.environ["TEST_GEN_OPENSEARCH_USERNAME"],
        password=os.environ["TEST_GEN_OPENSEARCH_PASSWORD"],
    )
    test_suite_fast = build_test_suite_fast()
    test_suite_slow = build_test_suite_slow()

    fast_test_path = f"{script_path}/../../../test_cases/functional/fast"
    slow_test_path = f"{script_path}/../../../test_cases/functional/slow"

    test_suite_fast.write(f"{fast_test_path}/tests.csv")
    with open(f"{fast_test_path}/eval.yaml", "w") as f:
        f.write(get_promptfoo_config_from_csv_cases(300000))
    test_suite_slow.write(f"{slow_test_path}/tests.csv")
    with open(f"{slow_test_path}/eval.yaml", "w") as f:
        f.write(get_promptfoo_config_from_csv_cases(3000000))
