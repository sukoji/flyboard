"""Which neurons are the fly's ears, and which neurons we read its 'taste in music' from.

All names come from the MaleCNS annotations (`type`, `synonyms` columns).
"""
EARS = {
    "JO-B": dict(prefix="JO-B"),  # low-frequency vibration, needed for courtship song
    "JO-A": dict(prefix="JO-A"),  # higher-frequency vibration
}

READOUTS = {
    "aPN1": dict(synonym="Vaughan 2014: aPN1"),       # song-responsive AMMC projection neurons
    "pC2l": dict(synonym="Nojima 2021: pC2l"),        # pulse-song responsive, drive courtship
    "pC1": dict(prefix="pC1"),                        # male courtship/arousal hub (P1 cluster)
    "pIP10": dict(types=["pIP10"]),                   # descending song command neuron
    "song_pattern": dict(types=["vPR6", "dPR1", "vMS11"]),  # VNC song pattern neurons
    "GF": dict(types=["DNp01"]),                      # giant fiber: escape jump
}

# score name -> readout groups averaged into it
SCORES = {
    "heart": ["aPN1", "pC2l"],          # "I hear a love song"
    "fire": ["pC1"],                    # "I'm into it"
    "mic": ["pIP10", "song_pattern"],   # "I want to sing back"
    "panic": ["GF"],                    # "jump scare"
}


def groups(brain, spec):
    return {k: brain.ids(**v) for k, v in spec.items()}
