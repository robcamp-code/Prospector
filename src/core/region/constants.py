"""Region and state definitions for geographic targeting."""

from enum import StrEnum


class EastCoastState(StrEnum):
    MAINE = "Maine"
    NEW_HAMPSHIRE = "New Hampshire"
    VERMONT = "Vermont"
    MASSACHUSETTS = "Massachusetts"
    RHODE_ISLAND = "Rhode Island"
    CONNECTICUT = "Connecticut"
    NEW_YORK = "New York"
    NEW_JERSEY = "New Jersey"
    PENNSYLVANIA = "Pennsylvania"
    DELAWARE = "Delaware"
    MARYLAND = "Maryland"
    VIRGINIA = "Virginia"
    NORTH_CAROLINA = "North Carolina"
    SOUTH_CAROLINA = "South Carolina"
    GEORGIA = "Georgia"
    FLORIDA = "Florida"


class WestCoastState(StrEnum):
    CALIFORNIA = "California"
    OREGON = "Oregon"
    WASHINGTON = "Washington"
    ALASKA = "Alaska"
    HAWAII = "Hawaii"


class MidwestState(StrEnum):
    OHIO = "Ohio"
    INDIANA = "Indiana"
    ILLINOIS = "Illinois"
    MICHIGAN = "Michigan"
    WISCONSIN = "Wisconsin"
    MINNESOTA = "Minnesota"
    IOWA = "Iowa"
    MISSOURI = "Missouri"
    NORTH_DAKOTA = "North Dakota"
    SOUTH_DAKOTA = "South Dakota"
    NEBRASKA = "Nebraska"
    KANSAS = "Kansas"


class SouthState(StrEnum):
    TEXAS = "Texas"
    OKLAHOMA = "Oklahoma"
    ARKANSAS = "Arkansas"
    LOUISIANA = "Louisiana"
    MISSISSIPPI = "Mississippi"
    ALABAMA = "Alabama"
    TENNESSEE = "Tennessee"
    KENTUCKY = "Kentucky"
    WEST_VIRGINIA = "West Virginia"


class MountainWestState(StrEnum):
    MONTANA = "Montana"
    IDAHO = "Idaho"
    WYOMING = "Wyoming"
    COLORADO = "Colorado"
    NEW_MEXICO = "New Mexico"
    ARIZONA = "Arizona"
    UTAH = "Utah"
    NEVADA = "Nevada"


REGIONS = {
    "east_coast": EastCoastState,
    "west_coast": WestCoastState,
    "midwest": MidwestState,
    "south": SouthState,
    "mountain_west": MountainWestState,
}


ALL_STATES = [state.value for region in REGIONS.values() for state in region]
