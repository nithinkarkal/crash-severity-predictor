"""
Human-readable labels used by the frontend
Backend values remain unchanged; only the displayed labels are translated

IMPORTANT:
- These mappings are presentation/API mappings only.
- They MUST match the values expected by PredictionRequest.
- They must NOT modify the underlying BAAC/domain semantics.
- catv and atm use the transformed values produced by the training pipeline.
"""

from typing import Final

# ---------------------------------------------------------------------------
# Human-readable labels
# ---------------------------------------------------------------------------

FEATURES_LABELS: Final[dict[str, str]] = {
    "place": "Seat Position",
    "catu": "Road User",
    "sexe": "Sex",
    "secu1": "Safety Equipment",
    "year_acc": "Accident Year",
    "victim_age": "Victim Age",
    "nb_victim": "Number of Victims",
    "catv": "Vehicle Category",
    "obsm": "Mobile Obstacle",
    "motor": "Engine Type",
    "nb_vehicles": "Number of Vehicles",
    "catr": "Road Category",
    "circ": "Traffic Direction",
    "surf": "Road Surface",
    "situ": "Accident Location",
    "vma": "Speed Limit (km/h)",
    "jour": "Day",
    "mois": "Month",
    "lum": "Lighting",
    "dep": "Department",
    "com": "Municipality",
    "agg": "Urban Area",
    "int": "Intersection",
    "atm": "Weather",
    "col": "Collision Type",
    "lat": "Latitude",
    "long": "Longitude",
    "hour": "Hour",
}


# ---------------------------------------------------------------------------
# API / model value mappings
# ---------------------------------------------------------------------------

FEATURE_MAPS: Final[dict[str, dict[int, str]]] = {
    # -----------------------------------------------------------------------
    # USAGERS
    # -----------------------------------------------------------------------
    "place": {
        1: "Seat Position 1",
        2: "Seat Position 2",
        3: "Seat Position 3",
        4: "Seat Position 4",
        5: "Seat Position 5",
        6: "Seat Position 6",
        7: "Seat Position 7",
        8: "Seat Position 8",
        9: "Seat Position 9",
        10: "Pedestrian / Other",
    },
    "catu": {
        1: "Driver",
        2: "Passenger",
        3: "Pedestrian",
    },
    "sexe": {
        1: "Male",
        2: "Female",
    },
    "secu1": {
        0: "No safety equipment",
        1: "Seat belt",
        2: "Helmet",
        3: "Child restraint",
        4: "Reflective vest",
        5: "Airbag (2/3-wheel)",
        6: "Gloves (2/3-wheel)",
        7: "Gloves + airbag",
        8: "Not determinable",
        9: "Other",
    },
    # -----------------------------------------------------------------------
    # VEHICLES
    # -----------------------------------------------------------------------
    # IMPORTANT:
    # catv is NOT the raw BAAC catv code here.
    # The training pipeline remaps the original 40 categories to 0..6.
    #
    # Therefore the UI exposes the seven MODEL categories, not the raw
    # BAAC values.
    #
    # Source transformation:
    # common/data/clean_data.py -> process_vehicles()
    "catv": {
        0: "Indeterminable / Other",
        1: "Two/three-wheel & mobility",
        2: "Passenger car / Quadricycle",
        3: "Public transport / Rail",
        4: "Heavy vehicle / Agricultural",
        5: "Light utility vehicle",
        6: "Quad / Side-car",
    },
    "obsm": {
        0: "No mobile obstacle",
        1: "Pedestrian",
        2: "Vehicle",
        4: "Rail vehicle",
        5: "Domestic animal",
        6: "Wild animal",
        9: "Other",
    },
    "motor": {
        0: "Unknown",
        1: "Hydrocarbon",
        2: "Hybrid electric",
        3: "Electric",
        4: "Hydrogen",
        5: "Human-powered",
        6: "Other",
    },
    # -----------------------------------------------------------------------
    # ROAD / LOCATION
    # -----------------------------------------------------------------------
    "catr": {
        1: "Motorway",
        2: "National road",
        3: "Departmental road",
        4: "Municipal road",
        5: "Outside public road network",
        6: "Public car park",
        7: "Urban metropolitan road",
        9: "Other",
    },
    "circ": {
        1: "One-way",
        2: "Two-way",
        3: "Divided carriageways",
        4: "Variable-direction lanes",
    },
    "surf": {
        1: "Normal",
        2: "Wet",
        3: "Puddles",
        4: "Flooded",
        5: "Snow-covered",
        6: "Mud",
        7: "Icy",
        8: "Oil / Grease",
        9: "Other",
    },
    "situ": {
        1: "On roadway",
        2: "Emergency lane",
        3: "Shoulder",
        4: "Sidewalk",
        5: "Cycle lane",
        6: "Other special lane",
        8: "Other",
    },
    # -----------------------------------------------------------------------
    # ACCIDENT CONDITIONS
    # -----------------------------------------------------------------------
    "lum": {
        1: "Daylight",
        2: "Dawn / Dusk",
        3: "Night - no public lighting",
        4: "Night - public lighting off",
        5: "Night - public lighting on",
    },
    "agg": {
        1: "Outside urban area",
        2: "Urban area",
    },
    "int": {
        1: "No intersection",
        2: "X intersection",
        3: "T intersection",
        4: "Y intersection",
        5: "Intersection with 4+ branches",
        6: "Roundabout",
        7: "Square",
        8: "Level crossing",
        9: "Other intersection",
    },
    # -----------------------------------------------------------------------
    # IMPORTANT:
    #
    # Raw BAAC atm:
    #   1 = Normal
    #   2..7 = adverse
    #   8..9 = normal
    #
    # Training preprocessing transforms this to:
    #   0 = normal
    #   1 = adverse
    #
    # Therefore ONLY 0/1 are exposed to the API.
    #   BAAC:
    #     1 → 0
    #     2 → 1
    #     3 → 1
    #     4 → 1
    #     5 → 1
    #     6 → 1
    #     7 → 1
    #     8 → 0
    #     9 → 0
    # -----------------------------------------------------------------------
    "atm": {
        0: "Good weather",
        1: "Adverse weather",
    },
    "col": {
        1: "Two vehicles - frontal",
        2: "Two vehicles - rear-end",
        3: "Two vehicles - side",
        4: "Three+ vehicles - chain collision",
        5: "Three+ vehicles - multiple collision",
        6: "Other collision",
        7: "No collision",
    },
}


# ---------------------------------------------------------------------------
# Numeric feature constraints
# ---------------------------------------------------------------------------

FEATURE_RANGES: Final[dict[str, tuple[int | float, int | float]]] = {
    "year_acc": (2021, 2024),
    "victim_age": (1, 120),
    "nb_victim": (1, 100),
    "nb_vehicles": (1, 100),
    "vma": (1, 130),
    "jour": (1, 31),
    "mois": (1, 12),
    "dep": (1, 976),
    "com": (1, 99999),
    "lat": (41.0, 51.0),
    "long": (-5.0, 10.0),
    "hour": (0, 23),
}
