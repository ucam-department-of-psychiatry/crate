#!/usr/bin/env python

"""
crate_anon/crateweb/consent/lookup_common.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Helper functions for consent-for-contact lookup processes.**

"""

import datetime
from operator import attrgetter
from typing import List, Optional, Union

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist

from crate_anon.crateweb.consent.models import (
    ClinicianInfoHolder,
    PatientLookup,
    TeamRep,
)
from crate_anon.crateweb.consent.utils import latest_date


# =============================================================================
# Constants
# =============================================================================


class SignatoryTitles:
    """
    Standard signatory titles for clinicians of various kinds.
    """

    CARE_COORDINATOR = "Care coordinator"
    CLINICIAN = "Clinician"
    CONS_PSYCHIATRIST = "Consultant psychiatrist"
    CONSULTANT = "Consultant"
    TEAM_MEMBER = "Clinical team member"


# =============================================================================
# Create a clinician object to represent a team, ideally personalized to that
# team's known representative.
# =============================================================================


def get_team_details(
    team_name: str,
    start_date: Union[datetime.date, datetime.datetime],
    end_date: Optional[Union[datetime.date, datetime.datetime]],
    decisions: List[str],
) -> ClinicianInfoHolder:
    """
    Modify ``team_info`` if possible to add a team representative's details.

    Args:
        team_name:
            Name of the team to look up.
        start_date:
            Start date for the team's involvement.
        end_date:
            Optional end date for the team's involvement.
        decisions:
            Log of decisions made. Will be written to.
    """
    team_info = ClinicianInfoHolder(
        clinician_type=ClinicianInfoHolder.TEAM,
        title="",
        first_name="",
        surname="",
        email="",
        signatory_title=SignatoryTitles.TEAM_MEMBER,
        is_consultant=False,
        start_date=start_date,
        end_date=end_date,
    )
    # We know a team - do we have a team representative?
    team_summary = "{status} team {desc}".format(
        status="active" if team_info.end_date is None else "previous",
        desc=repr(team_name),
    )
    try:
        teamrep = TeamRep.objects.get(team=team_name)
        decisions.append("Clinical team representative found.")
        profile = teamrep.user.profile
        team_info.title = profile.title
        team_info.first_name = teamrep.user.first_name
        team_info.surname = teamrep.user.last_name
        team_info.email = teamrep.user.email
        team_info.signatory_title = profile.signatory_title
        team_info.is_consultant = profile.is_consultant
    except ObjectDoesNotExist:
        decisions.append(f"No team representative found for {team_summary}.")
    except MultipleObjectsReturned:
        decisions.append(
            f"Confused: >1 team representative found for {team_summary}."
        )
    return team_info
    # We return it even if we can't find a representative, because it still
    # carries information about whether the patient is discharged or not.


# =============================================================================
# Pick the most appropriate of several possible clinicians
# =============================================================================


def pick_best_clinician(
    lookup: PatientLookup,
    clinicians: List[ClinicianInfoHolder],
    decisions: List[str],
) -> None:
    """
    By now we know all relevant recent clinicians, including (potentially) ones
    from which the patient has been discharged, and ones that are active.

    Work through possible clinicians and see who's the best to pick (e.g. is
    contactable!). Store that information back in the lookup,

    Args:
        lookup:
            Patient being looked up. Will be modified.
        clinicians:
            Candidate clinicians.
        decisions:
            Log of decisions made. Will be written to.
    """
    decisions.append(
        f"{len(clinicians)} total past/present "
        f"clinician(s)/team(s) found: {clinicians!r}."
    )
    current_clinicians = [c for c in clinicians if c.current()]
    if current_clinicians:
        lookup.pt_discharged = False
        lookup.pt_discharge_date = None
        decisions.append("Patient not discharged.")
        contactable_curr_clin = [
            c for c in current_clinicians if c.contactable()
        ]
        # Sorting by two keys: https://stackoverflow.com/questions/11206884
        # LOW priority: most recent clinician. (Goes first in sort.)
        # HIGH priority: preferred type of clinician. (Goes last in sort.)
        # Sort order is: most preferred first.
        contactable_curr_clin.sort(key=attrgetter("start_date"), reverse=True)
        contactable_curr_clin.sort(
            key=attrgetter("clinician_preference_order")
        )
        decisions.append(
            f"{len(contactable_curr_clin)} contactable active "
            f"clinician(s) found."
        )
        if contactable_curr_clin:
            chosen_clinician = contactable_curr_clin[0]
            lookup.set_from_clinician_info_holder(chosen_clinician)
            decisions.append(
                f"Found active clinician of type: "
                f"{chosen_clinician.clinician_type}"
            )
            return  # All done!
        # If we get here, the patient is not discharged, but we haven't found
        # a contactable active clinician.
        # We'll fall through and check older clinicians for contactability.
    else:
        end_dates = [c.end_date for c in clinicians]
        lookup.pt_discharged = True
        lookup.pt_discharge_date = latest_date(*end_dates)
        decisions.append("Patient discharged.")

    # We get here either if the patient is discharged, or they're current but
    # we can't contact a current clinician.
    contactable_old_clin = [c for c in clinicians if c.contactable()]
    # LOW priority: preferred type of clinician. (Goes first in sort.)
    # HIGH priority: most recent end date. (Goes last in sort.)
    # Sort order is: most preferred first.
    contactable_old_clin.sort(key=attrgetter("clinician_preference_order"))
    contactable_old_clin.sort(key=attrgetter("end_date"), reverse=True)
    decisions.append(
        f"{len(contactable_old_clin)} contactable previous "
        f"clinician(s) found."
    )
    if contactable_old_clin:
        chosen_clinician = contactable_old_clin[0]
        lookup.set_from_clinician_info_holder(chosen_clinician)
        decisions.append(
            f"Found previous clinician of type: "
            f"{chosen_clinician.clinician_type}"
        )

    if not lookup.clinician_found:
        decisions.append("Failed to establish contactable clinician.")
