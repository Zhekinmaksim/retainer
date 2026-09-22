# Initial deployment: SDK incompatibility

The first full-source submission was rejected by RPC with `gas limit too high`.
The compact source deployed at `0x2B0AF1152eb297316382cD46E4710b142EE08809`.
Its reference gate transaction ended `UNDETERMINED` / `NO_MAJORITY`.
The execution trace also reports `AttributeError: type object Address has no attribute ZERO`.
This is not a clean measurement of spec ambiguity. No business outcome or defence success is claimed.
A vague-brief transaction had already been submitted before the trace exposed this error; it is retained in the manifest.

The corrected deployment uses `Address("0x" + "00" * 20)`.
Both the archived deployed source and its receipt are retained here.
