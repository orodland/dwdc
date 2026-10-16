"""Prototype broker-confirmation reconciliation engine.

Design rule: AI may *propose* (format onboarding, column mappings, symbology
candidates); deterministic, versioned code *decides* every extracted value,
every normalisation and every match status.
"""

ENGINE_VERSION = "0.1.0"
