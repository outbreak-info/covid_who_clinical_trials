import pandas as pd
import requests
from math import ceil
import re
import collections
import json
import os
from datetime import date, datetime

"""
Parser to grab COVID-19 / SARS-Cov-2 Clinical Trials metadata from the WHO's trial registry.
Sources:
- WHO data: https://www.who.int/ictrp/COVID19-web.csv
- WHO data dictionary: https://www.who.int/ictrp/glossary/en/
- EU-CTR data dictionary: https://eudract.ema.europa.eu/protocol.html
- ANZCTR definitions: https://www.anzctr.org.au/docs/ANZCTR%20Data%20field%20explanation.pdf?t=279
- WHO sources:
    - Australian New Zealand Clinical Trials Registry (ANZCTR)
    - Brazilian Clinical Trials Registry (ReBec)
    - Chinese Clinical Trial Register (ChiCTR)
    - Clinical Research Information Service (CRiS), Republic of Korea
    - ClinicalTrials.gov
    - Clinical Trials Registry - India (CTRI)
    - Cuban Public Registry of Clinical Trials (RPCEC)
    - EU Clinical Trials Register (EU-CTR)
    - German Clinical Trials Register (DRKS)
    - Iranian Registry of Clinical Trials (IRCT)
    - ISRCTN
    - Japan Primary Registries Network (JPRN)
    - Pan African Clinical Trial Registry (PACTR)
    - Peruvian Clinical Trials Registry (REPEC)
    - Sri Lanka Clinical Trials Registry (SLCTR)
    - Thai Clinical Trials Register (TCTR)
    - The Netherlands National Trial Register (NTR)
"""

WHO_URL = "https://www.who.int/ictrp/COVID19-web.csv"
# Names derived from Natural Earth to standardize to their ISO3 code (ADM0_A3) and NAME for geo-joins: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/
dirname =os.path.dirname(os.path.realpath("naturalearth_countries.csv"))
COUNTRY_FILE = "https://raw.githubusercontent.com/flaneuse/clinical_trials/master/naturalearth_countries.csv"
COL_NAMES = ["@type", "_id", "identifier", "identifierSource", "url", "name", "alternateName", "abstract", "description", "funding", "author",
             "studyStatus", "studyEvent", "hasResults", "dateCreated", "datePublished", "dateModified", "curatedBy", "healthCondition", "keywords",
             "studyDesign", "outcome", "eligibilityCriteria", "isBasedOn", "relatedTo", "studyLocation", "armGroup", "interventions", "interventionText"]

# Generic helper functions


def formatDate(x, inputFormat="%B %d, %Y", outputFormat="%Y-%m-%d"):
    date_str = pd.datetime.strptime(x, inputFormat).strftime(outputFormat)
    return(date_str)


def binarize(val):
    if(val == val):
        if((val == "yes") | (val == "Yes") | (val == 1) | (val == "1")):
            return(True)
        if((val == "no") | (val == "No") | (val == 0) | (val == "0")):
            return(False)


def getIfExists(row, variable):
    if(variable in row.keys()):
        return(row[variable])


def flattenJson(arr):
    flat_list = []

    for study in arr:
        obj = {}
        for key in study:
            for innerKey in study[key]:
                obj[innerKey] = study[key][innerKey]
        flat_list.append(obj)
    return(flat_list)


def flattenList(l):
    return([item for sublist in l for item in sublist])

# from https://stackoverflow.com/questions/2158395/flatten-an-irregular-list-of-lists
def flatten(l):
    for el in l:
        if isinstance(el, collections.abc.Iterable) and not isinstance(el, (str, bytes)):
            yield from flatten(el)
        else:
            yield el

def listify(row, col_names):
    arr = []
    for col in col_names:
        try:
            if(row[col] == row[col]):
                arr.append(row[col])
        except:
            pass
    return(arr)


"""
WHO Specific functions
"""
# from https://www.who.int/ictrp/search/data_providers/en/
# and https://www.who.int/ictrp/network/primary/en/
# all ids converted to uppercase to account for weirdness in data entry


def convertSource(source):
    source_dict = {
        "ANZCTR": "Australian New Zealand Clinical Trials Registry",
        "REBEC": "Brazilian Clinical Trials Registry",
        "CHICTR": "Chinese Clinical Trial Register",
        "CRIS": "Clinical Research Information Service, Republic of Korea",
        "CTRI": "Clinical Trials Registry - India",
        "NCT": "ClinicalTrials.gov",
        "RPCEC": "Cuban Public Registry of Clinical Trials",
        "EU-CTR": "EU Clinical Trials Register",
        "DRKS": "German Clinical Trials Register",
        "IRCT": "Iranian Registry of Clinical Trials",
        "JPRN": "Japan Primary Registries Network",
        "PACTR": "Pan African Clinical Trial Registry",
        "REPEC": "Peruvian Clinical Trials Registry",
        "SLCTR": "Sri Lanka Clinical Trials Registry",
        "TCTR": "Thai Clinical Trials Register",
        "LBCTR": "Lebanon Clinical Trials Registry",
        "NTR": "Netherlands Trial Register"}
    try:
        return(source_dict[source.upper()])
    except:
        return(source)

def standardizeCountry(input, ctry_dict, return_val = "country_name"):
    try:
        return(ctry_dict[input.strip().lower()]["country_name"])
    except:
        print(f"No match found for country {input}")
        return(input)


def splitCountries(countryString, ctry_dict):
    if(countryString == countryString):
        # commas are both used as delimiters and in country names (sigh)
        countryNorm = countryString.replace("Virgin Islands, U.S.", "United States of America").replace("Virgin Islands, British", "United Kingdom").replace("Korea, North", "North Korea").replace("Korea, South", "South Korea").replace("Korea, Republic of", "South Korea").replace("Iran, Islamic Republic of", "Iran").replace("Congo, ", "South Korea")
        ctries = re.split(",|;", countryNorm)
        return([{"@type": "Place", "studyLocationCountry": standardizeCountry(country, ctry_dict)} for country in ctries])


def splitCondition(conditionString):
    if((conditionString == conditionString) & (isinstance(conditionString, str))):
        conditions = [text.split(";") for text in conditionString.split("<br>")]
        flat_list = [item.strip() for sublist in conditions for item in sublist if isinstance(item, str) ]
        return([item for item in flat_list if item != ""])


def getWHOStatus(row):
    obj = {"@type": "StudyStatus"}
    if(row["Recruitment Status"] == row["Recruitment Status"]):
        obj["status"] = row["Recruitment Status"].lower()
    obj["statusDate"] = row.dateModified

    if(row["Target size"] == row["Target size"]):
        armTargets = [text.split(":")
                      for text in row["Target size"].split(";")]
        targets = []
        for target in armTargets:
            if(len(target) == 2):
                try:
                    targets.append(int(target[1]))
                except:
                    pass
            else:
                try:
                    targets.append(int(target[0]))
                except:
                    pass
                    # print(f"cannot convert string {target[0]} to an integer")
        enrollmentTarget = sum(targets)

        if(enrollmentTarget > 0):
            obj["enrollmentCount"] = enrollmentTarget
            obj["enrollmentType"] = "anticipated"
    return(obj)


def getWHOEvents(row):
    arr = []
    if(row["Date enrollement"] == row["Date enrollement"]):
        arr.append({"@type": "StudyEvent", "studyEventType": "start",
                    "studyEventDate": row["Date enrollement"], "studyEventDateType": "actual"})
    if(row["results date completed"] == row["results date completed"]):
        arr.append({"@type": "StudyEvent", "studyEventType": "first submission of results",
                    "studyEventDate": row["results date completed"], "studyEventDateType": "actual"})
    if(row["results date posted"] == row["results date posted"]):
        arr.append({"@type": "StudyEvent", "studyEventType": "first posting of results",
                    "studyEventDate": row["results date posted"], "studyEventDateType": "actual"})
    return(arr)


def getWHOEligibility(row):
    obj = {}
    obj["@type"] = "Eligibility"
    if(row["Inclusion Criteria"] == row["Inclusion Criteria"]):
        criteria = row["Inclusion Criteria"].split("Exclusion Criteria:")
        obj["inclusionCriteria"] = [criteria[0].replace(
            "Inclusion criteria:", "").replace("Inclusion Criteria:", "").strip()]
        if(len(criteria) == 2):
            obj["exclusionCriteria"] = [criteria[1].strip()]
        else:
            obj["exclusionCriteria"] = []
    if(row["Exclusion Criteria"] == row["Exclusion Criteria"]):
        obj["exclusionCriteria"].append(row["Exclusion Criteria"].replace(
            "Exclusion criteria:", "").replace("Exclusion Criteria:", "").strip())
    if(row["Inclusion agemin"] == row["Inclusion agemin"]):
        obj["minimumAge"] = row["Inclusion agemin"].lower()
    if(row["Inclusion agemax"] == row["Inclusion agemax"]):
        obj["maximumAge"] = row["Inclusion agemax"].lower()
    if(row["Inclusion gender"] == row["Inclusion gender"]):
        obj["gender"] = row["Inclusion gender"].lower()
    return([obj])


def getWHOAuthors(row):
    arr = []
    affiliation = row["Contact Affiliation"]
    if((row["Contact Firstname"] == row["Contact Firstname"]) & (row["Contact Lastname"] == row["Contact Lastname"])):
        obj = {}
        obj["@type"] = "Person"
        obj["name"] = f"{row['Contact Firstname']} {row['Contact Lastname']}"
        if(affiliation == affiliation):
            obj["affiliation"] = [{"@type": "Organization", "name": affiliation.strip()}]
        return([obj])
    elif(row["Contact Firstname"] == row["Contact Firstname"]):
        # Assuming one affiliation for all authors?
        author_list = re.split(";|\?|,|;", row["Contact Firstname"])
        for author in author_list:
            if(affiliation == affiliation):
                arr.append({"@type": "Person", "name": author.strip(),
                            "affiliation": [{"@type": "Organization", "name": affiliation.strip()}]})
            else:
                arr.append({"@type": "Person", "name": author.strip()})
        return(arr)
    elif(row["Contact Lastname"] == row["Contact Lastname"]):
        # Assuming one affiliation for all authors?
        author_list = re.split(";|\?|,|;", row["Contact Lastname"])
        for author in author_list:
            if(affiliation == affiliation):
                arr.append({"@type": "Person", "name": author.strip(),
                            "affiliation": [{"@type": "Organization", "name": affiliation.strip()}]})
            else:
                arr.append({"@type": "Person", "name": author.strip()})
        return(arr)


def getOutcome(outcome_string):
    if(outcome_string == outcome_string):
        outcomes = outcome_string.split(";")
        return([{"@type": "Outcome", "outcomeMeasure": outcome, "outcomeType": "primary"} for outcome in outcomes if outcome != ""])


def standardizeType(type):
    type_dict = {
        "intervention": "interventional",
        "treatment study": "interventional",
        "interventional study": "interventional",
        "interventional clinical trial of medicinal product": "interventional",
        "prevention": "prevention",

        "observational study": "observational",
        "epidemilogical research": "observational",
        "prognosis study": "observational",

        "diagnostic test": "diagnostic test",
        "screening": "screening",
        "basic science": "basic science",
        "health services research": "health services research",
        "health services reaserch": "health services research",
        "others,meta-analysis etc": "others",
    }
    if(type == type):
        try:
            return(type_dict[type.lower()])
        except:
            return(type.lower())


def standardizePhase(phase):
    phase_dict = {
        "N/A": ["not applicable"],
        "retrospective": ["not applicable"],
        "retrospective study": ["not applicable"],
        "0": ["phase 0"],
        "1": ["phase 1"],
        "2": ["phase 2"],
        "3": ["phase 3"],
        "4": ["phase 4"],
        "i": ["phase 1"],
        "ii": ["phase 2"],
        "iii": ["phase 3"],
        "iv": ["phase 4"],
        "phase i": ["phase 1"],
        "phase ii": ["phase 2"],
        "phase iii": ["phase 3"],
        "phase iv": ["phase 4"],
        "phase-1": ["phase 1"],
        "phase-2": ["phase 2"],
        "phase-3": ["phase 3"],
        "phase-4": ["phase 4"],
        "phase 1/phase 2": ["phase 1", "phase 2"],
        "phase 1 / phase 2": ["phase 1", "phase 2"],
        "1-2": ["phase 1", "phase 2"],
        "phase i/ii": ["phase 1", "phase 2"],
        "phase 2/phase 3": ["phase 2", "phase 3"],
        "phase 2 / phase 3": ["phase 2", "phase 3"],
        "phase 2/phase 3": ["phase 2", "phase 3"],
        "phase ii/iii": ["phase 2", "phase 3"],
        "ii-iii": ["phase 2", "phase 3"],
        "2-3": ["phase 2", "phase 3"],
        "not selected": None
    }
    if(phase == phase):
        # For EU-CTR, spli the phases
        if("human pharmacology" in phase.lower()):
            phases = [re.search("\(phase (\w+)\)", item.lower())[1]
                      for item in phase.split("\n") if "yes" in item]
            phases_conv = [phase_dict[phase_str] for phase_str in phases]
            return(flattenList(phases_conv))
        else:
            try:
                return(phase_dict[phase.lower()])
            except:
                return([phase.lower()])


def getPhaseNumber(phase):
    if(phase == "early phase 1"):
        return([0,1])
    if(phase == "phase 0"):
        return(0)
    if(phase == "phase 1"):
        return(1)
    if(phase == "phase 2"):
        return(2)
    if(phase == "phase 3"):
        return(3)
    if(phase == "phase 4"):
        return(4)
    return(None)


def getNumArms(design_text):
    if(design_text == design_text):
        # For EU data
        arms = re.search("Number of treatment arms in the trial: (\d+)", design_text)
        if(arms):
            return(int(arms[1]))

def standardizeModel(design):
    # values from https://clinicaltrials.gov/api/query/field_values?field=DesignInterventionModel&fmt=json
    # and https://clinicaltrials.gov/api/query/field_values?field=DesignObservationalModel&fmt=json
    model_dict = {
        # interventional
        "cross-over": "crossover assignment",
        "crossover": "crossover assignment",
        "cross over": "crossover assignment",
        "factorial": "factorial assignment",
        "parallel": "parallel assignment",
        "sequential": "sequential assignment",
        "single group": "single group assignment",
        "single arm": "single group assignment",
        "single arm study": "single group assignment",
        # observational
        "case control": "case control",
        "case-control": "case-control",
        "case-control study": "case-control",
        "case-crossover": "case-crossover",
        "case-only": "case-only",
        "case study": "case-only",
        "cohort": "cohort",
        "cohort study": "cohort",
        "defined population": "defined population",
        "ecologic or community": "ecologic or community",
        "family-based": "family-based",
        "natural history": "natural history",
        "other": "other"
    }
    if(design != design):
        return(None)
    # Iran clinical trials format
    iran_design = re.search("assignment: (.+?)\,", design.lower())
    if(iran_design):
        try:
            return(model_dict[iran_design[1].lower()])
        except:
            return(iran_design[1].lower())

    # German clinical trials format
    drks_design = re.search("assignment: (.+?)\.", design.lower())
    if(drks_design):
        # Make sure to only pull the first term
        drk_arr = drks_design[1].lower().split(".")
        try:
            return(model_dict[drk_arr[0]])
        except:
            return(drk_arr[0])


    #  Aussie/NZ, Lebanon clinical trials format
    anz_design = re.search("assignment: (.+?)\;", design.lower())
    if(anz_design):
        # Make sure to only pull the first term
        anz_arr = anz_design[1].lower().split(";")
        try:
            return(model_dict[anz_arr[0]])
        except:
            return(anz_arr[0])


    # EU-parallel
    eu_parallel = re.search("parallel group: yes", design.lower())
    if(eu_parallel):
        return("parallel assignment")
    eu_crossover = re.search("cross over group: yes", design.lower())
    if(eu_crossover):
        return("crossover assignment")
    # JPN: parallel, single
    jpn_parallel = re.search("parallel assignment", design.lower())
    if(jpn_parallel):
        return("parallel assignment")
    jpn_single = re.search("single assignment", design.lower())
    if(jpn_single):
        return("single group assignment")
    else:
        try:
            return(model_dict[design.lower()])
        except:
            pass


def standardizeAllocation(design_text):
    if(design_text == design_text):
        design_text = design_text.lower()
        # German format
        if("allocation: single arm study" in design_text):
            return("non-randomized")
        # Netherlands format
        if("randomized: no" in design_text):
            return("non-randomized")
        # EU format
        if("randomised: no" in design_text):
            return("non-randomized")
        if("not randomized" in design_text):
            return("non-randomized")
        if("non randomized" in design_text):
            return("non-randomized")
        if("non-randomized" in design_text):
            return("non-randomized")
        if("not randomised" in design_text):
            return("non-randomized")
        if("non randomised" in design_text):
            return("non-randomized")
        if("non-randomised" in design_text):
            return("non-randomized")
        if("randomised" in design_text):
            return("randomized")
        if("randomized" in design_text):
            return("randomized")


def standardizePurpose(row):
    design_str = row["Study design"]
    purpose_dict = {
        "treatment": "treatment",
        "treatment.": "treatment",
        "prevention": "prevention",
        "diagnostic": "diagnostic",
        "diagnostic test for accuracy": "diagnostic",
        "supportive": "supportive care",
        "supportive care": "supportive care",
        "screening": "screening",
        "health services research": "health services research",
        "health services reaserch": "health services research",
        "health care system": "health services research",
        "basic science": "basic science",
        "basic science/physiological study": "basic science",
        "other": "other"
    }
    if(design_str == design_str):
        # Aus/NZ, Germany:
        anz_purpose = re.search("purpose: (.+?);", design_str.lower())
        if(anz_purpose):
            # Make sure to only pull the first term
            anz_str = anz_purpose[1].lower()
            try:
                return(purpose_dict[anz_str])
            except:
                return(anz_str)
        # Iran:
        iran_purpose = re.search("purpose: (.+?),", design_str.lower())
        if(iran_purpose):
            # Make sure to only pull the first term
            iran_str = iran_purpose[1].lower()
            try:
                return(purpose_dict[iran_str])
            except:
                return(iran_str)
        try:
            return(purpose_dict[design_str.lower()])
        except:
            try:
                return(purpose_dict[row["Study type"].lower()])
            except:
                pass

def standardizeTime(design_str):
    purpose_dict = {
        "cross-sectional": "cross-sectional",
        "longitudinal": "longitudinal",
        "other": "other",
        "prospective": "prospective",
        "retrospective": "retrospective",
        "both": "retrospective/prospective",
        "retrospective/prospective": "retrospective/prospective"
    }

    if(design_str == design_str):
        # Aus/NZ,:
        anz_purpose = re.search("timing: (.+?);", design_str.lower())
        if(anz_purpose):
            # Make sure to only pull the first term
            anz_str = anz_purpose[1].lower()
            try:
                return(purpose_dict[anz_str])
            except:
                return(anz_str)
        if("prospective/retrospective" in design_str.lower()):
            return("prospective/retrospective")
        if("retrospective" in design_str.lower()):
            return("retrospective")
        if("prospective" in design_str.lower()):
            return("prospective")
        if("longitudinal" in design_str.lower()):
            return("longitudinal")
        if("cross-sectional" in design_str.lower()):
            return("cross-sectional")
        return(None)
    return(None)


def getWHODesign(row):
    obj = {"@type": "StudyDesign"}
    obj["studyType"] = standardizeType(row["Study type"])
    obj["phase"] = standardizePhase(row["Phase"])
    if(obj["phase"] is not None):
        phases = [getPhaseNumber(
            phase) for phase in obj["phase"]]
        obj["phaseNumber"] = list(flatten(phases))
    if(row["Study design"] == row["Study design"]):
        obj["designAllocation"] = standardizeAllocation(row["Study design"])
        models = []
        designModel = standardizeModel(row["Study design"])
        if(designModel is not None):
            models.append(designModel)
        modelTime = standardizeTime(row["Study design"])
        if(modelTime is not None):
            models.append(modelTime)
        obj["designModel"] = models

        obj["designPrimaryPurpose"] = standardizePurpose(row)
        obj["studyDesignText"] = row["Study design"]
    return(obj)

def getArms(row):
    intervention_text = row.Intervention
    id = row["Source Register"].upper()
    if(intervention_text == intervention_text):
        if(id == "CHICTR"):
            groups = intervention_text.split(";")
            names = [group.split(":") for group in groups]
            arr = [{"name": name[0].strip(), "@type": "ArmGroup", "intervention": [{"name": name[1].strip(), "@type": "Intervention"}]} for name in names if len(name) > 1]
            return(arr)
        if(id == "PACTR"):
            names = intervention_text.split(";")
            arr = [{"name": name.strip(), "@type": "ArmGroup", "intervention": [{"name": name.strip(), "@type": "Intervention"}]} for name in names if len(name) > 1]
            return(arr)
        if(id == "German Clinical Trials Register".upper()):
            intervention_delim = re.sub("Intervention \d+: ", "****", intervention_text)
            names = intervention_delim.split("****")
            arr = [{"name": name.strip(), "@type": "ArmGroup", "intervention": [{"name": name.strip(), "@type": "Intervention"}]} for name in names if len(name) > 1]
            return(arr)
        if(id == "IRCT"):
            intervention_delim = re.sub("Intervention \d+: ", "****", intervention_text)
            names = intervention_delim.split("****")
            try:
                arr = [{"name": name.split(":")[0].strip(), "description": name.split(":")[1].strip(), "@type": "ArmGroup", "intervention": [{"name": name.split(":")[0].strip(), "description": name.split(":")[1].strip(), "@type": "Intervention"}]} for name in names if len(name) > 1]
            except:
                arr = [{"description": name.strip(), "@type": "ArmGroup", "intervention": [{"description": name.strip(), "@type": "Intervention"}]} for name in names if len(name) > 1]
            return(arr)

def getInterventions(row):
    intervention_text = row.Intervention
    id = row["Source Register"].upper()
    if(intervention_text == intervention_text):
        if(id == "CHICTR"):
            groups = intervention_text.split(";")
            names = [group.split(":") for group in groups]
            arr = [{"name": name[1].strip(), "@type": "Intervention"} for name in names if len(name) > 1]
            return(arr)
        if(id == "PACTR"):
            names = intervention_text.split(";")
            arr = [{"name": name.strip(), "@type": "Intervention"} for name in names if len(name) > 1]
            return(arr)
        if(id == "EU Clinical Trials Register".upper()):
            groups = intervention_text.split("<br><br>")
            interventions = [item.split("<br>") for item in groups]
            arr = []
            for intervention in interventions:
                if(len(intervention) > 0):
                    if(intervention[0] != "\n"):
                        parsed = dict([item.split(": ") for item in intervention if ": " in item])
                        obj = {"@type": "Intervention"}
                        obj["description"] = "\n".join(intervention)
                        if("Product Name" in parsed.keys()):
                            obj["name"] = parsed["Product Name"]
                        if("Trade Name" in parsed.keys()):
                            obj["name"] = parsed["Trade Name"]
                        if("CAS Number" in parsed.keys()):
                            obj["identifier"] = parsed["CAS Number"]
                        arr.append(obj)
            return(arr)
"""
Main function to grab the WHO records for clinical trials.
"""

def getWHOTrials(url, country_file, col_names, returnDF=False):
    today = date.today().strftime("%Y-%m-%d")
    # Natural Earth file to normalize country names.
    ctry_dict = pd.read_csv(country_file).set_index("name").to_dict(orient="index")

    raw = pd.read_csv(WHO_URL, dtype={"Date registration3": str})
    # Remove the data from ClinicalTrials.gov
    df = raw.loc[raw["Source Register"] != "ClinicalTrials.gov", :]
    df = df.copy()

    df["@type"] = "ClinicalTrial"
    df["_id"] = df.TrialID
    df["identifier"] = df.TrialID
    df["url"] = df["web address"]
    df["identifierSource"] = df["Source Register"].apply(convertSource)
    df["name"] = df["Scientific title"].apply(lambda x: x.strip())
    df["alternateName"] = df.apply(
        lambda x: listify(x, ["Acronym", "Public title"]), axis=1)
    df["abstract"] = None
    df["description"] = None
    df["isBasedOn"] = None
    df["relatedTo"] = None
    df["keywords"] = None
    df["funding"] = df["Primary sponsor"].apply(
        lambda x: [{"funder": [{"@type": "Organization", "name": x, "role": "lead sponsor"}]}])
    df["hasResults"] = df["results yes no"].apply(binarize)
    df["dateCreated"] = df["Date registration3"].apply(
        lambda x: formatDate(x, "%Y%m%d"))
    df["dateModified"] = df["Last Refreshed on"].apply(
        lambda x: formatDate(x, "%d %B %Y"))
    df["datePublished"] = None
    df["curatedBy"] = df["Export date"].apply(lambda x: {"@type": "Organization", "name": "WHO International Clinical Trials Registry Platform", "identifier": "ICTRP",
                                                         "url": "https://www.who.int/ictrp/en/", "versionDate": formatDate(x, "%m/%d/%Y %H:%M:%S %p"), "curationDate": today})
    df["studyLocation"] = df.Countries.apply(lambda x: splitCountries(x, ctry_dict))
    # df["healthCondition"] = None
    df["healthCondition"] = df.Condition.apply(splitCondition)
    df["studyStatus"] = df.apply(getWHOStatus, axis=1)
    df["studyEvent"] = df.apply(getWHOEvents, axis=1)
    df["eligibilityCriteria"] = df.apply(getWHOEligibility, axis=1)
    df["author"] = df.apply(getWHOAuthors, axis=1)
    df["studyDesign"] = df.apply(getWHODesign, axis=1)
    df["armGroup"] = df.apply(getArms, axis=1)
    df["interventions"] = df.apply(getInterventions, axis=1)
    df["interventionText"] = df.Intervention # creating a copy, since parsing is icky.
    df["outcome"] = df["Primary outcome"].apply(getOutcome)

    # Double check that the numbers all agree
    if(sum(df.duplicated(subset="_id"))):
        dupes = df[df.duplicated(subset="_id")]
        print(
            f"\n\n\nERROR: {sum(df.duplicated(subset='_id'))} duplicate IDs found:")
        print(dupes._id)
    if(returnDF):
        return(df)
    else:
        return df[col_names].to_json(orient="records")



# who = getWHOTrials(WHO_URL, COUNTRY_FILE, COL_NAMES, True)
# who.iloc[2]["funding"]

def load_annotations():
    docs = getWHOTrials(WHO_URL,COUNTRY_FILE, COL_NAMES)
    for doc in json.loads(docs):
        yield doc

# who.sample(1).iloc[0]['studyDesign']
# who.sample(5).to_json("/Users/laurahughes/GitHub/umin-clinical-trials/outputs/WHO_parsed_sample.json", orient="records")
# who[who.identifier =="EUCTR2020-001505-22-ES"].iloc[0]["studyDesign"]
