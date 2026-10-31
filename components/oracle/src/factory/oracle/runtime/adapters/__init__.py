"""Verifier adapters for the oracle brick.

Only the domain-agnostic ``GenericFallbackVerifier`` ships here. Domain
verifiers (e.g. a pentest verifier) live in their own packs as
DATA and register into the overlay via ``factory.oracle.interface``.
"""
