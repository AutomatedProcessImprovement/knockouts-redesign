from knockout_ios.pipeline_wrapper import Pipeline


def synthetic_example():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="synthetic_example_ko_order_io_pipeline_test.json",
                                   cache_dir="cache/synthetic_example").run_pipeline()

    assert ko_redesign_adviser.redesign_options['reordering']['optimal_ko_order'] == ["Check Monthly Income",
                                                                                      "Check Risk",
                                                                                      "Assess application",
                                                                                      "Check Liability"]


def synthetic_example_1_timest():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="synthetic_example_ko_order_io_pipeline_test_1_timest.json",
                                   cache_dir="cache/synthetic_example").run_pipeline()


def bpi_2017_1k():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="bpi_2017_1k.json",
                                   cache_dir="cache/bpi_2017_1k").run_pipeline()


def bpi_2017_8k():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="bpi_2017_8k.json",
                                   cache_dir="cache/bpi_2017_8k").run_pipeline()


def bpi_2017_21k():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="bpi_2017_21k.json",
                                   cache_dir="cache/bpi_2017_21k").run_pipeline()


def bpi_2017_1k_W():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="bpi_2017_1k_W.json",
                                   cache_dir="cache/bpi_2017_1k_W").run_pipeline()


def envpermit():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="envpermit.json",
                                   cache_dir="cache/envpermit").run_pipeline()


def envpermit_auto():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="envpermit_auto.json",
                                   cache_dir="cache/envpermit_auto").run_pipeline()


def bpi_2018_2k():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="bpi_2018_2k.json",
                                   cache_dir="cache/bpi_2018_2k").run_pipeline()


def bpi_2018_4k():
    ko_redesign_adviser = Pipeline(config_dir="config",
                                   config_file_name="bpi_2018_4k.json",
                                   cache_dir="cache/bpi_2018_4k").run_pipeline()


if __name__ == "__main__":
    synthetic_example()
    # synthetic_example_1_timest()
    # bpi_2017_1k()
    # bpi_2017_8k()
    # bpi_2017_21k()
    # bpi_2017_1k_W()
    # envpermit_auto()
    # envpermit()
    # bpi_2018_2k()
    # bpi_2018_4k()
