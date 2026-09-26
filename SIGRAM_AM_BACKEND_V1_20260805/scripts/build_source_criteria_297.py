"""Construye el catálogo ejecutable directamente desde las 297 filas médicas.

El archivo generado conserva una regla por fila fuente. No utiliza ni necesita
los códigos internos históricos Bxx/STOPP-x/START-x del prototipo.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


def canonical(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


DRUG_NAMES = """
acepromazina aclidinio aceite mineral alfacalcidol aliskireno alopurinol alprazolam
amilorida amiodarona amitriptilina amoxapina aniracetam apixaban aripiprazol
astemizol atropina avanafilo azitromicina baclofeno bambuterol benzatropina
beclometasona bisoprolol bromfeniramina budesonida buprenorfina butalbital
canagliflozina carbamazepina carvedilol cariprazina carisoprodol ciclesonida
ciclobenzaprina cilostazol cimetidina ciprofloxacino ciproheptadina citalopram
clidinio clomipramina clonazepam clonidina clobazam clordiazepoxido clorfeniramina
clorpromazina clorpropamida clorazepato clorzoxazona clozapina colchicina
desipramina desmopresina dexametasona dexlansoprazol dextrometorfano diazepam
diciclomina diclofenaco difenhidramina diflunisal digoxina dihidroergotoxina
diltiazem dimenhidrinato dofetilida donepezilo doxazosina doxepina doxilamina
dronedarona duloxetina edoxaban enoxaparina eplerenona ertugliflozina escitalopram
escopolamina esomeprazol espironolactona estazolam estradiol etodolaco
empagliflozina famotidina febuxostat fenilpiracetam fenitoina fenobarbital
fentanilo fesoterodina finasterida flavoxato flupentixol flufenazina flurbiprofeno
fluticasona fondaparinux formoterol fosfatidilserina gabapentina galantamina
ginkgo glibenclamida gliclazida glicopirronio glimepirida glipizida guanfacina
haloperidol hidroxicina hiosciamina hiosciamina homatropina ibuprofeno imipramina
indacaterol indometacina indoramina insulina ipratropio irbesartan itraconazol
ketoconazol ketorolaco lactulosa lansoprazol levetiracetam levodopa
levomepromazina levotiroxina lidocaina litio lorazepam lurasidona macrogol
meclizina megestrol meloxicam memantina meperidina metaxalona metformina
metilcelulosa metildopa metiltestosterona metocarbamol metoclopramida metoprolol
metotrexato midazolam mirabegron mirtazapina misoprostol modafinilo mometasona
morfina moxonidina nabumetona naproxeno nebivolol nifedipino nizatidina
nitrofurantoina nortriptilina olanzapina olodaterol omeprazol ondansetron
orfenadrina oxaprozina oxazepam oxibutinina oxicodona pantoprazol paracetamol
paroxetina pentazocina perfenazina petidina pimavanserina pioglitazona
piperotiazina piracetam piroxicam pramipexol pramiracetam prasugrel prazocina
prazosina pregabalina primidona probenecid proclorperazina prociclidina
promazina prometazina propranolol quetiapina quinina rabeprazol ranolazina
rimenidina risperidona rivaroxaban rivastigmina ropinirol rosiglitazona
rotigotina sacubitrilo salmeterol sildenafilo silodosina solifenacina sorbitol
sulfametoxazol sulindaco tadalafilo tamoxifeno tamsulosina tapentadol temazepam
teofilina terazosina teriparatida testosterona tiazolidinediona ticagrelor
ticlopidina tioridazina tiotropio tizanidina tolterodina tramadol triamtereno
triazolam trimetoprima triprolidina trospio umeclidinio valsartan vardenafilo
vasopresina venlafaxina verapamilo warfarina zaleplon ziprasidona zolpidem
zopiclona
""".split()


# Exposiciones que el texto expresa como terapia, formulación o clase amplia y
# que no se pueden recuperar de forma fiable con el extractor léxico general.
EXPOSURE_OVERRIDES = {
    "STOPP-023": {"groups": ["IECA", "ARA-II", "ARNI", "BETABLOQUE", "BLOQUEADORES DE CANALES DE CALCIO", "DIURETICOS", "ANTIHIPERTENSIVOS DE ACCION CENTRAL", "VASODILATADORES"]},
    "STOPP-079": {"names": ["fumarato ferroso", "sulfato ferroso", "gluconato ferroso"], "groups": ["PREPARADOS DE HIERRO"]},
    "STOPP-091": {"groups": ["CORTICOSTEROIDES SISTEMICOS"]},
    "STOPP-092": {"groups": ["CORTICOSTEROIDES SISTEMICOS"]},
    "STOPP-104": {"groups": ["ANTIBIOTICOS/ANTIINFECCIOSOS"]},
    "STOPP-117": {"groups": ["VASODILATADORES"]},
    "STOPP-123": {"groups": ["BLOQUEADORES ALFA-1"]},
    "STOPP-125": {"groups": ["ANTIHIPERTENSIVOS DE ACCION CENTRAL"]},
    "START-002": {"groups": ["IECA", "ARA-II", "ARNI", "BETABLOQUE", "BLOQUEADORES DE CANALES DE CALCIO", "DIURETICOS", "ANTIHIPERTENSIVOS DE ACCION CENTRAL", "VASODILATADORES"]},
    "START-012": {"names": ["hierro sacarosa", "carboximaltosa ferrica", "hierro dextrano"]},
    "START-023": {"groups": ["QUELANTES DE FOSFATO"]},
    "START-024": {"groups": ["ANALOGOS DE ERITROPOYETINA"]},
    "START-031": {"names": ["lactobacillus", "saccharomyces boulardii", "probiótico"]},
    "START-035": {"names": ["oxigeno medicinal"], "groups": ["GASES MEDICINALES: OXIGENO"]},
    "START-038": {"names": ["colecalciferol", "ergocalciferol"], "groups": ["VITAMINA D"]},
    "START-040": {"names": ["colecalciferol", "ergocalciferol"], "groups": ["VITAMINA D"]},
    "START-041": {"groups": ["FARMACOS ANTIRRESORTIVOS"]},
    "START-042": {"groups": ["FARMACOS ANTIRRESORTIVOS"]},
    "START-044": {"names": ["acido folico"], "groups": ["ACIDO FOLICO", "VITAMINA B9"]},
    "Beers-006": {"names": ["dipiridamol"]},
    "Beers-019": {"names": ["meprobamato"]},
    "Beers-025": {"names": ["tiroides disecada"]},
    "Beers-027": {"names": ["somatropina"], "groups": ["HORMONAS DEL CRECIMIENTO", "SOMATROPINAS"]},
}


# En una interacción, cada sublista representa un lado obligatorio. Esto evita
# falsos positivos como dos alternativas pertenecientes al mismo lado.
INTERACTION_CONFIG = {
    "STOPP-006": {"mode": "required_sets", "sets": [
        {"groups": ["BETABLOQUE"]}, {"names": ["verapamilo", "diltiazem"]},
    ]},
    "STOPP-016": {"mode": "required_sets", "sets": [
        {"names": ["espironolactona", "eplerenona"], "groups": ["ANTAGONISTAS DE ALDOSTERONA", "MINERALOCORTICOIDE"]},
        {"names": ["amilorida", "triamtereno"], "groups": ["IECA", "ARA-II", "AHORRADORES DE POTASIO"]},
    ]},
    "STOPP-027": {"mode": "required_sets", "sets": [{"names": ["aspirina", "acido acetilsalicilico"]}, {"names": ["clopidogrel"]}]},
    "STOPP-028": {"mode": "required_sets", "sets": [{"groups": ["ANTIAGREGANTES"]}, {"groups": ["ANTICOAGULANTES", "ANTAGONISTAS DE LA VITAMINA K", "INHIBIDORES DIRECTOS DE TROMBINA", "FACTOR XA"]}]},
    "STOPP-029": {"mode": "required_sets", "sets": [{"groups": ["ANTIAGREGANTES"]}, {"groups": ["ANTICOAGULANTES", "ANTAGONISTAS DE LA VITAMINA K", "INHIBIDORES DIRECTOS DE TROMBINA", "FACTOR XA"]}]},
    "STOPP-034": {"mode": "required_sets", "sets": [{"groups": ["AINE", "ANTIINFLAMATORIOS NO ESTEROIDEOS"]}, {"groups": ["ANTICOAGULANTES", "ANTAGONISTAS DE LA VITAMINA K", "INHIBIDORES DIRECTOS DE TROMBINA", "FACTOR XA"]}]},
    "STOPP-036": {"mode": "required_sets", "sets": [{"groups": ["ISRS"]}, {"groups": ["ANTICOAGULANTES", "ANTAGONISTAS DE LA VITAMINA K", "INHIBIDORES DIRECTOS DE TROMBINA", "FACTOR XA"]}]},
    "STOPP-037": {"mode": "required_sets", "sets": [{"names": ["dabigatran"]}, {"names": ["diltiazem", "verapamilo"]}]},
    "STOPP-038": {"mode": "required_sets", "sets": [
        {"names": ["apixaban", "dabigatran", "edoxaban", "rivaroxaban"]},
        {"names": ["amiodarona", "azitromicina", "carvedilol", "ciclosporina", "dronedarona", "itraconazol", "ketoconazol", "quinina", "ranolazina", "tamoxifeno", "ticagrelor", "verapamilo"], "groups": ["MACROLIDOS"]},
    ]},
    "STOPP-058": {"mode": "required_sets", "sets": [
        {"groups": ["INHIBIDORES DE ACETILCOLINESTERASA"]},
        {"names": ["digoxina", "diltiazem", "verapamilo"], "groups": ["BETABLOQUE"]},
    ]},
    "STOPP-094": {"mode": "required_sets", "sets": [{"groups": ["AINE", "ANTIINFLAMATORIOS NO ESTEROIDEOS"]}, {"groups": ["CORTICOSTEROIDES SISTEMICOS"]}]},
    "STOPP-133": {"mode": "count", "groups": ["ANTICOLINERG", "ANTIMUSCARIN", "ANTIDEPRESIVOS TRICICLICOS", "ANTIHISTAMINICOS H1 DE PRIMERA GENERACION", "ANTIPSICOTICOS"], "minimum": 2},
    "Beers-072": {"mode": "count", "names": ["aliskireno", "amilorida", "triamtereno"], "groups": ["IECA", "ARA-II", "ARNI", "AHORRADORES DE POTASIO"], "minimum": 2},
    "Beers-073": {"mode": "required_sets", "sets": [{"groups": ["OPIOIDES"]}, {"groups": ["BENZODIACEPINAS"]}]},
    "Beers-074": {"mode": "required_sets", "sets": [{"groups": ["OPIOIDES"]}, {"names": ["gabapentina", "pregabalina"], "groups": ["GABAPENTINOIDES"]}]},
    "Beers-075": {"mode": "count", "groups": ["ANTICOLINERG", "ANTIMUSCARIN"], "minimum": 2},
    "Beers-076": {"mode": "count", "groups": ["ANTIEPILEPT", "ANTICONVULS", "GABAPENTINO", "ANTIDEPRES", "ANTIPSICOT", "BENZODIACEP", "HIPNOTICOS NO BENZODIACEPINICOS", "OPIOIDE", "RELAJANTES MUSCULOESQUELETICOS"], "minimum": 3},
    "Beers-077": {"mode": "required_sets", "sets": [{"names": ["litio"]}, {"groups": ["IECA", "ARA-II", "ARNI", "DIURETICOS DE ASA"]}]},
    "Beers-078": {"mode": "required_sets", "sets": [{"groups": ["BLOQUEADORES ALFA-1 PERIFERICOS"]}, {"groups": ["DIURETICOS DE ASA"]}]},
    "Beers-079": {"mode": "required_sets", "sets": [{"names": ["fenitoina"]}, {"names": ["trimetoprima sulfametoxazol", "cotrimoxazol"]}]},
    "Beers-080": {"mode": "required_sets", "sets": [{"names": ["teofilina"]}, {"names": ["cimetidina"]}]},
    "Beers-081": {"mode": "required_sets", "sets": [{"names": ["teofilina"]}, {"names": ["ciprofloxacino"]}]},
    "Beers-082": {"mode": "required_sets", "sets": [
        {"names": ["warfarina"]},
        {"names": ["amiodarona", "ciprofloxacino", "claritromicina", "eritromicina", "trimetoprima sulfametoxazol", "cotrimoxazol"], "groups": ["ISRS"]},
    ]},
}


CO_TREATMENT_OMISSIONS = {
    "STOPP-128": {
        "primary": {"groups": ["OPIOIDES"]},
        "required": {"groups": ["LAXANTES"]},
        "primary_label": "opioide regular",
        "required_label": "laxante concomitante",
    },
    "STOPP-129": {
        "primary": {"groups": ["OPIOIDES"]},
        "required": {"names": ["opioide de accion corta"]},
        "primary_label": "opioide de acción prolongada",
        "required_label": "opioide de acción corta para dolor irruptivo",
    },
}


PRESENCE_FIELDS = {
    "START-001": ("criterion_start_001_treatment_present", "Fármaco indicado ya iniciado"),
    "START-032": ("criterion_start_032_eradication_therapy_present", "Terapia completa de erradicación de H. pylori presente"),
}


NAME_ALIASES = {
    "acido acetilsalicilico": ["aspirina", "acido acetilsalicilico"],
    "dabigatran": ["dabigatran"],
    "edoxaban": ["edoxaban"],
    "rivaroxaban": ["rivaroxaban"],
    "pramipexol": ["pramipexol"],
    "prazosina": ["prazosina", "prazocina"],
    "trimetoprima sulfametoxazol": ["trimetoprima sulfametoxazol", "cotrimoxazol"],
    "sacubitrilo valsartan": ["sacubitrilo valsartan"],
    "dextrometorfano quinidina": ["dextrometorfano quinidina"],
}


CLASS_PATTERNS = {
    "AINE": (["AINE", "ANTIINFLAMATORIOS NO ESTEROIDEOS"], ["ANTIINFLAMATORIOS NO ESTEROIDEOS"]),
    "BENZODIACEPINAS": (["BENZODIACEPINA"], ["BENZODIACEPINAS"]),
    "OPIOIDES": (["OPIOIDE"], ["OPIOIDES"]),
    "ANTIPSICOTICOS": (["ANTIPSICOTICO"], ["ANTIPSICOTICOS"]),
    "ANTIDEPRESIVOS": (["ANTIDEPRESIVO"], ["ANTIDEPRESIVOS"]),
    "ATC": (["ANTIDEPRESIVOS TRICICLICOS", "ATC", "ADT"], ["ANTIDEPRESIVOS TRICICLICOS"]),
    "ISRS": (["ISRS", "INHIBIDORES SELECTIVOS DE LA RECAPTACION DE SEROTONINA"], ["ISRS"]),
    "IRSN": (["IRSN", "SEROTONINA Y NORADRENALINA"], ["IRSN"]),
    "ANTIEPILEPTICOS": (["ANTIEPILEPTICO", "ANTICONVULSIVANTE"], ["ANTIEPILEPTICOS", "ANTICONVULSIVANTES"]),
    "GABAPENTINOIDES": (["GABAPENTINOIDE"], ["GABAPENTINOIDES"]),
    "ANTICOLINERGICOS": (["ANTICOLINERGIC", "ANTIMUSCARINIC"], ["ANTICOLINERGICOS", "ANTIMUSCARINICOS"]),
    "ANTIHISTAMINICOS_1G": (["ANTIHISTAMINICOS DE PRIMERA GENERACION"], ["ANTIHISTAMINICOS H1 DE PRIMERA GENERACION"]),
    "FARMACOS_Z": (["FARMACOS Z", "HIPNOTICOS NO BENZODIACEPINICOS"], ["HIPNOTICOS NO BENZODIACEPINICOS"]),
    "BETABLOQUEANTES": (["BETABLOQUEANTE", "BETABLOQUEADOR"], ["BETABLOQUEADORES"]),
    "IECA": (["IECA", "ENZIMA CONVERTIDORA DE ANGIOTENSINA"], ["IECA"]),
    "ARA_II": (["ARA II", "RECEPTORES DE ANGIOTENSINA"], ["ARA II"]),
    "ARNI": (["ARNI", "ANGIOTENSINA NEPRILISINA"], ["ARNI"]),
    "DIURETICOS_ASA": (["DIURETICO DEL ASA", "DIURETICOS DE ASA"], ["DIURETICOS DE ASA"]),
    "DIURETICOS_TIAZIDICOS": (["DIURETICO TIAZIDICO"], ["DIURETICOS TIAZIDICOS"]),
    "AHORRADORES_POTASIO": (["AHORRADOR DE POTASIO", "AHORRADORES DE POTASIO"], ["DIURETICOS AHORRADORES DE POTASIO"]),
    "ALDOSTERONA": (["ANTAGONISTAS DE LA ALDOSTERONA", "RECEPTORES DE MINERALOCORTICOIDES"], ["ANTAGONISTAS DE ALDOSTERONA", "MINERALOCORTICOIDES"]),
    "ANTIAGREGANTES": (["ANTIAGREGANTE"], ["ANTIAGREGANTES PLAQUETARIOS"]),
    "ANTICOAGULANTES": (["ANTICOAGULANTE", "ANTAGONISTAS DE LA VITAMINA K", "FACTOR XA", "TROMBINA"], ["ANTICOAGULANTES"]),
    "ESTATINAS": (["ESTATINA"], ["ESTATINAS"]),
    "IBP": (["INHIBIDOR DE LA BOMBA DE PROTONES", "IBP"], ["INHIBIDORES DE LA BOMBA DE PROTONES"]),
    "ANTAGONISTAS_H2": (["ANTAGONISTA H2", "RECEPTORES H2"], ["ANTAGONISTAS DE RECEPTORES H2"]),
    "CORTICOIDES_SISTEMICOS": (["CORTICOSTEROIDES SISTEMICOS", "CORTICOIDES SISTEMICOS", "CORTICOSTEROIDES ORALES", "CORTICOSTEROIDES PARENTERALES"], ["CORTICOSTEROIDES SISTEMICOS"]),
    "SULFONILUREAS": (["SULFONILUREA"], ["SULFONILUREAS"]),
    "BISFOSFONATOS": (["BIFOSFONATO", "BISFOSFONATO"], ["BISFOSFONATOS"]),
    "FAME": (["FAME", "ANTIRREUMATICO MODIFICADOR"], ["FARMACOS ANTIRREUMATICOS MODIFICADORES"]),
    "XANTINA_OXIDASA": (["XANTINA OXIDASA"], ["INHIBIDORES DE XANTINA OXIDASA"]),
    "LAXANTES": (["LAXANTE"], ["LAXANTES"]),
    "LAMA": (["LAMA", "ANTAGONISTA MUSCARINICO DE ACCION PROLONGADA"], ["ANTAGONISTAS MUSCARINICOS DE ACCION PROLONGADA"]),
    "LABA": (["LABA", "AGONISTA BETA 2 DE ACCION PROLONGADA"], ["AGONISTAS BETA 2 DE ACCION PROLONGADA"]),
    "SGLT2": (["SGLT2", "COTRANSPORTADOR DE SODIO GLUCOSA"], ["INHIBIDORES SGLT2"]),
    "ALFA_1": (["BLOQUEADOR ALFA 1", "ANTAGONISTAS DE LOS RECEPTORES ALFA 1"], ["BLOQUEADORES ALFA 1"]),
    "PDE5": (["FOSFODIESTERASA TIPO 5"], ["INHIBIDORES PDE5"]),
    "ESTROGENOS": (["ESTROGENO"], ["ESTROGENOS"]),
    "ANDROGENOS": (["ANDROGENO"], ["ANDROGENOS"]),
    "FENOTIAZINAS": (["FENOTIAZINA"], ["FENOTIAZINAS"]),
    "LEVODOPA_DOPAMINA": (["LEVODOPA", "L DOPA", "AGONISTAS DE LA DOPAMINA"], ["DOPAMINERGICOS"]),
    "COLINESTERASA": (["ACETILCOLINESTERASA", "COLINESTERASA", "IACHE"], ["INHIBIDORES DE ACETILCOLINESTERASA"]),
    "RELAJANTES_MUSCULARES": (["RELAJANTE MUSCULAR", "RELAJANTES MUSCULOESQUELETICOS"], ["RELAJANTES MUSCULOESQUELETICOS"]),
    "INSULINA": (["INSULINA"], ["INSULINAS"]),
    "VACUNAS": (["VACUNA"], ["VACUNAS"]),
}


COMMON_FIELDS = {
    "CAIDAS": ("falls_history", "Antecedentes de caídas o fracturas", "boolean"),
    "DEMENCIA": ("cognitive_impairment", "Demencia o deterioro cognitivo", "boolean"),
    "DETERIORO COGNITIVO": ("cognitive_impairment", "Demencia o deterioro cognitivo", "boolean"),
    "DELIRIUM": ("delirium", "Delirium o riesgo alto de delirium", "boolean"),
    "SINCOPE": ("syncope_history", "Antecedente de síncope", "boolean"),
    "HIPOTENSION ORTOSTATICA": ("orthostatic_hypotension", "Hipotensión ortostática", "boolean"),
    "ESTRENIMIENTO": ("constipation", "Estreñimiento crónico", "boolean"),
    "ENFERMEDAD ULCEROSA PEPTICA": ("peptic_ulcer_history", "Úlcera o sangrado gastrointestinal", "boolean"),
    "ULCERA": ("peptic_ulcer_history", "Úlcera o sangrado gastrointestinal", "boolean"),
    "PARKINSON": ("parkinsonism", "Enfermedad de Parkinson o parkinsonismo", "boolean"),
    "GLAUCOMA DE ANGULO ESTRECHO": ("narrow_angle_glaucoma", "Glaucoma de ángulo estrecho", "boolean"),
    "FIBRILACION AURICULAR": ("atrial_fibrillation", "Fibrilación auricular", "boolean"),
    "INSUFICIENCIA CARDIACA": ("heart_failure_diagnosis", "Insuficiencia cardíaca", "boolean"),
    "FRACCION DE EYECCION REDUCIDA": ("reduced_ejection_fraction", "Fracción de eyección reducida", "boolean"),
    "GOTA": ("gout_history", "Antecedente de gota", "boolean"),
    "DIABETES": ("diabetes_diagnosis", "Diabetes mellitus", "boolean"),
    "OSTEOARTRITIS": ("osteoarthritis", "Osteoartritis", "boolean"),
    "HIPERPLASIA BENIGNA": ("bph_urinary_symptoms", "Síntomas por hiperplasia prostática", "boolean"),
    "INCONTINENCIA URINARIA": ("urinary_incontinence", "Incontinencia urinaria", "boolean"),
    "ENFERMEDAD HEPATICA CRONICA": ("chronic_liver_disease", "Enfermedad hepática crónica", "boolean"),
    "HIPONATREMIA": ("sodium_mmol_l", "Sodio sérico", "number"),
    "HIPERPOTASEMIA": ("potassium_mmol_l", "Potasio sérico", "number"),
    "HIPOPOTASEMIA": ("potassium_mmol_l", "Potasio sérico", "number"),
    "HIPERCALCEMIA": ("corrected_calcium_mmol_l", "Calcio corregido", "number"),
    "HIPOCALCEMIA": ("corrected_calcium_mmol_l", "Calcio corregido", "number"),
}


RENAL_SPECIALS = {
    "STOPP-066": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "STOPP-067": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "STOPP-068": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 15},
    "STOPP-069": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 50},
    "STOPP-070": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 10},
    "STOPP-071": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "STOPP-072": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "STOPP-073": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 45},
    "STOPP-074": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "STOPP-075": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "START-008": {"metric": "egfr_ml_min_1_73m2", "operator": "gt", "value": 30},
    "START-022": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "START-023": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "START-024": {"metric": "egfr_ml_min_1_73m2", "operator": "lt", "value": 30},
    "START-050": {"metric": "egfr_ml_min_1_73m2", "operator": "gte", "value": 30},
    "Beers-002": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-083": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-084": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-085": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-086": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-087": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-088": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 60},
    "Beers-089": {"metric": "creatinine_clearance_ml_min", "operator": "outside", "min": 15, "max": 95},
    "Beers-090": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-091": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-092": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 51},
    "Beers-093": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-094": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-095": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 60},
    "Beers-096": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-097": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 60},
    "Beers-098": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 80},
    "Beers-099": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-100": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 60},
    "Beers-101": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-102": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-103": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 50},
    "Beers-104": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 50},
    "Beers-105": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 50},
    "Beers-106": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
    "Beers-107": {"metric": "creatinine_clearance_ml_min", "operator": "lt", "value": 30},
}


STRUCTURED_OVERRIDES = {
    "STOPP-007": [{"field": "heart_rate_bpm", "operator": "lt", "value": 50, "label": "Frecuencia cardíaca"}],
    "STOPP-015": [{"field": "potassium_mmol_l", "operator": "gt", "value": 5.5, "label": "Potasio sérico"}],
    "STOPP-043": [
        {"field": "systolic_bp_mm_hg", "operator": "gt", "value": 180, "label": "Presión arterial sistólica"},
        {"field": "diastolic_bp_mm_hg", "operator": "gt", "value": 105, "label": "Presión arterial diastólica", "join": "or"},
    ],
    "STOPP-046": [{"field": "sodium_mmol_l", "operator": "lt", "value": 130, "label": "Sodio sérico"}],
    "STOPP-079": [{"field": "daily_elemental_iron_mg", "operator": "gt", "value": 200, "label": "Hierro elemental diario (mg)"}],
    "STOPP-089": [
        {"field": "systolic_bp_mm_hg", "operator": "gt", "value": 170, "label": "Presión arterial sistólica"},
        {"field": "diastolic_bp_mm_hg", "operator": "gt", "value": 100, "label": "Presión arterial diastólica", "join": "or"},
    ],
    "STOPP-113": [{"field": "tsh_miu_l", "operator": "lt", "value": 10, "label": "TSH"}],
    "STOPP-117": [
        {"field": "orthostatic_systolic_drop_mm_hg", "operator": "gte", "value": 20, "label": "Caída ortostática de presión sistólica"},
        {"field": "orthostatic_diastolic_drop_mm_hg", "operator": "gte", "value": 10, "label": "Caída ortostática de presión diastólica", "join": "or"},
    ],
    "STOPP-132": [{"field": "daily_dose_mg", "operator": "gte", "value": 3000, "label": "Dosis diaria de paracetamol"}],
    "START-002": [
        {"field": "systolic_bp_mm_hg", "operator": "gt", "value": 140, "label": "Presión arterial sistólica"},
        {"field": "diastolic_bp_mm_hg", "operator": "gt", "value": 90, "label": "Presión arterial diastólica", "join": "or"},
    ],
    "START-022": [{"field": "corrected_calcium_mmol_l", "operator": "lt", "value": 2.10, "label": "Calcio corregido"}],
    "START-023": [{"field": "phosphate_mmol_l", "operator": "gt", "value": 1.76, "label": "Fosfato sérico"}],
    "START-025": [{"field": "proteinuria_mg_24h", "operator": "gt", "value": 300, "label": "Albúmina urinaria en 24 horas"}],
    "START-035": [{"field": "po2_mmhg", "operator": "lt", "value": 60, "label": "pO2"}],
    "START-050": [{"field": "proteinuria_mg_24h", "operator": "gt", "value": 30, "label": "Microalbuminuria/proteinuria en 24 horas"}],
}


CONTEXT_OVERRIDES = {
    **{
        f"STOPP-{number:03d}": [
            {"field": "falls_history", "label": "Antecedentes de caídas o fracturas", "expected": True}
        ]
        for number in range(115, 127)
    },
    **{
        f"Beers-{number:03d}": [
            {"field": "falls_history", "label": "Antecedentes de caídas o fracturas", "expected": True}
        ]
        for number in range(53, 60)
    },
    **{
        f"Beers-{number:03d}": [
            {"field": "delirium", "label": "Delirium o riesgo alto de delirium", "expected": True}
        ]
        for number in range(43, 49)
    },
    **{
        f"Beers-{number:03d}": [
            {"field": "cognitive_impairment", "label": "Demencia o deterioro cognitivo", "expected": True}
        ]
        for number in range(49, 53)
    },
    "STOPP-054": [
        {"field": "delirium", "label": "Delirium", "expected": True, "join": "or"},
        {"field": "cognitive_impairment", "label": "Demencia o deterioro cognitivo", "expected": True, "join": "or"},
    ],
    "STOPP-076": [{"field": "parkinsonism", "label": "Enfermedad de Parkinson o parkinsonismo", "expected": True}],
    "STOPP-087": [{"field": "respiratory_failure", "label": "Insuficiencia respiratoria", "expected": True}],
    "STOPP-097": [{"field": "cognitive_impairment", "label": "Demencia o deterioro cognitivo", "expected": True}],
    "STOPP-098": [{"field": "narrow_angle_glaucoma", "label": "Glaucoma de ángulo estrecho", "expected": True}],
    "STOPP-100": [{"field": "constipation", "label": "Estreñimiento", "expected": True}],
    "STOPP-101": [
        {"field": "orthostatic_hypotension", "label": "Hipotensión ortostática sintomática", "expected": True, "join": "or"},
        {"field": "syncope_history", "label": "Antecedente de síncope", "expected": True, "join": "or"},
    ],
    "Beers-060": [{"field": "parkinsonism", "label": "Enfermedad de Parkinson", "expected": True}],
    "Beers-061": [{"field": "parkinsonism", "label": "Enfermedad de Parkinson", "expected": True}],
}


DIRECT_WITHOUT_CONTEXT = {
    "STOPP-003", "STOPP-006", "STOPP-014", "STOPP-030", "STOPP-034", "STOPP-037", "STOPP-038", "STOPP-079", "STOPP-083", "STOPP-094", "STOPP-133",
    "Beers-001", "Beers-007", "Beers-008", "Beers-009", "Beers-013", "Beers-014", "Beers-015", "Beers-016", "Beers-017", "Beers-018", "Beers-019", "Beers-020", "Beers-024", "Beers-025", "Beers-026", "Beers-028", "Beers-030", "Beers-031", "Beers-032", "Beers-034", "Beers-035", "Beers-036", "Beers-073", "Beers-074", "Beers-075", "Beers-076", "Beers-077", "Beers-078", "Beers-079", "Beers-080", "Beers-081", "Beers-082",
}


def exposure_segment(description: str, criterion_type: str) -> str:
    text = description.split("EXCEPCIÓN:", 1)[0]
    if criterion_type == "START":
        pieces = re.split(r"\s+(?:en|para|cuando|al iniciar|despues de|después de)\s+", text, maxsplit=1, flags=re.I)
        return pieces[0]
    pieces = re.split(r"\s+(?:debido a|porque|por riesgo|riesgo de|mayor riesgo|no hay evidencia)\s+", text, maxsplit=1, flags=re.I)
    return pieces[0]


def extract_exposure(description: str, criterion_type: str) -> tuple[list[str], list[str]]:
    segment = canonical(exposure_segment(description, criterion_type))
    names: set[str] = set()
    for drug in DRUG_NAMES:
        if canonical(drug) in segment:
            names.add(drug)
    for display, aliases in NAME_ALIASES.items():
        if any(canonical(alias) in segment for alias in aliases):
            names.add(display)
    groups: set[str] = set()
    for _, (patterns, group_terms) in CLASS_PATTERNS.items():
        if any(canonical(pattern) in segment for pattern in patterns):
            groups.update(group_terms)
    return sorted(names), sorted(groups)


def requirement(field: str, label: str, data_type: str = "boolean") -> dict:
    return {"field": field, "label": label, "data_type": data_type}


def build_rule(row: dict) -> dict:
    criterion_type = str(row["criterion"])
    number = int(row["source_code"])
    source_id = f"{criterion_type}-{number:03d}" if criterion_type != "Beers" else f"Beers-{number:03d}"
    description = str(row["source_description"]).strip()
    canonical_description = canonical(description)
    medication_terms, group_terms = extract_exposure(description, criterion_type)

    exposure_override = EXPOSURE_OVERRIDES.get(source_id, {})
    medication_terms = sorted(set(medication_terms + exposure_override.get("names", [])))
    group_terms = sorted(set(group_terms + exposure_override.get("groups", [])))

    if source_id in {"STOPP-001", "STOPP-002"}:
        medication_terms = []
        group_terms = []

    interaction = "INTERACCIONES" in canonical(str(row.get("classification") or ""))
    kind = "omission" if criterion_type == "START" else "avoidance"
    if source_id == "STOPP-001":
        kind = "missing_indication"
    elif source_id == "STOPP-002":
        kind = "excess_duration"
    elif source_id == "STOPP-003":
        kind = "duplicate_class"
    elif source_id in CO_TREATMENT_OMISSIONS:
        kind = "co_treatment_omission"
    elif interaction:
        kind = "interaction"

    requirements: list[dict] = []
    structured_conditions = list(STRUCTURED_OVERRIDES.get(source_id, []))
    context_conditions = list(CONTEXT_OVERRIDES.get(source_id, []))
    interaction_config = INTERACTION_CONFIG.get(source_id)
    co_treatment_config = CO_TREATMENT_OMISSIONS.get(source_id)
    presence_field = PRESENCE_FIELDS.get(source_id)
    renal = RENAL_SPECIALS.get(source_id)
    if renal:
        metric = renal["metric"]
        label = "TFGe (mL/min/1.73 m²)" if metric.startswith("egfr") else "Depuración de creatinina, CrCl (mL/min)"
        requirements.append(requirement(metric, label, "number"))

    for condition in structured_conditions:
        data_type = "number" if condition["operator"] in {"lt", "lte", "gt", "gte", "between", "outside"} else "boolean"
        requirements.append(requirement(condition["field"], condition["label"], data_type))
    for condition in context_conditions:
        requirements.append(requirement(condition["field"], condition["label"], "boolean"))
    if presence_field:
        requirements.append(requirement(presence_field[0], presence_field[1], "boolean"))

    common_fields: list[dict] = []
    for phrase, (field, label, data_type) in COMMON_FIELDS.items():
        if phrase in canonical_description and field not in {item["field"] for item in requirements}:
            common_fields.append(requirement(field, label, data_type))

    # Los datos comunes se conservan como evidencia de apoyo. No se vuelven
    # obligatorios si la frase aparece únicamente en el fundamento clínico.

    needs_specific_fact = source_id not in DIRECT_WITHOUT_CONTEXT and not context_conditions and not (
        renal and criterion_type != "START" and not structured_conditions
    )
    if kind in {"missing_indication", "excess_duration", "duplicate_class", "co_treatment_omission"}:
        needs_specific_fact = False
    if kind == "interaction" and source_id in DIRECT_WITHOUT_CONTEXT:
        needs_specific_fact = False

    condition_field = None
    if needs_specific_fact:
        condition_field = f"criterion_{canonical(source_id).lower().replace(' ', '_')}_condition_met"
        requirements.append(
            requirement(
                condition_field,
                f"Condición clínica específica confirmada para {source_id}",
                "boolean",
            )
        )

    exception_field = None
    if "EXCEPCION" in canonical_description:
        exception_field = f"criterion_{canonical(source_id).lower().replace(' ', '_')}_exception_applies"
        requirements.append(requirement(exception_field, f"Aplica una excepción explícita de {source_id}", "boolean"))

    if kind == "missing_indication":
        requirements.append(requirement("medication_facts.indication", "Indicación de cada medicamento", "text"))
    elif kind == "excess_duration":
        requirements.extend([
            requirement("medication_facts.duration_days", "Duración usada por medicamento (días)", "number"),
            requirement("medication_facts.recommended_duration_days", "Duración máxima recomendada (días)", "number"),
        ])
    elif kind == "duplicate_class":
        requirements.append(requirement("medication_facts.regular_use", "Uso regular o PRN por medicamento", "boolean"))
    elif kind == "co_treatment_omission":
        requirements.append(requirement("medication_facts.regular_use", "Uso regular o PRN por medicamento", "boolean"))
        if source_id == "STOPP-129":
            requirements.extend([
                requirement("criterion_stopp_129_long_acting_opioid_present", "Opioide de acción prolongada presente", "boolean"),
                requirement("criterion_stopp_129_short_acting_opioid_present", "Opioide de acción corta para dolor irruptivo presente", "boolean"),
            ])

    deduplicated_requirements = []
    seen_fields = set()
    for item in requirements:
        if item["field"] not in seen_fields:
            seen_fields.add(item["field"])
            deduplicated_requirements.append(item)

    logic_parts = ["Edad ≥ 65 años"]
    if kind == "omission":
        logic_parts.append("indicación clínica presente")
        logic_parts.append("tratamiento recomendado ausente")
    elif kind == "interaction":
        logic_parts.append("exposiciones concurrentes descritas en la fila")
    elif kind == "duplicate_class":
        logic_parts.append("dos o más medicamentos regulares de la misma clase; se excluye PRN")
    elif kind == "missing_indication":
        logic_parts.append("medicamento sin indicación documentada")
    elif kind == "excess_duration":
        logic_parts.append("duración usada superior a la duración máxima documentada")
    elif kind == "co_treatment_omission":
        logic_parts.append(f"{co_treatment_config['primary_label']} presente")
        logic_parts.append(f"{co_treatment_config['required_label']} ausente")
    else:
        logic_parts.append("medicamento o clase descrita presente")
    if renal:
        op_text = {"lt": "<", "lte": "≤", "gt": ">", "gte": "≥", "outside": "fuera de"}[renal["operator"]]
        value_text = f"{renal.get('value', '')}" if renal["operator"] != "outside" else f"{renal['min']}–{renal['max']}"
        logic_parts.append(f"{renal['metric']} {op_text} {value_text}")
    if structured_conditions:
        logic_parts.append("umbral(es) clínico(s) estructurado(s) de la descripción")
    if condition_field:
        logic_parts.append("confirmación del dato clínico específico de la fila")
    if exception_field:
        logic_parts.append("sin excepción explícita aplicable")

    return {
        "source_id": source_id,
        "sequence": int(row["n"]),
        "system": "beers" if criterion_type == "Beers" else "stopp_start",
        "criterion_type": criterion_type.upper() if criterion_type != "Beers" else "BEERS",
        "source_code": f"{number:03d}",
        "classification": row.get("classification"),
        "clinical_area": row.get("type"),
        "description": description,
        "doctor_review": row.get("doctor_review"),
        "doctor_observation": row.get("doctor_observation"),
        "source_comment": row.get("source_comment"),
        "age_min": 65,
        "kind": kind,
        "medication_terms": medication_terms,
        "group_terms": group_terms,
        "minimum_distinct_exposures": 2 if kind == "interaction" else 1,
        "interaction_config": interaction_config,
        "co_treatment_config": co_treatment_config,
        "presence_field": presence_field[0] if presence_field else None,
        "renal_condition": renal,
        "structured_conditions": structured_conditions,
        "context_conditions": context_conditions,
        "condition_field": condition_field,
        "exception_field": exception_field,
        "required_data": deduplicated_requirements,
        "supporting_data": common_fields,
        "logic_summary": " Y ".join(logic_parts),
        "implementation_status": "implemented_executable_rule",
        "implementation_mode": "automatic_with_structured_data",
        "test_case": {
            "expected_positive": "Agregar la exposición indicada, completar los datos requeridos y confirmar la condición específica cuando corresponda.",
            "expected_negative": "Retirar la exposición o registrar que la condición clínica no se cumple.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = payload["source_rows"]
    criteria = [build_rule(row) for row in rows]
    if len(criteria) != 297 or len({row["source_id"] for row in criteria}) != 297:
        raise SystemExit("El catálogo debe contener exactamente 297 identificadores únicos.")
    result = {
        "catalog_version": "2026-09-25-source-criteria-297-v2",
        "source_file": "match_criterios_evaluacion_sigram-AT20260925-Beers.xlsx",
        "source_row_count": len(criteria),
        "criteria": criteria,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "criteria": len(criteria),
        "with_renal_threshold": sum(bool(row["renal_condition"]) for row in criteria),
        "with_specific_fact": sum(bool(row["condition_field"]) for row in criteria),
        "with_exception": sum(bool(row["exception_field"]) for row in criteria),
        "interaction_rules": sum(row["kind"] == "interaction" for row in criteria),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
