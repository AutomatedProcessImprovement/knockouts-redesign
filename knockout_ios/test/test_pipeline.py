import pytest

from knockout_ios.pipeline_wrapper import Pipeline


@pytest.mark.pipeline
def test_synthetic_example():
    ko_redesign_adviser = Pipeline(config_dir="test/config",
                                   config_file_name="synthetic_example_enriched_pytest.json",
                                   cache_dir="cache/synthetic_example",
                                   ).run_pipeline()

    assert ko_redesign_adviser.redesign_options['reordering']['optimal_ko_order'].index("Check Risk") \
           < ko_redesign_adviser.redesign_options['reordering']['optimal_ko_order'].index("Assess application")

    assert ko_redesign_adviser.redesign_options['reordering']['optimal_ko_order'].index("Check Liability") \
           == len(ko_redesign_adviser.redesign_options['reordering']['optimal_ko_order']) - 1

    assert ko_redesign_adviser.redesign_options['reordering']['optimal_ko_order'] == ["Check Monthly Income",
                                                                                      "Check Risk",
                                                                                      "Assess application",
                                                                                      "Check Liability"]
