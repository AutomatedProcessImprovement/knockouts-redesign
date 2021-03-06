# Knockout ko_activities discovery modes:
#
# - automatic: program considers characteristic ko_activities of top available_cases_before_ko shortest variants as
#                             knock-out-check ko_activities
#
# - semi-automatic: user provides activity name(s) associated to negative case outcome(s),
#                                  program uses that info to refine analysis and find knock-out-check ko_activities.
#
# - manual: user provides names of knock-out-check ko_activities


import os
import pprint
import sys

import pandas as pd
import pm4py
from tqdm import tqdm

from knockout_ios.utils.constants import globalColumnNames
from knockout_ios.utils.custom_exceptions import ConfigNotLoadedException, KnockoutsDiscoveryException, \
    LogNotLoadedException, EmptyKnockoutActivitiesException
from knockout_ios.utils.discovery import discover_ko_sequences
from knockout_ios.utils.metrics import get_ko_discovery_metrics
from knockout_ios.utils.formatting import format_for_post_proc, plot_cycle_times_per_ko_activity, \
    plot_ko_activities_count
from knockout_ios.utils.preprocessing.configuration import read_log_and_config, Configuration


class KnockoutDiscoverer:

    def __init__(self, log_df: pd.DataFrame, config: Configuration, config_file_name: str,
                 cache_dir="cache",
                 config_dir="config",
                 always_force_recompute=True,
                 quiet=False
                 ):

        # TODO: refactor the need for config_dir, cache_dir...

        os.makedirs(cache_dir, exist_ok=True)

        self.config_dir = config_dir
        self.cache_dir = cache_dir
        self.config_file_name = config_file_name
        self.always_force_recompute = always_force_recompute
        self.quiet = quiet

        self.ko_seqs = None
        self.ko_outcomes = None
        self.ko_activities = None
        self.force_recompute = None
        self.ko_rules_classifiers = None

        self.log_df = log_df
        self.config = config

        self.force_recompute = True

    def find_ko_activities(self):

        if self.config is None:
            raise ConfigNotLoadedException

        if self.config.ko_count_threshold is None:
            ko_count_threshold = len(self.log_df[globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME].unique())
        else:
            ko_count_threshold = self.config.ko_count_threshold

        self.ko_activities, self.ko_outcomes, _ = discover_ko_sequences(self.log_df,
                                                                        self.config_file_name,
                                                                        cache_dir=self.cache_dir,
                                                                        start_activity_name=self.config.start_activity,
                                                                        known_ko_activities=self.config.known_ko_activities,
                                                                        post_knockout_activities=self.config.post_knockout_activities,
                                                                        success_activities=self.config.success_activities,
                                                                        limit=ko_count_threshold,
                                                                        quiet=self.quiet,
                                                                        force_recompute=self.force_recompute)

        # remove start and end activities from ko activities if present
        self.ko_activities = [x for x in self.ko_activities if x != self.config.start_activity]
        self.ko_activities = [x for x in self.ko_activities if x != self.config.end_activity]

        # Do not consider known negative outcomes as ko_activities
        if len(self.config.post_knockout_activities) > 0:
            self.ko_activities = list(filter(lambda act: not (act in self.config.post_knockout_activities),
                                             self.ko_activities))

        # Exclude any activities that are explicitly indicated
        if (not (self.config.exclude_from_ko_activities is None)) and (len(self.config.exclude_from_ko_activities) > 0):
            self.ko_activities = list(filter(lambda act: not (act in self.config.exclude_from_ko_activities),
                                             self.ko_activities))

        if (len(self.ko_outcomes) == 0) or (len(self.ko_activities) == 0):
            raise KnockoutsDiscoveryException("Error finding knockouts")

        try:
            if self.force_recompute:
                raise FileNotFoundError

            self.log_df = pd.read_pickle(f"./{self.cache_dir}/{self.config_file_name}_with_knockouts.pkl")
            if not self.quiet:
                print(f"\nFound cache for {self.config_file_name} knockouts\n")

        except FileNotFoundError:

            if len(self.config.post_knockout_activities) > 0:
                self.ko_outcomes = self.config.post_knockout_activities
                relations = list(map(lambda ca: (self.config.start_activity, ca), self.config.post_knockout_activities))
                rejected = pm4py.filter_eventually_follows_relation(self.log_df, relations)
            elif len(self.config.success_activities) > 0:
                self.ko_outcomes = self.config.success_activities
                relations = list(map(lambda ca: (self.config.start_activity, ca), self.config.success_activities))
                rejected = pm4py.filter_eventually_follows_relation(self.log_df, relations, retain=False)
            else:
                # if no negative outcomes are provided, assume knocked-out cases go directly to the end activity
                self.ko_outcomes = [self.config.end_activity]
                relations = list(map(lambda check: (check, self.config.end_activity), self.ko_activities))
                rejected = pm4py.filter_directly_follows_relation(self.log_df, relations)

            rejected = pm4py.convert_to_dataframe(rejected)

            # Mark Knocked-out cases & their knock-out activity
            self.log_df['knocked_out_case'] = False
            self.log_df['knockout_activity'] = False

            def find_ko_activity(_ko_activities, _sorted_case):
                case_activities = list(_sorted_case[globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME].values)

                try:
                    # drop activites after the known negative outcomes
                    for outcome in self.ko_outcomes:
                        if outcome in case_activities and (case_activities.index(outcome) < len(case_activities)):
                            case_activities = case_activities[:case_activities.index(outcome) + 1]

                    # reverse case activities and return the first knockout activity that appears
                    case_activities.reverse()
                    for activity in case_activities:
                        if activity in _ko_activities:
                            return activity
                except:
                    return False

            gr = rejected.groupby(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME)

            self.log_df.set_index(globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME, inplace=True)

            for group in tqdm(gr.groups.keys(), desc="Marking knocked-out cases in log"):
                case_df = gr.get_group(group)
                sorted_case = case_df.sort_values(by=globalColumnNames.SIMOD_END_TIMESTAMP_COLUMN_NAME)
                knockout_activity = find_ko_activity(self.ko_activities, sorted_case)

                self.log_df.at[group, 'knocked_out_case'] = True
                self.log_df.at[group, 'knockout_activity'] = knockout_activity

            self.log_df.reset_index(inplace=True)

            self.log_df.to_pickle(f"./{self.cache_dir}/{self.config_file_name}_with_knockouts.pkl")

        self.ko_activities = list(filter(lambda act: act, set(self.log_df['knockout_activity'])))

        # Throw error when no KOs are distinguished (all cases are considered 'knocked out')
        # Ask user for more info
        if self.log_df['knocked_out_case'].all():
            raise KnockoutsDiscoveryException("No K.O. ko_activities could be distinguished."
                                              "\n\nSuggestions:"
                                              "\n- Provide negative outcome activity name(s)"
                                              "\n- Provide positive outcome activity name(s)")

        if not self.quiet:
            print(f"\nPost K.O. activities found in log: {list(self.ko_outcomes)}"
                  f"\nK.O. activities found in log: {list(self.ko_activities)}")

    def label_cases_with_known_ko_activities(self, ko_activities):

        if self.config is None:
            raise ConfigNotLoadedException("pipeline_config not yet loaded")

        self.ko_activities = ko_activities

        try:
            if self.force_recompute:
                raise FileNotFoundError

            self.log_df = pd.read_pickle(f"./{self.cache_dir}/{self.config_file_name}_with_knockouts.pkl")
            if not self.quiet:
                print(f"\nFound cache for {self.config_file_name} knockouts\n")

        except FileNotFoundError:

            if len(self.config.post_knockout_activities) > 0:
                self.ko_outcomes = self.config.post_knockout_activities
                relations = list(map(lambda ca: (self.config.start_activity, ca), self.config.post_knockout_activities))
                rejected = pm4py.filter_eventually_follows_relation(self.log_df, relations)
            elif len(self.config.success_activities) > 0:
                self.ko_outcomes = self.config.success_activities
                relations = list(map(lambda ca: (self.config.start_activity, ca), self.config.success_activities))
                rejected = pm4py.filter_eventually_follows_relation(self.log_df, relations, retain=False)
            else:
                # assume knocked-out cases go directly to the end activity
                self.ko_outcomes = [self.config.end_activity]
                relations = list(map(lambda check: (check, self.config.end_activity), self.ko_activities))
                rejected = pm4py.filter_directly_follows_relation(self.log_df, relations)

            rejected = pm4py.convert_to_dataframe(rejected)

            # Mark Knocked-out cases & their knock-out activity
            self.log_df['knocked_out_case'] = False
            self.log_df['knockout_activity'] = False

            def find_ko_activity(_ko_activities, _sorted_case):
                case_activities = list(_sorted_case[globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME].values)

                try:
                    # drop activites after the known negative outcomes
                    for outcome in self.ko_outcomes:
                        if outcome in case_activities and (case_activities.index(outcome) < len(case_activities)):
                            case_activities = case_activities[:case_activities.index(outcome) + 1]

                    # reverse case activities and return the first knockout activity that appears
                    case_activities.reverse()
                    for activity in case_activities:
                        if activity in _ko_activities:
                            return activity
                except:
                    return False

            gr = rejected.groupby(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME)

            self.log_df.set_index(globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME, inplace=True)

            for group in tqdm(gr.groups.keys(), desc="Marking knocked-out cases in log"):
                case_df = gr.get_group(group)
                sorted_case = case_df.sort_values(by=globalColumnNames.SIMOD_END_TIMESTAMP_COLUMN_NAME)
                knockout_activity = find_ko_activity(self.ko_activities, sorted_case)

                self.log_df.at[group, 'knocked_out_case'] = True
                self.log_df.at[group, 'knockout_activity'] = knockout_activity

            self.log_df.reset_index(inplace=True)

            self.log_df.to_pickle(f"./{self.cache_dir}/{self.config_file_name}_with_knockouts.pkl")

        self.ko_activities = list(filter(lambda act: act, set(self.log_df['knockout_activity'])))

        # Throw error when no KOs are distinguished (all cases are considered 'knocked out')
        # Ask user for more info
        if self.log_df['knocked_out_case'].all():
            raise KnockoutsDiscoveryException("No K.O. ko_activities could be distinguished."
                                              "\n\nSuggestions:"
                                              "\n- Provide negative outcome activity name(s)"
                                              "\n- Provide positive outcome activity name(s)")

    def print_basic_stats(self):
        # Basic impact assessment
        # See processing time distributions for cases that have the knockout and end in negative end
        # vs. cases that don't get knockout out but have negative end

        if self.log_df is None:
            raise LogNotLoadedException("log not yet processed")

        aggregated_df = format_for_post_proc(self.log_df)

        plot_cycle_times_per_ko_activity(aggregated_df, self.ko_activities)
        plot_ko_activities_count(aggregated_df)

    def get_activities(self):
        return list(set(self.log_df[globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME]))

    def get_discovery_metrics(self, expected_kos):

        if self.ko_activities is None:
            raise EmptyKnockoutActivitiesException("ko ko_activities not yet computed")

        return get_ko_discovery_metrics(self.get_activities(), expected_kos, self.ko_activities)


if __name__ == "__main__":
    test_data = (
        "synthetic_example_enriched.json",
        ['Assess application', 'Check Liability', 'Check Monthly Income', 'Check Risk'])

    log, configuration = read_log_and_config("test/config", "synthetic_example_enriched.json",
                                             "cache/synthetic_example_enriched")

    analyzer = KnockoutDiscoverer(log_df=log, config=configuration, config_file_name=test_data[0],
                                  cache_dir="cache/synthetic_example",
                                  always_force_recompute=True, quiet=False)

    analyzer.find_ko_activities()
    analyzer.print_basic_stats()
    pprint.pprint(analyzer.get_discovery_metrics(test_data[1]))
