from datetime import UTC, datetime, timedelta
import os
import logging

import asciichartpy as asciichart
from azure.identity import DefaultAzureCredential

from common.config import (
    tenant_id,
    subscription_id,
    resource_group_name,
    log_analytics_workspace_id,
    log_analytics_workspace_name,
)

from common.log_analytics import QueryProcessor, Table

logging.basicConfig(level=logging.INFO)
logging.getLogger("azure").setLevel(logging.WARNING)


start_time_string = os.getenv("TEST_START_TIME")
stop_time_string = os.getenv("TEST_STOP_TIME")

test_start_time = datetime.strptime(start_time_string, "%Y-%m-%dT%H:%M:%SZ")
test_stop_time = datetime.strptime(stop_time_string, "%Y-%m-%dT%H:%M:%SZ")

print(f"test_start_time  : {test_start_time}")
print(f"test_end_time    : {test_stop_time}")


metric_check_time = test_stop_time - timedelta(seconds=40)  # detecting the end of the test can take 30s, add 10s buffer

query_processor = QueryProcessor(
    workspace_id=log_analytics_workspace_id,
    token_credential=DefaultAzureCredential(),
    tenant_id=tenant_id,
    subscription_id=subscription_id,
    resource_group_name=resource_group_name,
    workspace_name=log_analytics_workspace_name,
)

print(f"metric_check_time: {metric_check_time}")
check_results_query = f"""
AppMetrics
| where TimeGenerated >= datetime({metric_check_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
	and Name == "locust.request_latency"
| count
"""
query_processor.wait_for_non_zero_count(check_results_query)

timespan = (datetime.now(UTC) - timedelta(days=1), datetime.now(UTC))


####################################################################
# Ensure the base latency remains low with rate-limiting in place
#


def validate_request_latency(table: Table):
    mean_latency = table.rows[0][0]
    if mean_latency > 10:
        return f"Mean latency is too high: {mean_latency}"
    return None


query_processor.add_query(
    title="Base Latency",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max)
| project mean_latency_ms=1000*Sum/Count, max_latency_ms=1000*Max
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_request_latency,
)


####################################################################
# Ensure the rate-limiting allows the expected number of requests per second
#


def validate_mean_sucess_rps(table: Table):
    # Check if the mean RPS is within the expected range
    # The deployment for the tests has 100,000 Tokens Per Minute (TPM) limit
    # That equates to 600 Requests Per Minute (RPM) or 10 Requests Per Second (RPS)
    mean_rps = int(table.rows[0][0])
    low_value = 9
    high_value = 11
    if mean_rps > high_value:
        return f"Mean RPS is too high: {mean_rps} (expected between {low_value} and {high_value})"
    if mean_rps < low_value:
        return f"Mean RPS is too low: {mean_rps} (expected between {low_value} and {high_value})"
    return None


query_processor.add_query(
    title="Mean RPS (successful requests)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| extend status_code = Properties["status_code"]
| where status_code == 200
| summarize RPS = sum(ItemCount)/60.0 by bin(TimeGenerated, 1m)
| summarize avg(RPS)
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_mean_sucess_rps,
)


####################################################################
# Ensure that we _do_ get 429 responses as expected
#


def validate_429_count(table: Table):
    # With the level of user load targetting the deployment, we expect a high number of 429 responses
    number_of_429_responses = table.rows[0][0]
    if number_of_429_responses < 100:
        return f"The number of 429 responses is too low: {number_of_429_responses}"
    return None


query_processor.add_query(
    title="Number of 429 responses (should be high)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| extend status_code = Properties["status_code"]
| where status_code == 429
| summarize ItemCount=sum(ItemCount)
""".strip(),
    timespan=timespan,
    show_query=True,
    include_link=True,
    validation_func=validate_429_count,
)


####################################################################
# Show the RPS over time
#

query_processor.add_query(
    title="RPS over time (successful - yellow, 429 - blue)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| extend status_code = tostring(Properties["status_code"])
| summarize rps = sum(ItemCount)/10 by bin(TimeGenerated, 10s), status_code
| project TimeGenerated, rps, status_code
| evaluate pivot(status_code, sum(rps))
| render timechart 
""".strip(),
    is_chart=True,
    columns=["200", "429"],
    chart_config={
        "height": 15,
        "min": 0,
        "colors": [
            asciichart.yellow,
            asciichart.blue,
        ],
    },
    timespan=timespan,
    show_query=True,
    include_link=True,
)
# query_processor.add_query(
#     title="RPS over time",
#     query=f"""
# AppMetrics
# | where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
#     and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
#     and Name == "aoai-simulator.latency.base"
# | summarize RPS = sum(ItemCount)/10 by bin(TimeGenerated, 10s)
# | project TimeGenerated, RPS
# """.strip(),
#     is_chart=True,
#     columns=["RPS"],
#     chart_config={
#         "height": 15,
#         "min": 0,
#         "colors": [
#             asciichart.yellow,
#         ],
#     },
#     timespan=timespan,
#     show_query=True,
#     include_link=True,
# )


####################################################################
# Show the RPS over time
#

query_processor.add_query(
    title="Latency (base) over time in ms (mean - yellow, max - blue)",
    query=f"""
AppMetrics
| where TimeGenerated >= datetime({test_start_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and TimeGenerated <= datetime({test_stop_time.strftime('%Y-%m-%dT%H:%M:%SZ')})
    and Name == "aoai-simulator.latency.base"
| summarize Sum=sum(Sum),  Count = sum(ItemCount), Max=max(Max) by bin(TimeGenerated, 10s)
| project TimeGenerated, mean_latency_ms=1000*Sum/Count, max_latency_ms=1000*Max
| render timechart
""".strip(),
    is_chart=True,
    columns=["mean_latency_ms", "max_latency_ms"],
    chart_config={
        "height": 15,
        "min": 0,
        "colors": [
            asciichart.yellow,
            asciichart.blue,
        ],
    },
    timespan=timespan,
    show_query=True,
    include_link=True,
)


query_errors = query_processor.run_queries()

if query_errors:
    exit(1)
