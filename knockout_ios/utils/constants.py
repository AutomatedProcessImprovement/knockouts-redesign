from dataclasses import dataclass, asdict


class ColumnNames:
    SIMOD_LOG_READER_CASE_ID_COLUMN_NAME = 'caseid'
    SIMOD_LOG_READER_ACTIVITY_COLUMN_NAME = 'task'
    SIMOD_START_TIMESTAMP_COLUMN_NAME = 'start_timestamp'
    SIMOD_END_TIMESTAMP_COLUMN_NAME = 'end_timestamp'
    SIMOD_RESOURCE_COLUMN_NAME = 'user'

    PM4PY_ACTIVITY_COLUMN_NAME = 'concept:name'
    PM4PY_RESOURCE_COLUMN_NAME = '@@startevent_org:resource'
    PM4PY_CASE_ID_COLUMN_NAME = 'case:concept:name'
    PM4PY_START_TIMESTAMP_COLUMN_NAME = 'start_timestamp'
    PM4PY_END_TIMESTAMP_COLUMN_NAME = "time:timestamp"

    DURATION_COLUMN_NAME = "@@duration"
    PROCESSING_TIME = 'Processing Time'

    EMPTY_NON_NUMERICAL_VALUE = "<NONE>"

    REPORT_COLUMN_WT_WASTE = 'Total Waiting Time Waste'
    REPORT_COLUMN_MEAN_WT_WASTE = 'Mean Waiting Time Waste'
    REPORT_COLUMN_TOTAL_PT_WASTE = 'Total PT Waste'
    REPORT_COLUMN_TOTAL_OVERPROCESSING_WASTE = 'Total Overprocessing Waste'
    REPORT_COLUMN_EFFORT_PER_KO = "Effort per rejection"
    REPORT_COLUMN_REJECTION_RATE = "Rejection rate"
    REPORT_COLUMN_MEAN_PT = "Mean Duration"
    REPORT_COLUMN_CASE_FREQ = "Case frequency"
    REPORT_COLUMN_TOTAL_FREQ = "Total frequency"
    REPORT_COLUMN_KNOCKOUT_CHECK = "Knockout Check"
    REPORT_COLUMN_REJECTION_RULE = "Rejection rule"
    REPORT_COLUMN_CONFIDENCE = "Confidence"
    REPORT_COLUMN_BALANCED_ACCURACY = "Balanced Accuracy"


globalColumnNames = ColumnNames()
