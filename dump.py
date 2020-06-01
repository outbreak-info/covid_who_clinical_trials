import os

import biothings, config
biothings.config_for_app(config)
from config import DATA_ARCHIVE_ROOT

import biothings.hub.dataload.dumper

class ClinicalTrialDumper(biothings.hub.dataload.dumper.DummyDumper):

    SRC_NAME = "covid_who_clinical_trials"
    SRC_URLS = ["https://www.who.int/ictrp/COVID19-web.csv", "https://www.naturalearthdata.com/downloads/10m-cultural-vectors/"]
    # override in subclass accordingly
    SRC_ROOT_FOLDER = os.path.join(DATA_ARCHIVE_ROOT, SRC_NAME)

    SCHEDULE = "20 14 * * *"  # daily at 14:20UTC/7:20PT
