def parse_to_macro_signal(simulation_result: dict) -> dict:
    return {
        "direction": simulation_result.get("direction", "NEUTRAL").upper(),
        "confidence": simulation_result.get("confidence", 0),
        "recommended_tf": simulation_result.get("recommended_tf", "H1"),
        "reasoning": simulation_result.get("reasoning", ""),
        "raw_output": simulation_result.get("raw_output", {}),
    }
