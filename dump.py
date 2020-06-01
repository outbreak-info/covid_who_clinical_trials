import os

import biothings, config
biothings.config_for_app(config)
from config import DATA_ARCHIVE_ROOT

import biothings.hub.dataload.dumper


class ClinicalTrialDumper(biothings.hub.dataload.dumper.DummyDumper):
    # Source info: clinicaltrials.gov
    # SRC_URLS = "https://clinicaltrials.gov/api/query/full_studies?expr=(%22covid-19%22%20OR%20%22sars-cov-2%22)&min_rnk=1&max_rnk=100&fmt=json"
    # {"license_url": "https://clinicaltrials.gov/ct2/about-site/terms-conditions",
    # "url": "https://clinicaltrials.gov/ct2/results?cond=COVID-19"}

    # Source info: WHO
    # SRC_URLS = "https://www.who.int/ictrp/COVID19-web.csv"
    # license/terms unavailable?
    # {"url": "https://www.who.int/ictrp/en/"}
    #
    # Source info: Natural Earth (used to normalize country names)
    # SRC_URLS = "https://www.naturalearthdata.com/downloads/10m-cultural-vectors/"
    # {"license_url": "https://www.naturalearthdata.com/about/terms-of-use/",
    # "license": "CC0 1.0 Universal",
    # "url": "https://www.naturalearthdata.com/"}

    SRC_NAME = "covid_who_clinical_trials"
    SRC_URLS = ["https://www.who.int/ictrp/COVID19-web.csv", "https://www.naturalearthdata.com/downloads/10m-cultural-vectors/"]
    # override in subclass accordingly
    SRC_ROOT_FOLDER = os.path.join(DATA_ARCHIVE_ROOT, SRC_NAME)

    SCHEDULE = "20 14 * * *"  # daily at 14:20UTC/7:20PT
