#!/usr/bin/env python
# crate_anon/anonymise/config_singleton.py

from crate_anon.anonymise.config import Config


# =============================================================================
# Singleton config
# =============================================================================

config = Config()

# A singleton class here is messy.
# The reason we use it is that class definitions, such as PatientInfo,
# depend on things set in the config, even before instances are created.
