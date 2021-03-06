from copy import deepcopy
from dataclasses import dataclass

import numpy as np
import pandas as pd
from tqdm import tqdm

from knockout_ios.utils.constants import globalColumnNames

from scipy.stats import truncnorm


def get_truncated_normal(mean, std, low, high):
    # source: https://stackoverflow.com/a/44308018/8522453

    return truncnorm((low - mean) / std, (high - mean) / std, loc=mean, scale=std).rvs()


def enrich_log_df(log_df) -> pd.DataFrame:
    # To keep consistency on every call
    np.random.seed(0)

    log_df = deepcopy(log_df)

    #  Synthetic Example Ground Truth
    #  (K.O. checks and their rejection rules):
    #
    # 'Check Liability':                 'Total Debt'     > 5000 ||  'Owns Vehicle' = False
    # 'Check Risk':                      'Loan Ammount'   > 10000
    # 'Check Monthly Income':            'Monthly Income' < 1000
    # 'Assess application':              'External Risk Score' > 0.3
    # 'Aggregated Risk Score Check':     'Aggregated Risk Score' > 0.5

    # First populate df with values that don't fall under any of the knock outs' rules

    demographic_values = ['demographic_type_1', 'demographic_type_2', 'demographic_type_3']

    if globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME in log_df.columns:
        log_df.set_index(globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME, inplace=True)
    elif globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME in log_df.columns:
        log_df.set_index(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME, inplace=True)

    for caseid in tqdm(log_df.index.unique(), desc="Enriching with case attributes"):

        log_df.at[caseid, 'Monthly Income'] = get_truncated_normal(mean=1000, std=500, low=1000, high=5000)
        log_df.at[caseid, 'Total Debt'] = get_truncated_normal(mean=5000, std=2000, low=0, high=4999)
        log_df.at[caseid, 'Loan Ammount'] = get_truncated_normal(mean=10000, std=8000, low=0, high=9999)
        log_df.at[caseid, 'Owns Vehicle'] = True
        log_df.at[caseid, 'Demographic'] = np.random.choice(demographic_values)
        log_df.at[caseid, 'External Risk Score'] = get_truncated_normal(mean=0.5, std=0.5, low=0, high=0.29)
        log_df.at[caseid, 'Aggregated Risk Score'] = get_truncated_normal(mean=0.5, std=0.5, low=0, high=0.49)

        ko_activity = log_df.loc[caseid]["knockout_activity"].unique()
        if len(ko_activity) > 0:
            ko_activity = ko_activity[0]

        if ko_activity == 'Check Liability':
            if np.random.uniform(0, 1) < 0.5:
                log_df.at[caseid, 'Total Debt'] = get_truncated_normal(mean=5000, std=2000, low=4999, high=50000)
            else:
                log_df.at[caseid, 'Owns Vehicle'] = False
        elif ko_activity == 'Check Risk':
            log_df.at[caseid, 'Loan Ammount'] = get_truncated_normal(mean=10000, std=8000, low=10000, high=100000)
        elif ko_activity == 'Check Monthly Income':
            log_df.at[caseid, 'Monthly Income'] = get_truncated_normal(mean=1000, std=500, low=0, high=999)
        elif ko_activity == 'Assess application':
            log_df.at[caseid, 'External Risk Score'] = get_truncated_normal(mean=0.5, std=0.5, low=0.3, high=1)
        elif ko_activity == 'Aggregated Risk Score Check':
            log_df.at[caseid, 'Aggregated Risk Score'] = get_truncated_normal(mean=0.5, std=0.5, low=0.5, high=1)

    log_df.reset_index(inplace=True)
    return log_df


def enrich_log_df_fixed_values(log_df) -> pd.DataFrame:
    # To keep consistency on every call
    np.random.seed(0)

    log_df = deepcopy(log_df)

    demographic_values = ['demographic_type_1', 'demographic_type_2', 'demographic_type_3']

    if globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME in log_df.columns:
        log_df.set_index(globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME, inplace=True)
    elif globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME in log_df.columns:
        log_df.set_index(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME, inplace=True)

    for caseid in tqdm(log_df.index.unique(), desc="Enriching with case attributes"):

        log_df.at[caseid, 'Monthly Income'] = 1500
        log_df.at[caseid, 'Total Debt'] = 4000
        log_df.at[caseid, 'Loan Ammount'] = 9000
        log_df.at[caseid, 'Owns Vehicle'] = True
        log_df.at[caseid, 'Demographic'] = 'demographic_type_1'
        log_df.at[caseid, 'External Risk Score'] = 0.1
        log_df.at[caseid, 'Aggregated Risk Score'] = 0.2

        ko_activity = log_df.loc[caseid]["knockout_activity"].unique()
        if len(ko_activity) > 0:
            ko_activity = ko_activity[0]

        if ko_activity == 'Check Liability':
            if np.random.uniform(0, 1) < 0.5:
                log_df.at[caseid, 'Total Debt'] = 5000
            else:
                log_df.at[caseid, 'Owns Vehicle'] = False
        elif ko_activity == 'Check Risk':
            log_df.at[caseid, 'Loan Ammount'] = 15000
        elif ko_activity == 'Check Monthly Income':
            log_df.at[caseid, 'Monthly Income'] = 800
        elif ko_activity == 'Assess application':
            log_df.at[caseid, 'External Risk Score'] = 0.4
        elif ko_activity == 'Aggregated Risk Score Check':
            log_df.at[caseid, 'Aggregated Risk Score'] = 0.6

    log_df.reset_index(inplace=True)
    return log_df


@dataclass
class RuntimeAttribute:
    attribute_name: str
    value_provider_activity: str


def enrich_log_df_with_masked_attributes(log_df: pd.DataFrame,
                                         runtime_attributes: list[RuntimeAttribute],
                                         fixed_values=False) -> pd.DataFrame:
    """
    Emulates attributes known only after certain activity
    """
    if fixed_values:
        log_df = enrich_log_df_fixed_values(log_df)
    else:
        log_df = enrich_log_df(log_df)

    activity_col = globalColumnNames.SIMOD_LOG_READER_ACTIVITY_COLUMN_NAME

    if globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME in log_df.columns:
        log_df.set_index(globalColumnNames.SIMOD_LOG_READER_CASE_ID_COLUMN_NAME, inplace=True)
    elif globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME in log_df.columns:
        log_df.set_index(globalColumnNames.PM4PY_CASE_ID_COLUMN_NAME, inplace=True)
        activity_col = globalColumnNames.PM4PY_ACTIVITY_COLUMN_NAME

    for attribute in runtime_attributes:

        for caseid in tqdm(log_df.index.unique(), desc="Masking case attributes"):
            case = log_df.loc[caseid]

            if attribute.value_provider_activity not in case[activity_col].unique():
                continue

            case = case.sort_values(by=globalColumnNames.SIMOD_START_TIMESTAMP_COLUMN_NAME, ascending=True)

            value_producer_end = \
                case[
                    case[globalColumnNames.SIMOD_LOG_READER_ACTIVITY_COLUMN_NAME] == attribute.value_provider_activity][
                    globalColumnNames.SIMOD_END_TIMESTAMP_COLUMN_NAME][0]

            log_df.at[caseid, attribute.attribute_name] = np.where(
                case[globalColumnNames.SIMOD_START_TIMESTAMP_COLUMN_NAME] >= value_producer_end,
                case[attribute.attribute_name],
                np.nan)

    log_df.reset_index(inplace=True)
    return log_df
