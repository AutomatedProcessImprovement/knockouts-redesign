import pickle

import pandas as pd
from tabulate import tabulate

from knockout_ios.knockout_analyzer import KnockoutAnalyzer
from knockout_ios.utils.formatting import get_edits_string
from knockout_ios.utils.preprocessing.configuration import read_log_and_config
from knockout_ios.utils.constants import globalColumnNames

from knockout_ios.utils.redesign import evaluate_knockout_relocation_io, \
    evaluate_knockout_rule_change_io, evaluate_knockout_reordering_io, find_ko_activity_dependencies, \
    evaluate_knockout_reordering_io

'''
KO redesign strategies

1. Relocate a knock-out
   place the knock-out check as early in the process as the attribute value (based on which the knock-out is performed)
   is available.

2. Reorder knock-outs
   according to the knock-out principle:
   checks are ordered according to the principle of “least effort to reject”– checks that require less effort and are more
   likely to reject the case come first. In addition, consider the knock-out rule so that the attribute value (based on which
   the knock-out is performed) is available at that point in the process.

3. Change the knock-out rule
   change the attribute value (or its range) based on which the knock-out is performed;

NOT IN CURRENT SCOPE:

4. Remove the knock-out

5. Add a new knock-out
'''


class KnockoutRedesignAdviser(object):
    def __init__(self, knockout_analyzer: KnockoutAnalyzer, quiet=False, attribute_range_confidence_interval=0.99):
        self.variants = None
        self.raw_rulesets = None
        self.dependencies = None
        self.knockout_analyzer = knockout_analyzer
        self.quiet = quiet
        self.attribute_range_confidence_interval = attribute_range_confidence_interval
        self.redesign_options = {}

    def compute_redesign_options(self):
        self.dependencies = find_ko_activity_dependencies(self.knockout_analyzer)

        self.redesign_options["reordering"] = evaluate_knockout_reordering_io(self.knockout_analyzer,
                                                                              self.dependencies)

        self.redesign_options["relocation"], self.variants = evaluate_knockout_relocation_io(self.knockout_analyzer,
                                                                                             self.dependencies,
                                                                                             optimal_ko_order=
                                                                                             self.redesign_options[
                                                                                                 "reordering"][
                                                                                                 "optimal_ko_order"],
                                                                                             start_activity_constraint=
                                                                                             self.knockout_analyzer.start_activity)

        self.redesign_options["rule_change"], self.raw_rulesets = evaluate_knockout_rule_change_io(
            self.knockout_analyzer,
            self.attribute_range_confidence_interval)

        reports = self.print_report()
        return self.redesign_options, reports

    def print_report(self):
        reports = {}
        print(f"\n** Redesign options **\n")

        # TODO: cleaner printing/reporting method...
        print_dependencies = True
        if print_dependencies:
            print("\n> Dependencies of KO activities\n")
            entries = []
            attribute_dependencies_dict = self.dependencies
            for activity in attribute_dependencies_dict.keys():
                if not (len(attribute_dependencies_dict[activity]) > 0):
                    entries.append(
                        {globalColumnNames.REPORT_COLUMN_KNOCKOUT_CHECK: activity,
                         "Dependencies": "required attributes are available from the start."})
                    continue

                dependencies_str = ""
                for pair in attribute_dependencies_dict[activity]:
                    dependencies_str += f"'{pair[0]}' available after activity '{pair[1]}'" + "\n"

                entries.append(
                    {globalColumnNames.REPORT_COLUMN_KNOCKOUT_CHECK: activity,
                     "Dependencies": dependencies_str})

            df = pd.DataFrame(entries)
            df.sort_values(by=globalColumnNames.REPORT_COLUMN_KNOCKOUT_CHECK, ignore_index=True, inplace=True)
            reports["dependencies"] = df
            print(tabulate(df, headers='keys', showindex="false", tablefmt="fancy_grid"))

        if "reordering" in self.redesign_options:
            print("\n\n> Knock-out Re-ordering\n")
            optimal_order = [f'{i + 1}. {ko}' + '\n' for i, ko in
                             enumerate(self.redesign_options['reordering']['optimal_ko_order'])]
            cases_respecting_order = self.redesign_options['reordering']['cases_respecting_order']
            total_cases = self.redesign_options['reordering']['total_cases']

            print(
                "Optimal Order of Knock-out checks (taking into account attribute dependencies):\n" + f"{''.join(optimal_order)}\n{cases_respecting_order}/{total_cases} non-knocked-out case(s) follow it.")

            reports["reordering"] = ''.join(
                optimal_order) + "\n" + f"{cases_respecting_order}/{total_cases} non-knocked-out case(s) follow it."

        if "relocation" in self.redesign_options:
            print("\n\n> Knock-out Re-location\n")

            total_cases = self.knockout_analyzer.get_total_cases()
            entries = []
            for item in self.redesign_options["relocation"].items():
                entries.append(
                    {"Case count": self.variants[item[0]],
                     "Cases Covered": f"{round(100 * (self.variants[item[0]] / total_cases), ndigits=1)} %",
                     "As-is / To-be": " -> ".join(item[0]) + '\n'
                                      + get_edits_string(" -> ".join(item[0]),
                                                         " -> ".join(item[1]))})

            df = pd.DataFrame(entries)
            df.index.name = "Variant"
            df = df.sort_values(by="Case count", ascending=False, ignore_index=True)
            reports["relocation"] = df[["Cases Covered", "As-is / To-be"]]
            print(tabulate(df, headers='keys', showindex="true", tablefmt="fancy_grid"))

        if "rule_change" in self.redesign_options:
            print("\n\n> Knock-out rule value ranges\n")

            entries = []

            rule_attribute_ranges_dict = self.redesign_options["rule_change"]
            for activity in rule_attribute_ranges_dict.keys():
                confidence_intervals_string = f"{self.raw_rulesets[activity]}"
                if not (len(self.raw_rulesets[activity]) > 0):
                    continue

                if len(rule_attribute_ranges_dict[activity]) > 0:
                    confidence_intervals_string += f"\nValue ranges of knocked-out cases:"
                else:
                    confidence_intervals_string += f"\nNo numerical attributes found in rule."
                for attribute in rule_attribute_ranges_dict[activity]:
                    confidence_intervals_string += f"\n- {attribute}: {rule_attribute_ranges_dict[activity][attribute][0]:.2f} - {rule_attribute_ranges_dict[activity][attribute][1]:.2f}"

                confidence_intervals_string += "\n"
                entries.append(
                    {globalColumnNames.REPORT_COLUMN_KNOCKOUT_CHECK: activity,
                     "Observation": confidence_intervals_string})

            df = pd.DataFrame(entries)
            df.sort_values(by=globalColumnNames.REPORT_COLUMN_KNOCKOUT_CHECK, ignore_index=True, inplace=True)
            reports["rule_change"] = df
            print(tabulate(df, headers='keys', showindex="false", tablefmt="fancy_grid"))

        return reports


if __name__ == "__main__":
    log, configuration = read_log_and_config("test/config", "synthetic_example_enriched.json",
                                             "cache/synthetic_example")

    analyzer = KnockoutAnalyzer(log_df=log,
                                config=configuration,
                                config_file_name="synthetic_example_enriched.json",
                                config_dir="test/config",
                                cache_dir="cache/synthetic_example",
                                always_force_recompute=False,
                                quiet=True)

    analyzer.discover_knockouts()

    analyzer.compute_ko_rules(grid_search=False, algorithm="IREP", confidence_threshold=0.5, support_threshold=0.1,
                              print_rule_discovery_stats=False, omit_report=False)

    adviser = KnockoutRedesignAdviser(analyzer)
    adviser.compute_redesign_options()
