import logging
import os
from concurrent.futures import ProcessPoolExecutor
from typing import List

import pandas as pd
from datetimerange import DateTimeRange
from numpy import nan
from wittgenstein.abstract_ruleset_classifier import AbstractRulesetClassifier

from knockout_ios.utils.constants import globalColumnNames

import swifter

from knockout_ios.utils.custom_exceptions import KnockoutMetricsException


def find_rejection_rates(log_df, ko_activities):
    # for every ko_activity,
    # P = how many cases were knocked out by it / how many cases contain it
    knock_out_counts_by_activity = log_df.drop_duplicates(subset=globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME) \
        .groupby('knockout_activity') \
        .count()[globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME]

    rates = {}
    for activity in ko_activities:
        cases_knocked_out_by_activity = knock_out_counts_by_activity.get(activity, 0)

        # count how many cases in log_df contain the activity
        filt = log_df[log_df[globalColumnNames.SIMOD_LOG_READER_ACTIVITY_COLUMN_NAME] == activity]
        cases_containing_activity = filt[globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME].unique().shape[0]

        if cases_containing_activity == 0:
            rates[activity] = 0
        else:
            rejection_rate = cases_knocked_out_by_activity / cases_containing_activity
            rates[activity] = rejection_rate

    return rates


def get_ko_discovery_metrics(activities, expected_kos, computed_kos):
    # Source: https://towardsdatascience.com/evaluating-categorical-models-e667e17987fd

    total_observations = len(activities)

    if total_observations == 0:
        raise KnockoutMetricsException("No ko_activities provided")

    # Compute components of metrics

    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0

    for act in activities:
        if (act not in computed_kos) and not (act in expected_kos):
            true_negatives += 1
        elif (act not in computed_kos) and (act in expected_kos):
            false_negatives += 1

    for ko in computed_kos:
        if ko in expected_kos:
            true_positives += 1
        else:
            false_positives += 1

    # Compute metrics, with care for divisions by zero

    accuracy = (true_positives + true_negatives) / total_observations

    if (true_positives + false_positives) == 0:
        precision = 1
    else:
        precision = true_positives / (true_positives + false_positives)

    if (true_positives + false_negatives) == 0:
        recall = 1
    else:
        recall = true_positives / (true_positives + false_negatives)

    if (precision + recall) == 0:
        f1_score = nan
    else:
        f1_score = 2 * ((precision * recall) / (precision + recall))

    return {'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score,
            'confusion_matrix': {
                'true_positives': true_positives,
                'false_positives': false_positives,
                'true_negatives': true_negatives,
                'false_negatives': false_negatives
            }}


def calc_knockout_ruleset_support(activity: str, ruleset_model: AbstractRulesetClassifier, log: pd.DataFrame,
                                  available_cases_before_ko: int):
    # Support: The percentage of instances to which the condition of a rule applies
    # Source: https://christophm.github.io/interpretable-ml-book/rules.html#rules

    predicted_ko = ruleset_model.predict(log)
    log['predicted_ko'] = predicted_ko

    # Find for how many cases, the knock-out condition holds (it doesn't matter whether the prediction is correct)
    true_positives = log[log['predicted_ko']].shape[0]

    if available_cases_before_ko == 0:
        return 0

    support = true_positives / available_cases_before_ko

    return support


def calc_knockout_ruleset_confidence(activity: str, ruleset_model: AbstractRulesetClassifier, log: pd.DataFrame):
    # Confidence: how accurate the rule is in predicting the correct class for the instances to which the condition of the rule applies
    # Source: https://christophm.github.io/interpretable-ml-book/rules.html#rules

    predicted_ko = ruleset_model.predict(log)
    log['predicted_ko'] = predicted_ko

    # Find for how many cases, the knock-out condition holds and the prediction matches the ground truth
    true_positives = log[(log['predicted_ko']) & (log['knockout_activity'] == activity)].shape[0]
    predicted_positives = sum(predicted_ko)

    if predicted_positives == 0:
        return 0

    confidence = true_positives / predicted_positives

    return confidence


def calc_available_cases_before_ko(ko_activities: List[str], log_df: pd.DataFrame):
    counts = {}

    for activity in ko_activities:
        filt = log_df[log_df[globalColumnNames.SIMOD_LOG_READER_ACTIVITY_COLUMN_NAME] == activity]
        cases_containing_activity = filt[globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME].unique().shape[0]
        counts[activity] = cases_containing_activity

    return counts


def calc_processing_waste(ko_activities: List[str], log_df: pd.DataFrame):
    counts = {}

    # Approximation, only adding durations of all ko_activities of knocked out cases per ko activity.
    # does not take into account idle time due to resource timetables
    for activity in ko_activities:
        filtered_df = log_df[log_df['knockout_activity'] == activity]
        # keep only activities different from the one that knocked out the case
        filtered_df = filtered_df[filtered_df[globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME] != activity]
        total_duration = filtered_df[globalColumnNames.DURATION_COLUMN_NAME].sum()
        counts[activity] = total_duration

    return counts


def calc_overprocessing_waste(ko_activities: List[str], log_df: pd.DataFrame):
    counts = {}

    # Basic Cycle time calculation: end time of last activity of a case - start time of first activity of a case
    # Not counting the activity that knocked out the case
    for activity in ko_activities:
        filtered_df = log_df[log_df['knockout_activity'] == activity]
        # keep only activities different from the one that knocked out the case
        filtered_df = filtered_df[filtered_df[globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME] != activity]
        aggr = filtered_df.groupby(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME).agg(
            {globalColumnNames.PM4PY_START_TIMESTAMP_COLUMN_NAME: 'min',
             globalColumnNames.PM4PY_END_TIMESTAMP_COLUMN_NAME: 'max'})
        total_duration = aggr[globalColumnNames.PM4PY_END_TIMESTAMP_COLUMN_NAME] - aggr[
            globalColumnNames.PM4PY_START_TIMESTAMP_COLUMN_NAME]

        counts[activity] = total_duration.sum().total_seconds()

    return counts


def calc_waiting_time_waste(ko_activities: List[str], log_df: pd.DataFrame):
    waste = {activity: 0 for activity in ko_activities}

    if not (globalColumnNames.PM4PY_RESOURCE_COLUMN_NAME in log_df.columns):
        print("The log does not contain resources")
        return waste

    log_df = log_df.sort_values(by=[globalColumnNames.SIMOD_START_TIMESTAMP_COLUMN_NAME])
    log_df.set_index(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME, inplace=True)

    for caseid in log_df.index.unique():
        log_df.loc[caseid, "next_activity_start"] = \
            (log_df.loc[caseid][globalColumnNames.PM4PY_START_TIMESTAMP_COLUMN_NAME]).shift(-1)

    log_df.reset_index(inplace=True)

    non_knocked_out_case_events = log_df[log_df['knockout_activity'] == False]

    disable_parallelization = os.getenv('DISABLE_PARALLELIZATION', False)

    if disable_parallelization:
        logging.info("Parallelization disabled for waiting time waste calculation")

        for activity in ko_activities:
            result = do_waiting_time_waste_calc(log_df, non_knocked_out_case_events, activity, True)
            waste[result["activity"]] = result["waste"]
    else:
        logging.info("Computing waiting time waste in parallel")

        with ProcessPoolExecutor() as executor:
            futures = []
            for activity in ko_activities:
                futures.append(
                    executor.submit(do_waiting_time_waste_calc, log_df, non_knocked_out_case_events, activity,
                                    False))

            for future in futures:
                result = future.result()
                waste[result["activity"]] = result["waste"]

    return waste


def do_waiting_time_waste_calc(log_df, non_knocked_out_case_events, activity, disable_parallelization):
    waste = 0

    # consider only events knocked out by the current activity
    knocked_out_case_events = log_df[log_df['knockout_activity'] == activity]

    for resource in knocked_out_case_events[globalColumnNames.PM4PY_RESOURCE_COLUMN_NAME].unique():
        if pd.isnull(resource):
            continue

        # consider only events that share the same resource
        knocked_out = knocked_out_case_events[
            knocked_out_case_events[globalColumnNames.PM4PY_RESOURCE_COLUMN_NAME] == resource]
        non_knocked_out = non_knocked_out_case_events[
            non_knocked_out_case_events[globalColumnNames.PM4PY_RESOURCE_COLUMN_NAME] == resource]

        # find indexes of columns in non_knocked_out, for an apply() call later using the 'raw' flag
        end_timestamp_index = non_knocked_out.columns.get_loc(globalColumnNames.PM4PY_END_TIMESTAMP_COLUMN_NAME)
        next_activity_start_index = non_knocked_out.columns.get_loc("next_activity_start")

        # find indexes of columns in knocked_out, for an apply() call later using the 'raw' flag
        start_timestamp_index = knocked_out.columns.get_loc(globalColumnNames.PM4PY_START_TIMESTAMP_COLUMN_NAME)
        ko_end_timestamp_index = knocked_out.columns.get_loc(globalColumnNames.PM4PY_END_TIMESTAMP_COLUMN_NAME)

        def compute_overlaps(non_ko_case_event):

            # handle these cases:
            # - value of NaT in last activity of every case
            # - cases with no "idle time" between its ko_activities

            if (pd.isnull(non_ko_case_event[next_activity_start_index])) or (
                    non_ko_case_event[next_activity_start_index] <= non_ko_case_event[end_timestamp_index]):
                return 0

            # Get the overlapping time between idle intervals of non_ko_case_event and knocked out cases

            idle_time = DateTimeRange(
                non_ko_case_event[end_timestamp_index],
                non_ko_case_event[next_activity_start_index]
            )

            def compute_intersections_with_non_ko_case_event(knocked_out_case_event):
                time_range2 = DateTimeRange(
                    knocked_out_case_event[start_timestamp_index],
                    knocked_out_case_event[ko_end_timestamp_index]
                )

                try:
                    return idle_time.intersection(time_range2).timedelta.total_seconds()
                except TypeError:  # like this we save up 1 call to is_intersection()
                    return 0

            total_overlap = knocked_out.apply(compute_intersections_with_non_ko_case_event, axis=1, raw=True)

            return total_overlap.sum()

        overlaps = non_knocked_out.apply(compute_overlaps, axis=1, raw=True)

        waste += overlaps.sum()

    return {"activity": activity, "waste": waste}
